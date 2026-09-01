from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ProducerBase(BaseModel):
    """
    Base producer profile schema.
    """
    document_id: str = Field(
        ...,
        min_length=5,
        max_length=50,
        description="National Identity Document (DUI, NIT)",
        example="01234567-8",
    )
    phone: Optional[str] = Field(
        None,
        max_length=30,
        description="Contact phone number",
        example="+503 7123-4567",
    )
    department: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Department in El Salvador",
        example="Santa Ana",
    )
    municipality: str = Field(
        ...,
        min_length=3,
        max_length=80,
        description="Municipality in El Salvador",
        example="Santa Ana Centro",
    )


class ProducerCreate(ProducerBase):
    """
    Schema for creating a new producer profile for the authenticated user.
    """
    pass


class ProducerUpdate(BaseModel):
    """
    Schema for updating an existing producer profile.
    """
    document_id: Optional[str] = Field(None, min_length=5, max_length=50)
    phone: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, min_length=3, max_length=50)
    municipality: Optional[str] = Field(None, min_length=3, max_length=80)


class ProducerOut(ProducerBase):
    """
    Schema for serialized producer profile output.
    """
    id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
