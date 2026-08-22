"""
ForensicReport model for DegradeWatch backend.
"""
import uuid
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ForensicReport(Base):
    """ForensicReport model."""

    __tablename__ = "forensic_reports"

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
    report_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., ACTION_REQUIRED, NO_ACTION_REQUIRED
    report: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )  # e.g., groq
    model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )  # e.g., mixtral-8x7b-32768

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="forensic_report"
    )

    def __repr__(self) -> str:
        return f"<ForensicReport(id={self.id}, incident_id={self.incident_id}, status='{self.report_status}')>"