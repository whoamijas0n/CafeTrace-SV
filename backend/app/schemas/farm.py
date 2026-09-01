from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class FarmBase(BaseModel):
    """
    Base farm (finca) schema.
    """
    name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Farm name",
        example="Finca La Esperanza",
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
        example="Chalchuapa",
    )
    canton_village: Optional[str] = Field(
        None,
        max_length=120,
        description="Canton or village (Caserío / Cantón)",
        example="Cantón El Porvenir",
    )
    altitude_masl: Optional[int] = Field(
        None,
        ge=400,
        le=2800,
        description="Altitude in meters above sea level (msnm)",
        example=1350,
    )


class FarmCreate(FarmBase):
    """
    Schema for registering a new farm under the producer's profile.
    """
    pass


class FarmUpdate(BaseModel):
    """
    Schema for updating farm details.
    """
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    department: Optional[str] = Field(None, min_length=3, max_length=50)
    municipality: Optional[str] = Field(None, min_length=3, max_length=80)
    canton_village: Optional[str] = Field(None, max_length=120)
    altitude_masl: Optional[int] = Field(None, ge=400, le=2800)


class FarmOut(FarmBase):
    """
    Schema for serialized farm output.
    """
    id: UUID
    producer_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FarmWithPlotsCountOut(FarmOut):
    """
    Extended farm schema including aggregate spatial information.
    """
    plots_count: int = Field(default=0, description="Total number of georeferenced plots")
    total_area_hectares: float = Field(default=0.0, description="Total surface area in hectares")
