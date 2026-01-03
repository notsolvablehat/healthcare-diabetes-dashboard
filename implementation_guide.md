# IMPLEMENTATION GUIDE: Case Management with Doctor Notes

## Quick Start: Using Your Schemas

### 1. FastAPI Controller Structure

```python
# src/cases/controller.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime

from src.database.core import DbSession
from src.auth.services import CurrentUser
from src.cases.models import CaseCreate, CaseUpdate, CaseResponse
from src.cases.services import case_service
from case_schema_models import Case, DoctorNoteCreate

router = APIRouter(prefix="/cases", tags=["cases"])

# ============================================================================
# CASE CRUD OPERATIONS
# ============================================================================

@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    user: CurrentUser,
    case_data: CaseCreate,
    db: DbSession
):
    """
    Create a new case (doctor only).
    Dual-writes to: PostgreSQL (relational) + MongoDB (full document)
    """
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can create cases")
    
    new_case = case_service.create_case(
        db=db,
        doctor_id=user.id,
        case_data=case_data
    )
    return CaseResponse(**new_case.dict())

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    user: CurrentUser,
    db: DbSession
):
    """Fetch complete case (merge Postgres + MongoDB data)"""
    case = case_service.get_case_by_id(db, case_id, user.id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Log view in audit trail
    case_service.add_audit_log(case_id, "viewed", user.id)
    
    return CaseResponse(**case.dict())

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    user: CurrentUser,
    case_update: CaseUpdate,
    db: DbSession
):
    """Update case (subjective/objective/assessment/plan sections)"""
    case = case_service.get_case_by_id(db, case_id, user.id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check authorization (doctor or patient viewing own case)
    if not case_service.can_edit_case(user, case):
        raise HTTPException(status_code=403, detail="Not authorized to edit this case")
    
    updated_case = case_service.update_case(db, case_id, case_update, user.id)
    
    return CaseResponse(**updated_case.dict())

@router.post("/{case_id}/approve", response_model=CaseResponse)
def approve_case(
    case_id: str,
    user: CurrentUser,
    approval_notes: str = None,
    db: DbSession = None
):
    """Doctor approval workflow"""
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can approve cases")
    
    approved_case = case_service.approve_case(
        db, case_id, user.id, approval_notes
    )
    return CaseResponse(**approved_case.dict())

@router.get("/doctor/{doctor_id}/list")
def list_doctor_cases(
    doctor_id: str,
    user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
    status: str = None,
    db: DbSession = None
):
    """List all cases for a doctor (doctor view)"""
    if user.role != "doctor" or user.id != doctor_id:
        raise HTTPException(status_code=403, detail="Can only view your own cases")
    
    cases = case_service.list_cases_by_doctor(
        db, doctor_id, status=status, skip=skip, limit=limit
    )
    return {"total": len(cases), "cases": cases}

@router.get("/patient/{patient_id}/list")
def list_patient_cases(
    patient_id: str,
    user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
    db: DbSession = None
):
    """List all cases for a patient (patient view)"""
    if user.role != "patient" or user.id != patient_id:
        raise HTTPException(status_code=403, detail="Can only view your own cases")
    
    cases = case_service.list_cases_by_patient(
        db, patient_id, skip=skip, limit=limit
    )
    # Patient sees summaries only (no sensitive internal notes)
    return case_service.sanitize_for_patient(cases)

# ============================================================================
# DOCTOR NOTES OPERATIONS
# ============================================================================

@router.post("/{case_id}/notes")
def add_doctor_note(
    case_id: str,
    user: CurrentUser,
    note_data: DoctorNoteCreate,
    db: DbSession
):
    """Add a note to case"""
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can add notes")
    
    case = case_service.get_case_by_id(db, case_id, user.id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    note = case_service.add_doctor_note(
        case_id=case_id,
        doctor_id=user.id,
        note_data=note_data
    )
    return note

@router.get("/{case_id}/notes")
def get_case_notes(
    case_id: str,
    user: CurrentUser,
    db: DbSession
):
    """Get all notes for a case"""
    notes = case_service.get_doctor_notes(case_id, user.id)
    return {"notes": notes}

@router.patch("/notes/{note_id}")
def amend_doctor_note(
    note_id: str,
    user: CurrentUser,
    amendment_data: dict,
    db: DbSession
):
    """Amend an existing note (creates amendment record)"""
    updated_note = case_service.amend_note(
        note_id=note_id,
        doctor_id=user.id,
        reason=amendment_data.get("reason"),
        new_content=amendment_data.get("new_content")
    )
    return updated_note

@router.get("/notes/{note_id}/history")
def get_note_amendment_history(
    note_id: str,
    user: CurrentUser
):
    """View amendment history for a note"""
    history = case_service.get_note_amendment_history(note_id, user.id)
    return {"amendment_history": history}

# ============================================================================
# PROBLEM LIST OPERATIONS
# ============================================================================

@router.post("/{case_id}/problems")
def add_problem_to_case(
    case_id: str,
    user: CurrentUser,
    problem_data: dict,
    db: DbSession
):
    """Add a diagnosis/problem to case assessment"""
    problem = case_service.add_problem(
        case_id=case_id,
        doctor_id=user.id,
        problem_data=problem_data
    )
    return problem

@router.delete("/{case_id}/problems/{problem_id}")
def remove_problem_from_case(
    case_id: str,
    problem_id: str,
    user: CurrentUser,
    db: DbSession
):
    """Remove problem from case"""
    case_service.remove_problem(case_id, problem_id, user.id)
    return {"status": "deleted"}

# ============================================================================
# LAB & IMAGING
# ============================================================================

@router.post("/{case_id}/labs")
def add_lab_result(
    case_id: str,
    user: CurrentUser,
    lab_data: dict,
    db: DbSession
):
    """Add lab result to case"""
    lab = case_service.add_lab_result(case_id, user.id, lab_data)
    return lab

@router.post("/{case_id}/imaging")
def add_imaging_result(
    case_id: str,
    user: CurrentUser,
    imaging_data: dict,
    db: DbSession
):
    """Add imaging result to case"""
    imaging = case_service.add_imaging_result(case_id, user.id, imaging_data)
    return imaging

# ============================================================================
# AI ANALYSIS
# ============================================================================

@router.post("/{case_id}/analyze")
@limiter.limit("5/hour")  # Rate limit to prevent abuse
def trigger_ai_analysis(
    case_id: str,
    user: CurrentUser,
    db: DbSession
):
    """Trigger LLM analysis of case (Celery task)"""
    # This would be a Celery task in production
    from src.ai.tasks import analyze_case_task
    
    task = analyze_case_task.delay(case_id)
    return {"task_id": task.id, "status": "queued"}

@router.get("/{case_id}/summary")
def get_case_summary(
    case_id: str,
    user: CurrentUser,
    db: DbSession
):
    """Get AI-generated case summary"""
    summary = case_service.get_ai_summary(case_id, user.id)
    if not summary:
        raise HTTPException(status_code=404, detail="AI summary not yet generated")
    
    # For patients, return simplified summary
    if user.role == "patient":
        return case_service.simplify_summary_for_patient(summary)
    
    return summary
```

