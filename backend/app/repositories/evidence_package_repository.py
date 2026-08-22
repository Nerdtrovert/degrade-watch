"""
EvidencePackage repository for DegradeWatch backend.
Provides asynchronous database operations for EvidencePackage model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from ..models.evidence_package import EvidencePackage
from ..models.incident import Incident


class EvidencePackageRepository:
    """Repository for EvidencePackage model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_incident_id(self, incident_id: str) -> Optional[EvidencePackage]:
        """Get evidence package by incident_id."""
        result = await self.db.execute(
            select(EvidencePackage)
            .join(EvidencePackage.incident)
            .options(joinedload(EvidencePackage.incident))
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[EvidencePackage]:
        """Get evidence package by UUID."""
        result = await self.db.execute(
            select(EvidencePackage).filter(EvidencePackage.id == id)
        )
        return result.scalars().first()

    async def create(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Create a new evidence package."""
        self.db.add(evidence_package)
        await self.db.commit()
        await self.db.refresh(evidence_package)
        return evidence_package

    async def update(self, evidence_package: EvidencePackage) -> EvidencePackage:
        """Update an existing evidence package."""
        await self.db.commit()
        await self.db.refresh(evidence_package)
        return evidence_package

    async def delete(self, evidence_package: EvidencePackage) -> None:
        """Delete an evidence package."""
        await self.db.delete(evidence_package)
        await self.db.commit()