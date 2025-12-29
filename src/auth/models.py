from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterUserRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    role: Literal["patient", "doctor", "admin"] = Field(...)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str | None = None

    def get_uuid(self) -> UUID | None:
        if self.user_id:
            return UUID(self.user_id)
        return None
