import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMBase


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(ORMBase):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
