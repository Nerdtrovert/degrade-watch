"""
Incident repository for DegradeWatch backend.
Provides asynchronous database operations for Incident model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from ..models.incident import Incident
from ..models.merchant import Merchant


class IncidentRepository:
    """Repository for Incident model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _eager_options(self):
        return [
            selectinload(Incident.evidence_package),
            selectinload(Incident.forensic_report),
            selectinload(Incident.policy_decision),
            selectinload(Incident.recoveries),
            selectinload(Incident.audit_events),
            selectinload(Incident.merchant),
        ]

    async def get_by_id(self, incident_id: str) -> Optional[Incident]:
        """Get incident by incident_id."""
        result = await self.db.execute(
            select(Incident)
            .options(*self._eager_options())
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[Incident]:
        """Get incident by UUID."""
        result = await self.db.execute(
            select(Incident)
            .options(*self._eager_options())
            .filter(Incident.id == id)
        )
        return result.scalars().first()

    async def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get incidents by merchant_id."""
        result = await self.db.execute(
            select(Incident)
            .options(*self._eager_options())
            .join(Incident.merchant)
            .filter(Merchant.merchant_id == merchant_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Incident]:
        """Get all incidents."""
        result = await self.db.execute(
            select(Incident)
            .options(*self._eager_options())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create(self, incident: Incident) -> Incident:
        """Create a new incident."""
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    async def update(self, incident: Incident) -> Incident:
        """Update an existing incident."""
        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    async def delete(self, incident: Incident) -> None:
        """Delete an incident."""
        await self.db.delete(incident)
        await self.db.commit()

    async def get_count_by_merchant_id(self, merchant_id: str) -> int:
        """Get count of incidents by merchant_id."""
        result = await self.db.execute(
            select(func.count(Incident.id))
            .join(Incident.merchant)
            .filter(Merchant.merchant_id == merchant_id)
        )
        return result.scalar() or 0

    async def get_count(self) -> int:
        """Get total count of incidents."""
        result = await self.db.execute(
            select(func.count(Incident.id))
        )
        return result.scalar() or 0

    async def get_merchant_overview_stats(self, merchant_id: str):
        """Get overview statistics for a merchant using SQL aggregations."""
        from sqlalchemy import case, cast, Numeric

        # Query to get aggregations directly from database
        result = await self.db.execute(
            select(
                func.count(Incident.id).label('total_incidents'),
                func.sum(case((Incident.classification == 'INCIDENT', 1), else_=0)).label('active_incidents'),
                func.coalesce(func.sum(
                    case(
                        (
                            Incident.evidence_package.has_value(),
                            Incident.evidence_package['impact_evidence']['revenue_at_risk']['paise'].astext.cast(Numeric)
                        ),
                        else_=0
                    )
                ), 0).label('total_revenue_at_risk_paise'),
                func.avg(
                    case(
                        (
                            Incident.evidence_package.has_value(),
                            Incident.evidence_package['success_rate_evidence']['baseline_success_rate'].astext.cast(Numeric)
                        )
                    )
                ).label('avg_baseline_success_rate'),
                func.avg(
                    case(
                        (
                            Incident.evidence_package.has_value(),
                            Incident.evidence_package['success_rate_evidence']['current_success_rate'].astext.cast(Numeric)
                        )
                    )
                ).label('avg_current_success_rate')
            )
            .select_from(Incident)
            .join(Incident.merchant)
            .filter(Merchant.merchant_id == merchant_id)
        )

        row = result.first()
        if row:
            return {
                'total_incidents': row.total_incidents or 0,
                'active_incidents': row.active_incidents or 0,
                'total_revenue_at_risk_paise': int(row.total_revenue_at_risk_paise or 0),
                'avg_baseline_success_rate': float(row.avg_baseline_success_rate or 0),
                'avg_current_success_rate': float(row.avg_current_success_rate or 0)
            }
        return {
            'total_incidents': 0,
            'active_incidents': 0,
            'total_revenue_at_risk_paise': 0,
            'avg_baseline_success_rate': 0.0,
            'avg_current_success_rate': 0.0
        }

    async def get_recent_incidents(self, merchant_id: str, limit: int = 5):
        """Get recent incidents for a merchant with minimal data for overview."""
        result = await self.db.execute(
            select(Incident)
            .options(
                selectinload(Incident.evidence_package).load_only(
                    Incident.evidence_package['impact_evidence'],
                    Incident.evidence_package['success_rate_evidence']
                )
            )
            .join(Incident.merchant)
            .filter(Merchant.merchant_id == merchant_id)
            .order_by(Incident.detection_timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()