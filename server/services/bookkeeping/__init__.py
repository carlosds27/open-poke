from __future__ import annotations

from .models import BookkeepingRecord
from .service import BookkeepingService
from .store import BookkeepingStore


_bookkeeping_store = BookkeepingStore()
_bookkeeping_service = BookkeepingService(_bookkeeping_store)


def get_bookkeeping_service() -> BookkeepingService:
    return _bookkeeping_service


__all__ = [
    "BookkeepingRecord",
    "BookkeepingService",
    "BookkeepingStore",
    "get_bookkeeping_service",
]

