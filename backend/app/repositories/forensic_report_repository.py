"""
ForensicReport repository for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..models.forensic_report import ForensicReport


class ForensicReportRepository:
    """Repository for ForensicReport model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_incident_id(self, incident_id: str) -> Optional[ForensicReport]:
        """Get forensic report by incident_id."""
        return self.db.query(ForensicReport).join(ForensicReport.incident).filter(
            Incident.incident_id == incident_id
        ).first()

    def get_by_uuid(self, id: str) -> Optional[ForensicReport]:
        """Get forensic report by UUID."""
        return self.db.query(ForensicReport).filter(ForensicReport.id == id).first()

    def create(self, forensic_report: ForensicReport) -> ForensicReport:
        """Create a new forensic report."""
        self.db.add(forensic_report)
        self.db.commit()
        self.db.refresh(forensic_report)
        return forensic_report

    def update(self, forensic_report: ForensicReport) -> ForensicReport:
        """Update an existing forensic report."""
        self.db.commit()
        self.db.refresh(forensic_report)
        return forensic_report

    def delete(self, forensic_report: ForensicReport) -> None:
        """Delete a forensic report."""
        self.db.delete(forensic_report)
        self.db.commit()