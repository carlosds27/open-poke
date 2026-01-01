from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TriggerRecord(BaseModel):
    """Serialized trigger representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    payload: str
    start_time: Optional[datetime] = None
    next_trigger: Optional[datetime] = None
    recurrence_rule: Optional[str] = None
    timezone: Optional[str] = None
    status: str
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


__all__ = ["TriggerRecord"]
