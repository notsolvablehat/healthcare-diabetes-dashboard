import uuid
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.orm import Session

from src.cases.models import Case, CaseCreate, CaseUpdate, DoctorNote, DoctorNoteCreate
from src.schemas.cases import Case as CaseORM
from src.schemas.users.users import Patient


def resolve_patient_user_id(db: Session, patient_identifier: str) -> str:
    """
    Resolve patient identifier to user_id.
    The identifier can be:
    - patient_id (from patients table, same as user_id)
    - user_id (from users table)

    Returns the user_id for the foreign key constraint.
    """
    # Try to find by patient_id first
    patient = db.query(Patient).filter(Patient.patient_id == patient_identifier).first()
    if patient:
        return patient.user_id

    # If not found, assume it's already a user_id and verify it exists
    patient = db.query(Patient).filter(Patient.user_id == patient_identifier).first()
    if patient:
        return patient.user_id

    raise HTTPException(
        status_code=404,
        detail=f"Patient not found with identifier: {patient_identifier}"
    )


class CaseService:
    async def create_case(self, db: Session, mongo_db: AsyncDatabase, doctor_id: str, case_data: CaseCreate) -> Case:
        """
        Create case in BOTH PostgreSQL and MongoDB.
        Returns complete Case object.
        """
        # Generate IDs
        case_uuid = str(uuid.uuid4())
        case_id = f"CASE{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"

        # Resolve patient_id to user_id (handles both business patient_id and user_id)
        patient_user_id = resolve_patient_user_id(db, case_data.patient_id)

        # ============ POSTGRESQL WRITE ============
        postgres_case = CaseORM(
            id=case_uuid,
            case_id=case_id,
            patient_id=patient_user_id,
            doctor_id=doctor_id,
            status="open",
            chief_complaint=case_data.chief_complaint,
            created_at=datetime.utcnow(),
            mongo_case_id=None  # Will update after MongoDB write
        )
        db.add(postgres_case)
        db.flush()  # Get the ID without committing

        # ============ MONGODB WRITE ============
        # Note: Convert UUIDs to strings for MongoDB compatibility
        case_document = Case(
            id=case_uuid,
            case_id=case_id,
            patient_id=patient_user_id,
            doctor_id=doctor_id,
            encounter_id=case_data.encounter_id,
            case_type=case_data.case_type,
            chief_complaint=case_data.chief_complaint,
            subjective=case_data.subjective,
            objective=case_data.objective,
            assessment=case_data.assessment,
            plan=case_data.plan,
            created_at=datetime.utcnow()
        ).model_dump(mode="json")  # Use mode="json" to serialize UUIDs to strings

        result = await mongo_db["cases"].insert_one(case_document)
        mongo_id = str(result.inserted_id)

        # Update PostgreSQL with MongoDB reference
        postgres_case.mongo_case_id = mongo_id
        db.commit()

        return Case(**case_document)

    async def get_case_by_id(self, db: Session, mongo_db: AsyncDatabase, case_id: str, user_id: str) -> Case | None:
        """
        Fetch case merging PostgreSQL and MongoDB data.
        Authorization check included.
        """
        # Get from PostgreSQL first (faster queries)
        postgres_case = db.query(CaseORM).filter(
            CaseORM.case_id == case_id
        ).first()

        if not postgres_case:
            return None

        # Authorization check
        # Note: In a real app, strict checks would be here. For now we check if related.
        # Ideally, we pass role and id so we can allow admins etc.
        if str(postgres_case.doctor_id) != user_id and str(postgres_case.patient_id) != user_id:
            # We return None to hide existence, or raise Forbidden in controller
            return None

        # Get full document from MongoDB
        try:
            mongo_case = await mongo_db["cases"].find_one({
                "_id": ObjectId(postgres_case.mongo_case_id)
            })

            if mongo_case:
                mongo_case["_id"] = str(mongo_case["_id"])
                return Case(**mongo_case)
        except Exception as e:
            # MongoDB error - raise HTTP exception with details
            raise HTTPException(
                status_code=500,
                detail=f"Database error while fetching case: {str(e)}"
            )

        return None

    async def list_cases_by_doctor(
        self, db: Session, doctor_id: str, skip: int = 0, limit: int = 20, status: str = None
    ) -> list[dict]:
        """List cases for a doctor (Postgres only for list view)"""
        query = db.query(CaseORM).filter(CaseORM.doctor_id == doctor_id)

        if status:
            query = query.filter(CaseORM.status == status)

        cases = query.offset(skip).limit(limit).all()

        # Return summary list
        # We assume the frontend needs basic info.
        # Adapt to CaseResponse or a summary model if needed.
        # For now, converting ORM to dict manually or using Pydantic if we had a summary model.
        # We will return list of dicts.
        return [
            {
                "case_id": c.case_id,
                "created_at": c.created_at,
                "chief_complaint": c.chief_complaint,
                "status": c.status,
                "patient_id": str(c.patient_id)
            } for c in cases
        ]

    async def list_cases_by_patient(
        self, db: Session, patient_id: str, skip: int = 0, limit: int = 20
    ) -> list[dict]:
        """List cases for a patient"""
        query = db.query(CaseORM).filter(CaseORM.patient_id == patient_id)

        cases = query.offset(skip).limit(limit).all()

        return [
             {
                "case_id": c.case_id,
                "created_at": c.created_at,
                "chief_complaint": c.chief_complaint,
                "status": c.status,
                "doctor_id": str(c.doctor_id)
            } for c in cases
        ]

    async def add_audit_log(self, db: Session, mongo_db: AsyncDatabase, case_id: str, action: str, user_id: str):
        """Add action to audit trail"""
        postgres_case = db.query(CaseORM).filter(CaseORM.case_id == case_id).first()

        if not postgres_case or not postgres_case.mongo_case_id:
            return

        log_entry = {
            "action": action,
            "timestamp": datetime.utcnow(),
            "performed_by": user_id,
        }

        await mongo_db["cases"].update_one(
            {"_id": ObjectId(postgres_case.mongo_case_id)},
            {"$push": {"audit_trail": log_entry}}
        )

    async def add_doctor_note(
        self, db: Session, mongo_db: AsyncDatabase, case_id: str, doctor_id: str, note_data: DoctorNoteCreate
    ) -> DoctorNote:

        note = DoctorNote(
            note_id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            created_by=doctor_id,
            content=note_data.content,
            note_type=note_data.note_type,
            visibility=note_data.visibility,
            linked_to_case_section=note_data.linked_to_case_section
        )

        postgres_case = db.query(CaseORM).filter(CaseORM.case_id == case_id).first()
        if not postgres_case:
            raise HTTPException(
                status_code=404,
                detail=f"Case not found with ID: {case_id}"
            )

        # Add to MongoDB
        await mongo_db["cases"].update_one(
            {"_id": ObjectId(postgres_case.mongo_case_id)},
            {"$push": {"doctor_notes": note.model_dump(mode="json")}}
        )

        await self.add_audit_log(db, mongo_db, case_id, "note_added", doctor_id)

        return note

    async def get_doctor_notes(self, db: Session, mongo_db: AsyncDatabase, case_id: str, user_id: str):
        postgres_case = db.query(CaseORM).filter(CaseORM.case_id == case_id).first()
        if not postgres_case:
            raise HTTPException(
                status_code=404,
                detail=f"Case not found with ID: {case_id}"
            )

        mongo_case = await mongo_db["cases"].find_one(
            {"_id": ObjectId(postgres_case.mongo_case_id)},
            {"doctor_notes": 1}
        )

        if not mongo_case or "doctor_notes" not in mongo_case:
            return []

        return mongo_case["doctor_notes"]


    async def update_case(self, db: Session, mongo_db: AsyncDatabase, case_id: str, case_update: CaseUpdate, user_id: str) -> Case:
        """
        Update case in both databases.
        Track amendments in MongoDB.
        """
        postgres_case = db.query(CaseORM).filter(
            CaseORM.case_id == case_id
        ).first()

        if not postgres_case:
            raise HTTPException(
                status_code=404,
                detail=f"Case not found with ID: {case_id}"
            )

        # Check authorization (basic owner check)
        if str(postgres_case.doctor_id) != user_id and str(postgres_case.patient_id) != user_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to update this case"
            )

        # Get current MongoDB document to track changes
        mongo_case = await mongo_db["cases"].find_one({
            "_id": ObjectId(postgres_case.mongo_case_id)
        })

        # In a real app, strict diffing logic here (as per your guide)
        # For MVP, we apply updates.

        # Update PostgreSQL
        postgres_case.updated_at = datetime.utcnow()
        if case_update.status:
            postgres_case.status = case_update.status

        # Update MongoDB
        update_dict = case_update.model_dump(mode="json", exclude_unset=True)
        if not update_dict:
             mongo_case["_id"] = str(mongo_case["_id"]) # ensure ID stringification if no update
             return Case(**mongo_case)

        update_dict["updated_at"] = datetime.utcnow().isoformat()

        await mongo_db["cases"].update_one(
            {"_id": ObjectId(postgres_case.mongo_case_id)},
            {"$set": update_dict}
        )

        db.commit()

        # Return updated document
        updated_mongo = await mongo_db["cases"].find_one({
            "_id": ObjectId(postgres_case.mongo_case_id)
        })
        updated_mongo["_id"] = str(updated_mongo["_id"])
        return Case(**updated_mongo)

    async def approve_case(self, db: Session, mongo_db: AsyncDatabase, case_id: str, doctor_id: str, approval_notes: str | None = None) -> Case | None:
        """
        Approve a case and update status in both databases.
        Handles potential UUID/string type mismatches in doctor_id.
        """
        postgres_case = db.query(CaseORM).filter(CaseORM.case_id == case_id).first()

        if not postgres_case:
            raise HTTPException(
                status_code=404,
                detail=f"Case not found with ID: {case_id}"
            )
        
        if str(postgres_case.doctor_id) != str(doctor_id):
            raise HTTPException(
                status_code=403,
                detail="Only the assigned doctor can approve this case"
            )

        # PostgreSQL Update
        postgres_case.status = "approved_by_doctor"
        postgres_case.updated_at = datetime.utcnow()
        db.commit()

        # MongoDB Update
        approval_data = {
            "approved": True,
            "approved_by": doctor_id,
            "approval_date": datetime.utcnow()
        }

        # Add approval_notes if provided
        if approval_notes:
            approval_data["approval_notes"] = approval_notes

        await mongo_db["cases"].update_one(
            {"_id": ObjectId(postgres_case.mongo_case_id)},
            {"$set": {
                "status": "approved_by_doctor",
                "approvals": approval_data
            }}
        )

        # Return full case
        return await self.get_case_by_id(db, mongo_db, case_id, doctor_id)


case_service = CaseService()
