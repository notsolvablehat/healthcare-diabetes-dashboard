from fastapi import APIRouter, HTTPException, status

from src.assignments.models import PatientAssignRequest, RevokeAccessRequest
from src.auth.services import CurrentUser
from src.database.core import DbSession

from .services import (
    assign_patient,
    get_doctors,
    get_patient_by_email,
    get_patients,
    get_specialities,
    revoke_patient_access,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("/specialities")
def list_specialities(db: DbSession):
    """
    Fetch all available doctor specializations in the system.
    No authentication required - public endpoint.
    """
    return get_specialities(db)

@router.get("/patient")
def get_my_patients(user: CurrentUser, db: DbSession):
    """
    Fetch all patients currently assigned to the logged-in doctor.
    """
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return get_patients(user.user_id, db)

@router.get("/doctors")
def get_my_doctors(user: CurrentUser, db: DbSession):
    """
    Fetch all doctors currently assigned to the logged-in patient.
    """
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")

    return get_doctors(user_id=user.user_id, db=db)

@router.get("/get-my-patient/{patient_email}")
def get_my_patient_by_email(patient_email: str, user: CurrentUser, db: DbSession):
    """
    Get complete patient information by email.
    Only returns data if the patient is assigned to the logged-in doctor.
    """
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")

    if user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access patient details.")

    patient = get_patient_by_email(db, user.user_id, patient_email)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or not assigned to you."
        )

    return patient

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
