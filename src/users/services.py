from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select

from src.database.core import DbSession
from src.schemas.users.users import Patient, User
from src.users.models import DoctorProfile, PatientOnboarding, PatientProfile


def get_user(db: DbSession, user_id: str) -> User:
    stmt = select(User).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return user

def get_profile(db: DbSession, user_id: str) -> PatientProfile | DoctorProfile:
    """
    Returns the user's profile.
    Possible to return either PatientProfile or DoctorProfile
    """

    # user = db.query(User).filter(User.id == user_id).first()
    user = get_user(db, user_id)

    if str(user.role) == "patient":
        if user.patient_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found for this user.")
        return user.patient_profile
    elif str(user.role) == "doctor":
        if user.doctor_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found for this user.")
        return user.doctor_profile

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User Profile is corrupted. Hence something went wrong.")

def onboard_user(db: DbSession, user_id: str, request: PatientOnboarding) -> User:
    """
    For onboarding patients.
    Returns current user.
    """

    user = get_user(db, user_id)

    if user.patient_profile is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already onboarded.")

    if str(user.role) == "patient":
        if user.patient_profile is None:
            user.patient_profile = Patient(
                user_id=user.id,
                patient_id="patient_"+str(uuid4()),
                date_of_birth=request.date_of_birth,
                gender=request.gender,
                phone_number=request.phone_number,
                address=request.address,
                blood_group=request.blood_group,
                height_cm=request.height_cm,
                weight_kg=request.weight_kg,
                allergies=request.allergies,
                current_medications=request.current_medications,
                medical_history=request.medical_history,
                emergency_contact_name=request.emergency_contact_name,
                emergency_contact_phone=request.emergency_contact_phone,
                consent_hipaa=request.consent_hipaa,
            )

    user.is_onboarded = True # type: ignore
    db.commit()
    db.refresh(user)

    return user

def update_user(db: DbSession, user_id: str, request: PatientOnboarding) -> User:
    """
    For updating a user's profile data.
    Returns User
    """

    user = get_user(db, user_id)
    ALLOWED_FIELDS = {
        "date_of_birth",
        "gender",
        "phone_number",
        "address",
        "blood_group",
        "height_cm",
        "weight_kg",
        "allergies",
        "current_medications",
        "medical_history",
        "emergency_contact_name",
        "emergency_contact_phone",
        "consent_hipaa",
    }
    for field, value in request.model_dump().items():
        if field in ALLOWED_FIELDS:
            setattr(user.patient_profile, field, value)

    if str(user.role) == "doctor":
        if user.doctor_profile is None:
            raise HTTPException(400, "Doctor profile must be created separately")
        for field, value in request.model_dump().items():
            if field in ALLOWED_FIELDS:
                setattr(user.doctor_profile, field, value)

    return user
