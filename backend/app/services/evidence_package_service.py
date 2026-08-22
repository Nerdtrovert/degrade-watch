"""
EvidencePackage service for DegradeWatch backend.
Provides asynchronous database operations for EvidencePackage model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.evidence_package_repository import EvidencePackageRepository
from ..models.evidence_package import EvidencePackage


class EvidencePackageService:
    """Service for EvidencePackage model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = EvidencePackageRepository(db)

    async def get_by_incident_id(self, incident_id: str) -> Optional[EvidencePackage]:
        """Get evidence package by incident_id."""
        return await self.repository.get_by_incident_id(incident_id)

    async def get_by_uuid(self, id: str) -> Optional[EvidencePackage]:
        """Get evidence package by UUID."""
        return await self.repository.get_by_uuid(id)

    async def create(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Create a new evidence package."""
        return await self.repository.create(evidence_package)

    async def update(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Update an existing evidence package."""
        return await self.repository.update(evidence_package)

    async def delete(self, evidence_package: EvidencePackage) -> None:
        """Delete an evidence package."""
        await self.repository.delete(evidence_package)