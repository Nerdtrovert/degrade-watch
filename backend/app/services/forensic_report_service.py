"""
ForensicReport service for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..repositories.forensic_report_repository import ForensicReportRepository
from ..models.forensic_report import ForensicReport


class ForensicReportService:
    """Service for ForensicReport model."""

    def __init__(self, db: Session):
        self.repository = ForensicReportRepository(db)

    def get_by_incident_id(self, incident_id: str) -> Optional[ForensicReport]:
        """Get forensic report by incident_id."""
        return self.repository.get_by_incident_id(incident_id)

    def get_by_uuid(self, id: str) -> Optional[ForensicReport]:
        """Get forensic report by UUID."""
        return self.repository.get_by_uuid(id)

    def create(self, forensic_report: ForensicReport) -> ForensicReport:
        """Create a new forensic report."""
        return self.repository.create(forensic_report)

    def update(self, forensic_report: ForensicReport) -> ForensicReport:
        """Update an existing forensic report."""
        return self.repository.update(forensic_report)

    def delete(self, forensic_report: ForensicReport) -> None:
        """Delete a forensic report."""
        self.repository.delete(forensic_report)