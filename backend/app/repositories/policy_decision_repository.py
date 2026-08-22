"""
PolicyDecision repository for DegradeWatch backend.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..models.policy_decision import PolicyDecision


class PolicyDecisionRepository:
    """Repository for PolicyDecision model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_incident_id(self, incident_id: str) -> Optional[PolicyDecision]:
        """Get policy decision by incident_id."""
        return self.db.query(PolicyDecision).join(PolicyDecision.incident).filter(
            Incident.incident_id == incident_id
        ).first()

    def get_by_uuid(self, id: str) -> Optional[PolicyDecision]:
        """Get policy decision by UUID."""
        return self.db.query(PolicyDecision).filter(PolicyDecision.id == id).first()

    def create(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Create a new policy decision."""
        self.db.add(policy_decision)
        self.db.commit()
        self.db.refresh(policy_decision)
        return policy_decision

    def update(self, policy_decision: PolicyDecision) -> PolicyDecision:
        """Update an existing policy decision."""
        self.db.commit()
        self.db.refresh(policy_decision)
        return policy_decision

    def delete(self, policy_decision: PolicyDecision) -> None:
        """Delete a policy decision."""
        self.db.delete(policy_decision)
        self.db.commit()