"""
EvidencePackage model for DegradeWatch backend.
"""
import uuid
from typing import Optional
from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class EvidencePackage(Base):
    """EvidencePackage model."""

    __tablename__ = "evidence_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id"),
        nullable=False,
        index=True
    )
    schema_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    evidence_package: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="evidence_package"
    )

    def __repr__(self) -> str:
        return f"<EvidencePackage(id={self.id}, incident_id={self.incident_id})>"