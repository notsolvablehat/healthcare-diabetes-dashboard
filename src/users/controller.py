from fastapi import APIRouter, HTTPException, status

from src.auth.services import CurrentUser
from src.database.core import DbSession
from src.users.models import PatientOnboarding

from .services import get_profile, onboard_user, update_user

router = APIRouter(prefix="/users", tags=["user"])

@router.get("/me")
def read_users_me(user: CurrentUser):
    return {"user": user}

@router.get("/profile")
def get_user_profile(user: CurrentUser, db: DbSession):
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
