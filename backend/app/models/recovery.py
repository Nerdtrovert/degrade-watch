"""
Recovery model for DegradeWatch backend.
"""
import uuid
from typing import Optional
from sqlalchemy import DateTime, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Recovery(Base):
    """Recovery model."""

    __tablename__ = "recoveries"

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
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., PAYMENT_LINK, NONE
    amount_paise: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )  # Amount requested for recovery
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )  # e.g., INR
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED, NOT_AUTHORIZED
    razorpay_payment_link_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    razorpay_payment_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # e.g., created, paid, etc.
    recovered_amount_paise: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )  # Amount actually recovered from Razorpay
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True
    )  # To ensure idempotency of recovery requests
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="recoveries"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="recovery"
    )

    def __repr__(self) -> str:
        return f"<Recovery(id={self.id}, incident_id={self.incident_id}, state='{self.state}')>"