---

### 2. Service Layer (Business Logic)

```python
# src/cases/services.py

from datetime import datetime, date
from typing import Optional, List
import uuid
from pymongo import MongoClient
from sqlalchemy import and_, or_

from src.database.core import DbSession
from src.schemas.cases import Case as CaseORM
from case_schema_models import Case, Problem, DoctorNote

class CaseService:
    def __init__(self, db: DbSession, mongo_client: MongoClient):
        self.db = db
        self.mongo_db = mongo_client["healthcare"]
        self.cases_collection = self.mongo_db["cases"]
    
    def create_case(self, db: DbSession, doctor_id: str, case_data) -> Case:
        """
        Create case in BOTH PostgreSQL and MongoDB.
        Returns complete Case object.
        """
        # Generate IDs
        case_uuid = str(uuid.uuid4())
        case_id = f"CASE{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # ============ POSTGRESQL WRITE ============
        postgres_case = CaseORM(
            id=case_uuid,
            case_id=case_id,
            patient_id=case_data.patient_id,
            doctor_id=doctor_id,
            case_type=case_data.case_type.value,
            status="open",
            chief_complaint=case_data.chief_complaint,
            created_at=datetime.utcnow(),
            mongo_doc_id=None  # Will update after MongoDB write
        )
        db.add(postgres_case)
        db.flush()  # Get the ID without committing
        
        # ============ MONGODB WRITE ============
        case_document = Case(
            id=case_uuid,
            case_id=case_id,
            patient_id=case_data.patient_id,
            doctor_id=doctor_id,
            case_type=case_data.case_type,
            subjective=case_data.subjective,
            objective=case_data.objective,
            assessment=case_data.assessment,
            plan=case_data.plan,
            created_at=datetime.utcnow()
        ).dict()
        
        result = self.cases_collection.insert_one(case_document)
        mongo_id = str(result.inserted_id)
        
        # Update PostgreSQL with MongoDB reference
        postgres_case.mongo_doc_id = mongo_id
        db.commit()
        
        return Case(**case_document)
    
    def get_case_by_id(self, db: DbSession, case_id: str, user_id: str) -> Optional[Case]:
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
        if postgres_case.doctor_id != user_id and postgres_case.patient_id != user_id:
            return None
        
        # Get full document from MongoDB
        mongo_case = self.cases_collection.find_one({
            "_id": ObjectId(postgres_case.mongo_doc_id)
        })
        
        if mongo_case:
            mongo_case["_id"] = str(mongo_case["_id"])
            return Case(**mongo_case)
        
        return None
    
    def update_case(self, db: DbSession, case_id: str, case_update, user_id: str) -> Case:
        """
        Update case in both databases.
        Track amendments in MongoDB.
        """
        postgres_case = db.query(CaseORM).filter(
            CaseORM.case_id == case_id
        ).first()
        
        if not postgres_case:
            return None
        
        # Get current MongoDB document to track changes
        mongo_case = self.cases_collection.find_one({
            "_id": ObjectId(postgres_case.mongo_doc_id)
        })
        
        # Record amendment
        changes = {}
        if case_update.subjective and mongo_case.get("subjective") != case_update.subjective.dict():
            changes["subjective"] = {
                "oldValue": mongo_case.get("subjective"),
                "newValue": case_update.subjective.dict()
            }
        # ... repeat for other sections
        
        # Update PostgreSQL
        postgres_case.updated_at = datetime.utcnow()
        if case_update.status:
            postgres_case.status = case_update.status.value
        if case_update.severity:
            postgres_case.severity = case_update.severity.value
        
        # Update MongoDB
        update_dict = case_update.dict(exclude_unset=True)
        update_dict["updated_at"] = datetime.utcnow()
        
        self.cases_collection.update_one(
            {"_id": ObjectId(postgres_case.mongo_doc_id)},
            {"$set": update_dict}
        )
        
        # Add amendment record
        if changes:
            amendment = {
                "amendment_id": str(uuid.uuid4()),
                "amended_at": datetime.utcnow(),
                "amended_by": user_id,
                "reason": "case_update",
                "changed_fields": changes
            }
            self.cases_collection.update_one(
                {"_id": ObjectId(postgres_case.mongo_doc_id)},
                {"$push": {"amendment_history": amendment}}
            )
        
        db.commit()
        
        # Return updated document
        updated_mongo = self.cases_collection.find_one({
            "_id": ObjectId(postgres_case.mongo_doc_id)
        })
        updated_mongo["_id"] = str(updated_mongo["_id"])
        return Case(**updated_mongo)
    
    def approve_case(self, db: DbSession, case_id: str, doctor_id: str, approval_notes: str = None) -> Case:
        """Doctor approves case - workflow status update"""
        postgres_case = db.query(CaseORM).filter(
            CaseORM.case_id == case_id,
            CaseORM.doctor_id == doctor_id
        ).first()
        
        if not postgres_case:
            return None
        
        # Update PostgreSQL
        postgres_case.doctor_approved = True
        postgres_case.doctor_approved_at = datetime.utcnow()
        postgres_case.approval_notes = approval_notes
        postgres_case.status = "approved_by_doctor"
        
        # Update MongoDB
        self.cases_collection.update_one(
            {"_id": ObjectId(postgres_case.mongo_doc_id)},
            {"$set": {
                "approvals.doctor_approval": {
                    "approved": True,
                    "approved_by": doctor_id,
                    "approval_date": datetime.utcnow(),
                    "approval_notes": approval_notes
                },
                "status": "approved_by_doctor"
            }}
        )
        
        # Add audit log
        self.add_audit_log(case_id, "approved", doctor_id)
        
        db.commit()
        
        mongo_case = self.cases_collection.find_one({
            "_id": ObjectId(postgres_case.mongo_doc_id)
        })
        mongo_case["_id"] = str(mongo_case["_id"])
        return Case(**mongo_case)
    
    def add_doctor_note(self, case_id: str, doctor_id: str, note_data) -> DoctorNote:
        """Add a time-stamped note to case"""
        note_id = str(uuid.uuid4())
        
        note = DoctorNote(
            note_id=note_id,
            created_at=datetime.utcnow(),
            created_by=doctor_id,
            content=note_data.content,
            note_type=note_data.note_type,
            visibility=note_data.visibility,
            linked_to_case_section=note_data.linked_to_case_section
        )
        
        # Get case from PostgreSQL
        postgres_case = self.db.query(CaseORM).filter(
            CaseORM.case_id == case_id
        ).first()
        
        # Add to MongoDB
        self.cases_collection.update_one(
            {"_id": ObjectId(postgres_case.mongo_doc_id)},
            {"$push": {"doctor_notes": note.dict()}}
        )
        
        self.add_audit_log(case_id, "note_added", doctor_id)
        
        return note
    
    def amend_note(self, note_id: str, doctor_id: str, reason: str, new_content: str) -> dict:
        """Create amendment record for a note (immutable history)"""
        amendment = {
            "amended_at": datetime.utcnow(),
            "reason": reason,
            "amendment_content": new_content
        }
        
        # MongoDB: Push amendment to note's amendment_history
        result = self.cases_collection.update_one(
            {"doctor_notes.note_id": note_id},
            {
                "$push": {
                    "doctor_notes.$[elem].amendment_history": amendment
                }
            },
            array_filters=[{"elem.note_id": note_id}]
        )
        
        if result.modified_count == 0:
            return None
        
        return amendment
    
    def add_audit_log(self, case_id: str, action: str, user_id: str, details: str = None):
        """Add action to audit trail"""
        postgres_case = self.db.query(CaseORM).filter(
            CaseORM.case_id == case_id
        ).first()
        
        if not postgres_case:
            return
        
        log_entry = {
            "action": action,
            "timestamp": datetime.utcnow(),
            "performed_by": user_id,
            "change_details": details
        }
        
        self.cases_collection.update_one(
            {"_id": ObjectId(postgres_case.mongo_doc_id)},
            {"$push": {"audit_trail": log_entry}}
        )
    
    def sanitize_for_patient(self, cases: List[Case]) -> List[dict]:
        """Remove sensitive fields when returning to patient"""
        sanitized = []
        for case in cases:
            case_dict = case.dict()
            # Remove doctor-only notes
            case_dict["doctor_notes"] = [
                n for n in case_dict.get("doctor_notes", [])
                if n.get("visibility") in ["patient_visible", "shared"]
            ]
            # Remove amendments
            case_dict["amendment_history"] = []
            sanitized.append(case_dict)
        return sanitized
```

