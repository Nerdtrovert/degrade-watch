"""
Recovery service for DegradeWatch backend.
Provides asynchronous database operations for Recovery model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.recovery_repository import RecoveryRepository
from ..models.recovery import Recovery


class RecoveryService:
    """Service for Recovery model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.repository = RecoveryRepository(db)

    async def get_by_id(self, recovery_id: str) -> Optional[Recovery]:
        """Get recovery by recovery_id."""
        return await self.repository.get_by_id(recovery_id)

    async def get_by_uuid(self, id: str) -> Optional[Recovery]:
        """Get recovery by UUID."""
        return await self.repository.get_by_uuid(id)

    async def get_by_incident_id(self, incident_id: str) -> List[Recovery]:
        """Get recoveries by incident_id."""
        return await self.repository.get_by_incident_id(incident_id)

    async def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Recovery]:
        """Get recoveries by merchant_id."""
        return await self.repository.get_by_merchant_id(merchant_id, skip, limit)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Recovery]:
        """Get recovery by idempotency key."""
        return await self.repository.get_by_idempotency_key(idempotency_key)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Recovery]:
        """Get all recoveries."""
        return await self.repository.get_all(skip, limit)

    async def create(self, recovery: Recovery) -> Recovery:
        """Create a new recovery."""
        return await self.repository.create(recovery)

    async def update(self, recovery: Recovery) -> Recovery:
        """Update an existing recovery."""
        return await self.repository.update(recovery)

    async def delete(self, recovery: Recovery) -> None:
        """Delete a recovery."""
        await self.repository.delete(recovery)

    async def get_count_by_merchant_id(self, merchant_id: str) -> int:
        """Get count of recoveries by merchant_id."""
        return await self.repository.get_count_by_merchant_id(merchant_id)