"""
PolicyDecision model for DegradeWatch backend.
"""
import uuid
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PolicyDecision(Base):
    """PolicyDecision model."""

    __tablename__ = "policy_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., AUTO_APPROVED, HUMAN_APPROVAL, BLOCKED
    reason_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False
    )
    human_readable_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    requested_recovery_action: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # e.g., PAYMENT_LINK, NONE
    policy_inputs: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )
    decision_timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="policy_decision"
    )

    def __repr__(self) -> str:
        return f"<PolicyDecision(id={self.id}, incident_id={self.incident_id}, decision='{self.decision}')>"