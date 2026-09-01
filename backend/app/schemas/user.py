from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleEnum(str, Enum):
    """
    Role definitions for role-based access control.
    """
    ADMIN = "ADMIN"
    PRODUCTOR = "PRODUCTOR"
    TECNICO = "TECNICO"


class UserBase(BaseModel):
    """
    Base user schema with common attributes.
    """
    email: EmailStr = Field(..., description="Unique email address", example="productor@cafetrace.sv")
    full_name: str = Field(..., min_length=2, max_length=150, description="Full legal name", example="Carlos Antonio Ramos")
    role: RoleEnum = Field(default=RoleEnum.PRODUCTOR, description="Assigned user role")
    is_active: bool = Field(default=True, description="Account active status")


class UserCreate(BaseModel):
    """
    Schema for creating a new user.
    """
    email: EmailStr = Field(..., description="Unique email address", example="productor@cafetrace.sv")
    full_name: str = Field(..., min_length=2, max_length=150, description="Full legal name", example="Carlos Antonio Ramos")
    password: str = Field(..., min_length=8, max_length=100, description="Plain text password (min 8 characters)", example="CafeSV2026!Pass")
    role: RoleEnum = Field(default=RoleEnum.PRODUCTOR, description="User role")


class UserUpdate(BaseModel):
    """
    Schema for updating user details.
    """
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserOut(UserBase):
    """
    Schema for serialized user output.
    """
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """
    OAuth2 / JWT Token response schema.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=86400, description="Token lifetime in seconds")


class TokenPayload(BaseModel):
    """
    Decoded JWT token payload schema.
    """
    sub: Optional[str] = None
    role: Optional[str] = None
    iat: Optional[int] = None
    exp: Optional[int] = None
