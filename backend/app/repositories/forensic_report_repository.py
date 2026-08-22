"""
ForensicReport repository for DegradeWatch backend.
Provides asynchronous database operations for ForensicReport model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from ..models.forensic_report import ForensicReport
from ..models.incident import Incident


class ForensicReportRepository:
    """Repository for ForensicReport model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_incident_id(self, incident_id: str) -> Optional[ForensicReport]:
        """Get forensic report by incident_id."""
        result = await self.db.execute(
            select(ForensicReport)
            .join(ForensicReport.incident)
            .options(joinedload(ForensicReport.incident))
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[ForensicReport]:
        """Get forensic report by UUID."""
        result = await self.db.execute(
            select(ForensicReport).filter(ForensicReport.id == id)
        )
        return result.scalars().first()

    async def create(self, forensic_report: ForensicReport) -> ForensicReport:
        """Create a new forensic report."""
        self.db.add(forensic_report)
        await self.db.commit()
        await self.db.refresh(forensic_report)
        return forensic_report

    async def update(self, forensic_report: ForensicReport) -> ForensicReport:
        """Update an existing forensic report."""
        await self.db.commit()
        await self.db.refresh(forensic_report)
        return forensic_report

    async def delete(self, forensic_report: ForensicReport) -> None:
        """Delete a forensic report."""
        await self.db.delete(forensic_report)
        await self.db.commit()