from __future__ import annotations

from .models import TriggerRecord
from .service import TriggerService
from .store import TriggerStore


_trigger_store = TriggerStore()
_trigger_service = TriggerService(_trigger_store)


def get_trigger_service() -> TriggerService:
    return _trigger_service


__all__ = [
    "TriggerRecord",
    "TriggerService",
    "get_trigger_service",
]
