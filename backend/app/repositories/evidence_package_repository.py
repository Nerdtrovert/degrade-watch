"""
EvidencePackage repository for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..models.evidence_package import EvidencePackage


class EvidencePackageRepository:
    """Repository for EvidencePackage model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_incident_id(self, incident_id: str) -> Optional[EvidencePackage]:
        """Get evidence package by incident_id."""
        return self.db.query(EvidencePackage).join(EvidencePackage.incident).filter(
            Incident.incident_id == incident_id
        ).first()

    def get_by_uuid(self, id: str) -> Optional[EvidencePackage]:
        """Get evidence package by UUID."""
        return self.db.query(EvidencePackage).filter(EvidencePackage.id == id).first()

    def create(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Create a new evidence package."""
        self.db.add(evidence_package)
        self.db.commit()
        self.db.refresh(evidence_package)
        return evidence_package

    def update(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Update an existing evidence package."""
        self.db.commit()
        self.db.refresh(evidence_package)
        return evidence_package

    def delete(self, evidence_package: EvidencePackage) -> None:
        """Delete an evidence package."""
        self.db.delete(evidence_package)
        self.db.commit()