from fastapi import APIRouter, HTTPException, status

from src.auth.services import CurrentUser
from src.cases.models import (
    CaseApprovalRequest,
    CaseCreate,
    CaseResponse,
    CaseUpdate,
    DoctorNoteCreate,
)
from src.cases.services import case_service
from src.database.core import DbSession
from src.database.mongo import MongoDb

router = APIRouter(prefix="/cases", tags=["cases"])

@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    user: CurrentUser,
    case_data: CaseCreate,
    db: DbSession,
    mongo_db: MongoDb
):
    """
    Create a new case (doctor only).
    Dual-writes to: PostgreSQL (relational) + MongoDB (full document)
    """
    # if user.role != "doctor":
    #     raise HTTPException(status_code=403, detail="Only doctors can create cases")
    new_case = await case_service.create_case(
        db=db,
        mongo_db=mongo_db,
        doctor_id=user.user_id,
        case_data=case_data
    )
    return CaseResponse(**new_case.dict())

@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb
):
    """Fetch complete case (merge Postgres + MongoDB data)"""
    case = await case_service.get_case_by_id(db, mongo_db, case_id, user.user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Log view in audit trail
    await case_service.add_audit_log(db, mongo_db, case_id, "viewed", user.user_id)

    return CaseResponse(**case.dict())

@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    user: CurrentUser,
    case_update: CaseUpdate,
    db: DbSession,
    mongo_db: MongoDb
):
    """Update case (subjective/objective/assessment/plan sections)"""
    case = await case_service.get_case_by_id(db, mongo_db, case_id, user.user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    updated_case = await case_service.update_case(db, mongo_db, case_id, case_update, user.user_id)
    if not updated_case:
         raise HTTPException(status_code=403, detail="Not authorized to edit this case")

    return CaseResponse(**updated_case.dict())

@router.post("/{case_id}/approve", response_model=CaseResponse)
async def approve_case(
    case_id: str,
    user: CurrentUser,
    approval_data: CaseApprovalRequest,
    db: DbSession,
    mongo_db: MongoDb
):
    """Doctor approval workflow with optional approval notes"""
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can approve cases")

    approved_case = await case_service.approve_case(
        db, mongo_db, case_id, user.user_id, approval_data.approval_notes
    )
    if not approved_case:
        raise HTTPException(status_code=404, detail="Case not found or not owned by you")

    return CaseResponse(**approved_case.dict())

@router.get("/doctor/{doctor_id}/list")
async def list_doctor_cases(
    doctor_id: str,
    user: CurrentUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 20,
    status: str = None
):
    """List all cases for a doctor (doctor view)"""
    # Assuming CurrentUser middleware sets user_id
    if user.role != "doctor" or str(user.user_id) != doctor_id:
        raise HTTPException(status_code=403, detail="Can only view your own cases")

    cases = await case_service.list_cases_by_doctor(
        db, doctor_id, status=status, skip=skip, limit=limit
    )
    return {"total": len(cases), "cases": cases}

@router.get("/patient/{patient_id}/list")
async def list_patient_cases(
    patient_id: str,
    user: CurrentUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 20
):
    """List all cases for a patient (patient view)"""
    if user.role != "patient" or str(user.user_id) != patient_id:
        raise HTTPException(status_code=403, detail="Can only view your own cases")

    cases = await case_service.list_cases_by_patient(
        db, patient_id, skip=skip, limit=limit
    )
    return {"total": len(cases), "cases": cases}

@router.post("/{case_id}/notes")
async def add_doctor_note(
    case_id: str,
    user: CurrentUser,
    note_data: DoctorNoteCreate,
    db: DbSession,
    mongo_db: MongoDb
):
    """Add a note to case"""
    if user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can add notes")

    note = await case_service.add_doctor_note(
        db, mongo_db, case_id, user.user_id, note_data
    )
    if not note:
        raise HTTPException(status_code=404, detail="Case not found or failed to add note")

    return note

@router.get("/{case_id}/notes")
async def get_case_notes(
    case_id: str,
    user: CurrentUser,
    db: DbSession,
    mongo_db: MongoDb
):
    """Get all notes for a case"""
    notes = await case_service.get_doctor_notes(db, mongo_db, case_id, user.user_id)
    return {"notes": notes}
