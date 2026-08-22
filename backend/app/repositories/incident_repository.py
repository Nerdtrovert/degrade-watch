"""
Incident repository for DegradeWatch backend.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.incident import Incident


class IncidentRepository:
    """Repository for Incident model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Get incident by incident_id."""
        return self.db.query(Incident).filter(Incident.incident_id == incident_id).first()

    def get_by_uuid(self, id: str) -> Optional[Incident]:
        """Get incident by UUID."""
        return self.db.query(Incident).filter(Incident.id == id).first()

    def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get incidents by merchant_id."""
        # We need to join with merchant table to filter by merchant_id
        return self.db.query(Incident).join(Incident.merchant).filter(
            Merchant.merchant_id == merchant_id
        ).offset(skip).limit(limit).all()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get all incidents."""
        return self.db.query(Incident).offset(skip).limit(limit).all()

    def create(self, incident: Incident) -> Incident:
        """Create a new incident."""
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update(self, incident: Incident) -> Incident:
        """Update an existing incident."""
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def delete(self, incident: Incident) -> None:
        """Delete an incident."""
        self.db.delete(incident)
        self.db.commit()