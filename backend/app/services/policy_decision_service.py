"""
PolicyDecision service for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..repositories.policy_decision_repository import PolicyDecisionRepository
from ..models.policy_decision import PolicyDecision


class PolicyDecisionService:
    """Service for PolicyDecision model."""

    def __init__(self, db: Session):
        self.repository = PolicyDecisionRepository(db)

    def get_by_incident_id(self, incident_id: str) -> Optional[PolicyDecision]:
        """Get policy decision by incident_id."""
        return self.repository.get_by_incident_id(incident_id)

    def get_by_uuid(self, id: str) -> Optional[PolicyDecision]:
        """Get policy decision by UUID."""
        return self.repository.get_by_uuid(id)

    def create(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Create a new policy decision."""
        return self.repository.create(policy_decision)

    def update(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Update an existing policy decision."""
        return self.repository.update(policy_decision)

    def delete(self, policy_decision: PolicyDecision) -> None:
        """Delete a policy decision."""
        self.repository.delete(policy_decision)