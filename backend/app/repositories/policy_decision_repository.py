"""
PolicyDecision repository for DegradeWatch backend.
Provides asynchronous database operations for PolicyDecision model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from ..models.policy_decision import PolicyDecision
from ..models.incident import Incident


class PolicyDecisionRepository:
    """Repository for PolicyDecision model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_incident_id(self, incident_id: str) -> Optional[PolicyDecision]:
        """Get policy decision by incident_id."""
        result = await self.db.execute(
            select(PolicyDecision)
            .join(PolicyDecision.incident)
            .options(joinedload(PolicyDecision.incident))
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[PolicyDecision]:
        """Get policy decision by UUID."""
        result = await self.db.execute(
            select(PolicyDecision).filter(PolicyDecision.id == id)
        )
        return result.scalars().first()

    async def create(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Create a new policy decision."""
        self.db.add(policy_decision)
        await self.db.commit()
        await self.db.refresh(policy_decision)
        return policy_decision

    async def update(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Update an existing policy decision."""
        await self.db.commit()
        await self.db.refresh(policy_decision)
        return policy_decision

    async def delete(self, policy_decision: PolicyDecision) -> None:
        """Delete a policy decision."""
        await self.db.delete(policy_decision)
        await self.db.commit()