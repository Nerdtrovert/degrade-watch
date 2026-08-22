"""
AuditEvent service for DegradeWatch backend.
Provides asynchronous database operations for AuditEvent model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.audit_event_repository import AuditEventRepository
from ..models.audit_event import AuditEvent


class AuditEventService:
    """Service for AuditEvent model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = AuditEventRepository(db)

    async def get_by_id(self, event_id: str) -> Optional[AuditEvent]:
        """Get audit event by event_id."""
        return await self.repository.get_by_id(event_id)

    async def get_by_uuid(self, id: str) -> Optional[AuditEvent]:
        """Get audit event by UUID."""
        return await self.repository.get_by_uuid(id)

    async def get_by_incident_id(self, incident_id: str) -> List[AuditEvent]:
        """Get audit events by incident_id."""
        return await self.repository.get_by_incident_id(incident_id)

    async def get_by_recovery_id(self, recovery_id: str) -> List[AuditEvent]:
        """Get audit events by recovery_id."""
        return await self.repository.get_by_recovery_id(recovery_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[AuditEvent]:
        """Get all audit events."""
        return await self.repository.get_all(skip, limit)

    async def create(self, audit_event: AuditEvent) -> AuditEvent:
        """Create a new audit event."""
        return await self.repository.create(audit_event)

    async def update(self, audit_event: AuditEvent) -> AuditEvent:
        """Update an existing audit event."""
        return await self.repository.update(audit_event)

    async def delete(self, audit_event: AuditEvent) -> None:
        """Delete an audit event."""
        await self.repository.delete(audit_event)