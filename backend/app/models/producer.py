import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.user import User


class Producer(Base):
    """
    Producer entity representing registered coffee farmers and cooperative members.
    """
    __tablename__ = "producers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="DUI, NIT or National ID",
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    department: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Salvadoran Department e.g. Santa Ana, Usulután",
    )
    municipality: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="producer",
    )
    farms: Mapped[List["Farm"]] = relationship(
        "Farm",
        back_populates="producer",
        cascade="all, delete-orphan",
        order_by="Farm.name",
    )

    def __repr__(self) -> str:
        return f"<Producer id={self.id} document_id={self.document_id} dept={self.department}>"
