from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BookkeepingRecord(BaseModel):
    """Serialized bookkeeping record representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    record_type: str  # "income" or "expense"
    amount: float
    category: str  # e.g., "food", "grocery", "gift", "salary", etc.
    description: Optional[str] = None
    date_time: datetime
    created_at: datetime
    updated_at: datetime


__all__ = ["BookkeepingRecord"]

