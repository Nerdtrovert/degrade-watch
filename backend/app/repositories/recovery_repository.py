"""
Recovery repository for DegradeWatch backend.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.recovery import Recovery


class RecoveryRepository:
    """Repository for Recovery model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, recovery_id: str) -> Optional[Recovery]:
        """Get recovery by recovery_id."""
        return self.db.query(Recovery).filter(Recovery.recovery_id == recovery_id).first()

    def get_by_uuid(self, id: str) -> Optional[Recovery]:
        """Get recovery by UUID."""
        return self.db.query(Recovery).filter(Recovery.id == id).first()

    def get_by_incident_id(self, incident_id: str) -> List[Recovery]:
        """Get recoveries by incident_id."""
        return self.db.query(Recovery).join(Recovery.incident).filter(
            Incident.incident_id == incident_id
        ).all()

    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Recovery]:
        """Get recovery by idempotency key."""
        return self.db.query(Recovery).filter(Recovery.idempotency_key == idempotency_key).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Recovery]:
        """Get all recoveries."""
        return self.db.query(Recovery).offset(skip).limit(limit).all()

    def create(self, recovery: Recovery) -> Recovery:
        """Create a new recovery."""
        self.db.add(recovery)
        self.db.commit()
        self.db.refresh(recovery)
        return recovery

    def update(self, recovery: Recovery) -> Recovery:
        """Update an existing recovery."""
        self.db.commit()
        self.db.refresh(recovery)
        return recovery

    def delete(self, recovery: Recovery) -> None:
        """Delete a recovery."""
        self.db.delete(recovery)
        self.db.commit()