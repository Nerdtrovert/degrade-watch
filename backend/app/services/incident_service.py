"""
Incident service for DegradeWatch backend.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from ..repositories.incident_repository import IncidentRepository
from ..models.incident import Incident


class IncidentService:
    """Service for Incident model."""

    def __init__(self, db: Session):
        self.repository = IncidentRepository(db)

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Get incident by incident_id."""
        return self.repository.get_by_id(incident_id)

    def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get incidents by merchant_id."""
        return self.repository.get_by_merchant_id(merchant_id, skip, limit)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get all incidents."""
        return self.repository.get_all(skip, limit)

    def create(self, incident: Incident) -> Incident:
        """Create a new incident."""
        return self.repository.create(incident)

    def update(self, incident: Incident) -> Incident:
        """Update an existing incident."""
        return self.repository.update(incident)

    def delete(self, incident: Incident) -> None:
        """Delete an incident."""
        self.repository.delete(incident)