---

### 3. Database Schema (SQLAlchemy)

```python
# src/schemas/cases.py
class Case(Base):
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Link to Mongo
    mongo_case_id = Column(String, nullable=False, unique=True, index=True)

    # Searchable Metadata (Keep this! It's fast for lists)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String, default="open", index=True) 
    chief_complaint = Column(String) # Short text for the dashboard list view
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])
---

## Testing Your Schema

```python
# tests/test_case_schema.py

import pytest
from datetime import datetime, date
from case_schema_models import (
    Case, CaseCreate, SubjectiveSection, HistoryOfPresentIllness,
    ObjectiveSection, AssessmentSection, PlanSection, Problem,
    DoctorNote, validate_case_completeness
)

def test_case_creation():
    """Test creating a complete case"""
    case = Case(
        patient_id="pat-123",
        doctor_id="doc-456",
        case_type="initial",
        chief_complaint="Chest pain",
        subjective=SubjectiveSection(
            chief_complaint="Acute chest pain for 3 days",
            history_of_present_illness=HistoryOfPresentIllness(
                onset="2025-01-02",
                severity={"scale": 8, "description": "severe"},
                character="sharp, burning"
            )
        ),
        assessment=AssessmentSection(
            problem_list=[
                Problem(
                    rank=1,
                    problem_type="diagnosis",
                    condition="Acute Coronary Syndrome",
                    snomed_code="233861007",
                    confidence="high"
                )
            ]
        )
    )
    
    assert case.patient_id == "pat-123"
    assert case.status == "open"
    assert len(case.assessment.problem_list) == 1

def test_case_completeness():
    """Test case completeness calculation"""
    incomplete_case = Case(
        patient_id="pat-123",
        doctor_id="doc-456",
        case_type="initial",
        chief_complaint="Pain"
    )
    
    assert validate_case_completeness(incomplete_case) < 50

def test_doctor_note_creation():
    """Test creating doctor notes"""
    note = DoctorNote(
        case_id="case-789",
        content="Patient appears stable, vital signs normal",
        note_type="progress",
        visibility="shared"
    )
    
    assert note.note_type == "progress"
    assert note.visibility == "shared"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Next Steps

1. **Implement MongoDB indexes** for fast queries:
   ```javascript
   db.cases.createIndex({"patient_id": 1, "created_at": -1})
   db.cases.createIndex({"doctor_id": 1, "status": 1})
   db.cases.createIndex({"assessment.problem_list.snomed_code": 1})
   ```

2. **Add LLM integration** for case summarization (in your Celery tasks)

3. **Implement file upload** for attachments (S3 signed URLs)

4. **Add search/filter endpoints** using MongoDB aggregation

5. **Create approval workflow** UI for doctors
