import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.plot import Plot
    from app.models.producer import Producer


class Farm(Base):
    """
    Farm (Finca) entity representing agricultural properties.
    """
    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    producer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("producers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    department: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    municipality: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )
    canton_village: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )
    altitude_masl: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Meters above sea level (msnm)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    producer: Mapped["Producer"] = relationship(
        "Producer",
        back_populates="farms",
    )
    plots: Mapped[List["Plot"]] = relationship(
        "Plot",
        back_populates="farm",
        cascade="all, delete-orphan",
        order_by="Plot.name",
    )

    def __repr__(self) -> str:
        return f"<Farm id={self.id} name={self.name} altitude={self.altitude_masl}msnm>"
