"""
EvidencePackage service for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..repositories.evidence_package_repository import EvidencePackageRepository
from ..models.evidence_package import EvidencePackage


class EvidencePackageService:
    """Service for EvidencePackage model."""

    def __init__(self, db: Session):
        self.repository = EvidencePackageRepository(db)

    def get_by_incident_id(self, incident_id: str) -> Optional[EvidencePackage]:
        """Get evidence package by incident_id."""
        return self.repository.get_by_incident_id(incident_id)

    def get_by_uuid(self, id: str) -> Optional[EvidencePackage]:
        """Get evidence package by UUID."""
        return self.repository.get_by_uuid(id)

    def create(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Create a new evidence package."""
        return self.repository.create(evidence_package)

    def update(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Update an existing evidence package."""
        return self.repository.update(evidence_package)

    def delete(self, evidence_package: EvidencePackage) -> None:
        """Delete an evidence package."""
        self.repository.delete(evidence_package)