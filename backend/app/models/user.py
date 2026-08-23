"""
User model for DegradeWatch backend.
"""
import uuid
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Foreign key to merchant
    merchant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchants.id"),
        nullable=True
    )

    # Relationships
    merchant: Mapped[Optional["Merchant"]] = relationship(
        "Merchant",
        lazy="joined"
    )

    # For role-based access control, we'll store roles as a comma-separated string
    # or use a separate user_roles table. For simplicity, we'll use a string field.
    roles: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_id='{self.user_id}', email='{self.email}')>"

    @property
    def role_list(self) -> List[str]:
        """Get list of roles."""
        if self.roles:
            return [role.strip() for role in self.roles.split(',')]
        return []

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.role_list