"""
Incident model for DegradeWatch backend.
"""
import uuid
from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Incident(Base):
    """Incident model."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    incident_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    classification: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., INCIDENT, NORMAL
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # e.g., LOW, MEDIUM, HIGH
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., OPEN, INVESTIGATING, RESOLVED, IGNORED (we'll set to classification for now)
    affected_segment: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    detection_timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(
        "Merchant",
        back_populates="incidents"
    )
    evidence_package: Mapped["EvidencePackage"] = relationship(
        "EvidencePackage",
        uselist=False,
        back_populates="incident",
        cascade="all, delete-orphan"
    )
    forensic_report: Mapped["ForensicReport"] = relationship(
        "ForensicReport",
        uselist=False,
        back_populates="incident",
        cascade="all, delete-orphan"
    )
    policy_decision: Mapped["PolicyDecision"] = relationship(
        "PolicyDecision",
        uselist=False,
        back_populates="incident",
        cascade="all, delete-orphan"
    )
    recoveries: Mapped[list["Recovery"]] = relationship(
        "Recovery",
        back_populates="incident",
        cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="incident",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Incident(id={self.id}, incident_id='{self.incident_id}', classification='{self.classification}')>"