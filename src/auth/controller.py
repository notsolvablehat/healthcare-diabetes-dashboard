from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from src.database.core import DbSession
from src.rate_limiting import limiter

from . import models, services

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=models.Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register_user(request: Request, user_data: models.RegisterUserRequest, db: DbSession):
    return services.register_user(db=db, request=user_data)

@router.post("/login", response_model=models.Token)
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    return services.login_for_token(form_data, db)
