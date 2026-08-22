"""
AuditEvent repository for DegradeWatch backend.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.audit_event import AuditEvent


class AuditEventRepository:
    """Repository for AuditEvent model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, event_id: str) -> Optional[AuditEvent]:
        """Get audit event by event_id."""
        return self.db.query(AuditEvent).filter(AuditEvent.id == event_id).first()

    def get_by_uuid(self, id: str) -> Optional[AuditEvent]:
        """Get audit event by UUID."""
        return self.db.query(AuditEvent).filter(AuditEvent.id == id).first()

    def get_by_incident_id(self, incident_id: str) -> List[AuditEvent]:
        """Get audit events by incident_id."""
        return self.db.query(AuditEvent).join(AuditEvent.incident).filter(
            Incident.incident_id == incident_id
        ).all()

    def get_by_recovery_id(self, recovery_id: str) -> List[AuditEvent]:
        """Get audit events by recovery_id."""
        return self.db.query(AuditEvent).filter(AuditEvent.recovery_id == recovery_id).all()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[AuditEvent]:
        """Get all audit events."""
        return self.db.query(AuditEvent).offset(skip).limit(limit).all()

    def create(self, audit_event: AuditEvent) -> AuditEvent:
        """Create a new audit event."""
        self.db.add(audit_event)
        self.db.commit()
        self.db.refresh(audit_event)
        return audit_event

    def update(self, audit_event: AuditEvent) -> AuditEvent:
        """Update an existing audit event."""
        self.db.commit()
        self.db.refresh(audit_event)
        return audit_event

    def delete(self, audit_event: AuditEvent) -> None:
        """Delete an audit event."""
        self.db.delete(audit_event)
        self.db.commit()