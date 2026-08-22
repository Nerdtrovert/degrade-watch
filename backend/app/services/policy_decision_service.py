"""
PolicyDecision service for DegradeWatch backend.
Provides asynchronous database operations for PolicyDecision model.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.policy_decision_repository import PolicyDecisionRepository
from ..models.policy_decision import PolicyDecision


class PolicyDecisionService:
    """Service for PolicyDecision model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = PolicyDecisionRepository(db)

    async def get_by_incident_id(self, incident_id: str) -> Optional[PolicyDecision]:
        """Get policy decision by incident_id."""
        return await self.repository.get_by_incident_id(incident_id)

    async def get_by_uuid(self, id: str) -> Optional[PolicyDecision]:
        """Get policy decision by UUID."""
        return await self.repository.get_by_uuid(id)

    async def create(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Create a new policy decision."""
        return await self.repository.create(policy_decision)

    async def update(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Update an existing policy decision."""
        return await self.repository.update(policy_decision)

    async def delete(self, policy_decision: PolicyDecision) -> None:
        """Delete a policy decision."""
        await self.repository.delete(policy_decision)