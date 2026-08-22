"""
AuditEvent model for DegradeWatch backend.
"""
import uuid
from typing import Optional
from sqlalchemy import DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AuditEvent(Base):
    """AuditEvent model."""

    __tablename__ = "audit_events"

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
    recovery_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recoveries.id"),
        nullable=True,
        index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )  # e.g., INCIDENT_CREATED, EVIDENCE_GENERATED, POLICY_EVALUATED, RECOVERY_REQUESTED, etc.
    timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    actor: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )  # e.g., system, recovery_engine, policy_engine
    outcome: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # e.g., SUCCESS, FAILED
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="audit_events"
    )
    recovery: Mapped[Optional["Recovery"]] = relationship(
        "Recovery",
        back_populates="audit_events"
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, incident_id={self.incident_id}, event_type='{self.event_type}', timestamp='{self.timestamp}')>"