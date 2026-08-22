"""
ForensicReport service for DegradeWatch backend.
Provides asynchronous database operations for ForensicReport model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.forensic_report_repository import ForensicReportRepository
from ..models.forensic_report import ForensicReport


class ForensicReportService:
    """Service for ForensicReport model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = ForensicReportRepository(db)

    async def get_by_incident_id(self, incident_id: str) -> Optional[ForensicReport]:
        """Get forensic report by incident_id."""
        return await self.repository.get_by_incident_id(incident_id)

    async def get_by_uuid(self, id: str) -> Optional[ForensicReport]:
        """Get forensic report by UUID."""
        return await self.repository.get_by_uuid(id)

    async def create(self, forensic_report: ForensicReport) -> ForensicReport:
        """Create a new forensic report."""
        return await self.repository.create(forensic_report)

    async def update(self, forensic_report: ForensicReport) -> ForensicReport:
        """Update an existing forensic report."""
        return await self.repository.update(forensic_report)

    async def delete(self, forensic_report: ForensicReport) -> None:
        """Delete a forensic report."""
        await self.repository.delete(forensic_report)