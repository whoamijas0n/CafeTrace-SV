import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm


class Plot(Base):
    """
    Plot (Parcela / Tablón) entity containing spatial PostGIS polygon geometry and coffee variety.
    """
    __tablename__ = "plots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Plot or Tablon name, e.g. Tablon Los Cedros",
    )
    coffee_variety: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
        comment="Coffee variety: Bourbon, Pacamara, Cuscatleco, Pacas, Geisha",
    )
    area_hectares: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Calculated area in hectares using PostGIS ST_Area(geography)",
    )
    # PostGIS Polygon Geometry (SRID 4326 - WGS84)
    geometry: Mapped[Any] = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    farm: Mapped["Farm"] = relationship(
        "Farm",
        back_populates="plots",
    )

    def __repr__(self) -> str:
        return f"<Plot id={self.id} name={self.name} variety={self.coffee_variety} area_ha={self.area_hectares}>"
