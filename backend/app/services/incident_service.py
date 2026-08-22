"""
Incident service for DegradeWatch backend.
Provides asynchronous database operations for Incident model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..repositories.incident_repository import IncidentRepository
from ..models.incident import Incident


class IncidentService:
    """Service for Incident model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = IncidentRepository(db)

    async def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Get incident by incident_id."""
        return await self.repository.get_by_id(incident_id)

    async def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get incidents by merchant_id."""
        return await self.repository.get_by_merchant_id(merchant_id, skip, limit)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get all incidents."""
        return await self.repository.get_all(skip, limit)

    async def create(self, incident: Incident) -> Incident:
        """Create a new incident."""
        return await self.repository.create(incident)

    async def update(self, incident: Incident) -> Incident:
        """Update an existing incident."""
        return await self.repository.update(incident)

    async def delete(self, incident: Incident) -> None:
        """Delete an incident."""
        await self.repository.delete(incident)

    async def get_count_by_merchant_id(self, merchant_id: str) -> int:
        """Get count of incidents by merchant_id."""
        return await self.repository.get_count_by_merchant_id(merchant_id)

    async def get_count(self) -> int:
        """Get total count of incidents."""
        return await self.repository.get_count()

    async def get_merchant_overview_stats(self, merchant_id: str):
        """Get overview statistics for a merchant."""
        return await self.repository.get_merchant_overview_stats(merchant_id)

    async def get_recent_incidents(self, merchant_id: str, limit: int = 5):
        """Get recent incidents for a merchant."""
        return await self.repository.get_recent_incidents(merchant_id, limit)