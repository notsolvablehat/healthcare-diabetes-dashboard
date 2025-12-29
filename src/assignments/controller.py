from fastapi import APIRouter, HTTPException, status

from src.assignments.models import PatientAssignRequest, RevokeAccessRequest
from src.auth.services import CurrentUser
from src.database.core import DbSession

from .services import assign_patient, get_doctors, get_patients, revoke_patient_access

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("/patient")
def get_my_patients(user: CurrentUser, db: DbSession):
    """
    Fetch all patients currently assigned to the logged-in doctor.
    """
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return get_patients(user.user_id, db)

@router.get("/doctors")
def get_my_doctors(doctor_id: str, user: CurrentUser, db: DbSession):
    """
    Fetch all doctors currently assigned to the logged-in patient.
    """
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")

    return get_doctors(user_id=user.user_id, db=db)

@router.post("/assign")
def assign_doctor_patient(user: CurrentUser, patient_info: PatientAssignRequest, db: DbSession):
    """
    Assign a doctor a patient.
    Can be done my doctor or an admin.
    """
    return assign_patient(db, user.user_id, patient_info)

@router.post("/revoke")
def revoke_patient(user: CurrentUser, db: DbSession, request_data: RevokeAccessRequest):
    """
    Revoke doctor's access from a patient.
    Can be done by doctor or an admin.\n
    `doctor_identifier` can be either email or id.\n
    Given that admin must provide a doctor_id or doctor_email.
    """
    return revoke_patient_access(db, user.user_id, request_data)
