"""
Recovery repository for DegradeWatch backend.
Provides asynchronous database operations for Recovery model.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload
from ..models.recovery import Recovery
from ..models.incident import Incident
from ..models.merchant import Merchant


class RecoveryRepository:
    """Repository for Recovery model with async database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, recovery_id: str) -> Optional[Recovery]:
        """Get recovery by recovery_id."""
        result = await self.db.execute(
            select(Recovery).filter(Recovery.recovery_id == recovery_id)
        )
        return result.scalars().first()

    async def get_by_uuid(self, id: str) -> Optional[Recovery]:
        """Get recovery by UUID."""
        result = await self.db.execute(
            select(Recovery).filter(Recovery.id == id)
        )
        return result.scalars().first()

    async def get_by_incident_id(self, incident_id: str) -> List[Recovery]:
        """Get recoveries by incident_id."""
        result = await self.db.execute(
            select(Recovery)
            .join(Recovery.incident)
            .options(joinedload(Recovery.incident))
            .filter(Incident.incident_id == incident_id)
        )
        return result.scalars().all()

    async def get_by_merchant_id(self, merchant_id: str, skip: int = 0, limit: int = 100) -> List[Recovery]:
        """Get recoveries by merchant_id."""
        result = await self.db.execute(
            select(Recovery)
            .join(Recovery.incident)
            .join(Incident.merchant)
            .options(
                joinedload(Recovery.incident).joinedload(Incident.merchant)
            )
            .filter(
                Merchant.merchant_id == merchant_id
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Recovery]:
        """Get recovery by idempotency key."""
        result = await self.db.execute(
            select(Recovery).filter(Recovery.idempotency_key == idempotency_key)
        )
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Recovery]:
        """Get all recoveries."""
        result = await self.db.execute(
            select(Recovery).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, recovery: Recovery) -> Recovery:
        """Create a new recovery."""
        self.db.add(recovery)
        await self.db.commit()
        await self.db.refresh(recovery)
        return recovery

    async def update(self, recovery: Recovery) -> Recovery:
        """Update an existing recovery."""
        await self.db.commit()
        await self.db.refresh(recovery)
        return recovery

    async def get_count_by_merchant_id(self, merchant_id: str) -> int:
        """Get count of recoveries by merchant_id."""
        result = await self.db.execute(
            select(func.count(Recovery.id))
            .join(Recovery.incident)
            .join(Incident.merchant)
            .filter(Merchant.merchant_id == merchant_id)
        )
        return result.scalar() or 0

    async def delete(self, recovery: Recovery) -> None:
        """Delete a recovery."""
        await self.db.delete(recovery)
        await self.db.commit()

    async def delete_older_than(self, timestamp) -> int:
        """Delete recoveries created older than given timestamp."""
        result = await self.db.execute(
            select(Recovery).filter(Recovery.created_at < timestamp)
        )
        records = result.scalars().all()
        count = len(records)
        for r in records:
            await self.db.delete(r)
        await self.db.commit()
        return count
        await self.db.commit()