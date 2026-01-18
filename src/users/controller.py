from fastapi import APIRouter, HTTPException, status
from pydantic import EmailStr

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.users.models import PatientOnboarding

from .services import (
    get_patient_profile_by_email,
    get_profile,
    onboard_user,
    update_user,
    update_user_name,
)

router = APIRouter(prefix="/users", tags=["user"])

@router.get("/me")
def read_users_me(user: CurrentUser, db: DbSession):
    from .services import get_user
    user_data = get_user(db, user.user_id)  # type: ignore
    return {
        "user_id": user_data.id,
        "role": user_data.role,
        "is_onboarded": user_data.is_onboarded,
        "email": user_data.email,
        "username": user_data.username,
        "name": user_data.name
    }

@router.get("/profile")
def get_my_profile(user: CurrentUser, db: DbSession):
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return get_profile(db=db, user_id=user.user_id)

@router.post("/onboard")
def users_onboard(user: CurrentUser, db: DbSession, request: PatientOnboarding):
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return onboard_user(db, user.user_id, request)

@router.post("/update-user")
def update_user_profile(user: CurrentUser, db: DbSession, request: PatientOnboarding):
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return update_user(db, user.user_id, request)

@router.post("/update-user-name")
def update_name_endpoint(user: CurrentUser, db: DbSession, name_of_user: str):
    if not user or not user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is required.")
    return update_user_name(db, user.user_id, name_of_user)

@router.get("/patient-profile/{patient_email}")
def get_patient_profile(user: CurrentUser, db: DbSession, patient_email: EmailStr):
    return get_patient_profile_by_email(db, user.user_id, patient_email)
