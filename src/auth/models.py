from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterUserRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    role: Literal["patient", "doctor", "admin"] = Field(...)

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    is_onboarded: bool

class TokenData(BaseModel):
    user_id: str | None = None
    role: str | None = None
    is_onboarded: bool | None = None
