import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.schemas.users.users import User

from . import models

load_dotenv()

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/login")
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET: str | None = os.getenv("JWT_SECRET")
SECRET_ALGORITHM: str | None = os.getenv("SECRET_ALGORITHM")
ACCESS_TOKEN_EXPIRATION_MIN = 1440

# Security Logic Start
def generate_password_hash(password: str) -> str:
    return bcrypt_context.hash(password)

def verify_password(plain_pass: str, pass_hash: str) -> bool:
    return bcrypt_context.verify(plain_pass, pass_hash)

def create_access_token(email: str, user_id: UUID, expires_delta: timedelta) -> str:
    if not JWT_SECRET or not SECRET_ALGORITHM:
        raise RuntimeError("Secrets have not been configured correctly.")

    payload = {
        "sub": email,
        "id": str(user_id),
        "exp": datetime.now(timezone.utc) + expires_delta
    }

    return jwt.encode(payload, key=JWT_SECRET, algorithm=SECRET_ALGORITHM)

def verify_token(token: str) -> models.TokenData:
    if not JWT_SECRET or not SECRET_ALGORITHM:
        raise RuntimeError("Secrets have not been configured correctly.")

    try:
        payload = jwt.decode(token, key=JWT_SECRET, algorithms=[SECRET_ALGORITHM])
        user_id: str = payload.get("id")
        return models.TokenData(user_id=user_id)
    except Exception as e:
        logging.warning(f"Token verification failed {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e

def authenticate_user(username: str, password: str, db: Session) -> User | bool:
    user = db.query(User).filter(
            or_(
                User.username == username,
                User.email == username
            )
        ).first()
    if not user or not verify_password(password, str(user.hashed_pass)):
        logging.warning(f"Failed to authenticate user for email: {username}")
        return False
    return user
# Security Logic End

# Business Logic Start
def register_user(db: Session, request: models.RegisterUserRequest) -> None:
    try:
        pass_hash = generate_password_hash(request.password)
        create_user_model = User(
            id=uuid4(),
            email=request.email,
            username=request.username,
            hashed_pass=pass_hash,
            role=request.role if request.role else "patient",
            is_onboarded=False,
            created_at=date.today()
        )

        db.add(create_user_model)
        db.commit()
    except Exception:
        logging.error("Failed to create an user.")
        raise

def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]) -> models.TokenData:
    return verify_token(token)

CurrentUser = Annotated[models.TokenData, Depends(get_current_user)]

def login_for_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session) -> models.Token:
    if not ACCESS_TOKEN_EXPIRATION_MIN:
        logging.error("Secrets have not been configured")
        raise

    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")

    token = create_access_token(user.email, user.id, timedelta(minutes=ACCESS_TOKEN_EXPIRATION_MIN)) # type: ignore
    return models.Token(access_token=token, token_type="bearer")

# Business Logic End
