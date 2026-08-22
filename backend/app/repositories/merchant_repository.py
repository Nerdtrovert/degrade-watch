"""
Merchant repository for DegradeWatch backend.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.merchant import Merchant


class MerchantRepository:
    """Repository for Merchant model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, merchant_id: str) -> Optional[Merchant]:
        """Get merchant by merchant_id."""
        return self.db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()

    def get_by_uuid(self, id: str) -> Optional[Merchant]:
        """Get merchant by UUID."""
        return self.db.query(Merchant).filter(Merchant.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Merchant]:
        """Get all merchants."""
        return self.db.query(Merchant).offset(skip).limit(limit).all()

    def create(self, merchant: Merchant) -> Merchant:
        """Create a new merchant."""
        self.db.add(merchant)
        self.db.commit()
        self.db.refresh(merchant)
        return merchant

    def update(self, merchant: Merchant) -> Merchant:
        """Update an existing merchant."""
        self.db.commit()
        self.db.refresh(merchant)
        return merchant

    def delete(self, merchant: Merchant) -> None:
        """Delete a merchant."""
        self.db.delete(merchant)
        self.db.commit()