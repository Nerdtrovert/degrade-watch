"""
Merchant model for DegradeWatch backend.
"""
import uuid
from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Merchant(Base):
    """Merchant model."""

    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    merchant_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    incidents: Mapped[list["Incident"]] = relationship(
        "Incident",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, merchant_id='{self.merchant_id}')>"