"""
AuditEvent repository for DegradeWatch backend.
Provides asynchronous database operations for AuditEvent model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from ..models.audit_event import AuditEvent
from ..models.incident import Incident
from ..models.recovery import Recovery


class AuditEventRepository:
    """Repository for AuditEvent model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, event_id: str) -> Optional[AuditEvent]:
        """Get audit event by event_id."""
        result = await self.db.execute(
            select(AuditEvent)
            .options(joinedload(AuditEvent.incident), joinedload(AuditEvent.recovery))
            .filter(AuditEvent.id == event_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[AuditEvent]:
        """Get audit event by UUID."""
        result = await self.db.execute(
            select(AuditEvent)
            .options(joinedload(AuditEvent.incident), joinedload(AuditEvent.recovery))
            .filter(AuditEvent.id == id)
        )
        return result.scalars().first()

    async def get_by_incident_id(self, incident_id: str) -> List[AuditEvent]:
        """Get audit events by incident_id."""
        result = await self.db.execute(
            select(AuditEvent)
            .join(AuditEvent.incident)
            .options(joinedload(AuditEvent.incident), joinedload(AuditEvent.recovery))
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().all()

    async def get_by_recovery_id(self, recovery_id: str) -> List[AuditEvent]:
        """Get audit events by recovery_id."""
        result = await self.db.execute(
            select(AuditEvent)
            .options(joinedload(AuditEvent.incident), joinedload(AuditEvent.recovery))
            .filter(AuditEvent.recovery_id == recovery_id)
        )
        return result.scalars().all()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[AuditEvent]:
        """Get all audit events."""
        result = await self.db.execute(
            select(AuditEvent)
            .options(joinedload(AuditEvent.incident), joinedload(AuditEvent.recovery))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create(self, audit_event: AuditEvent) -> AuditEvent:
        """Create a new audit event."""
        self.db.add(audit_event)
        await self.db.commit()
        await self.db.refresh(audit_event)
        return audit_event

    async def update(self, audit_event: AuditEvent) -> AuditEvent:
        """Update an existing audit event."""
        await self.db.commit()
        await self.db.refresh(audit_event)
        return audit_event

    async def delete(self, audit_event: AuditEvent) -> None:
        """Delete an audit event."""
        await self.db.delete(audit_event)
        await self.db.commit()