from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ...logging_config import logger
from ...utils.timezones import now_in_user_timezone
from .models import BookkeepingRecord
from .store import BookkeepingStore


class BookkeepingService:
    """High-level bookkeeping management."""

    def __init__(self, store: BookkeepingStore):
        self._store = store

    def create_record(
        self,
        *,
        record_type: str,
        amount: float,
        category: str,
        description: Optional[str] = None,
        date_time: Optional[datetime] = None,
    ) -> BookkeepingRecord:
        """Create a new bookkeeping record (income or expense).
        
        The date_time parameter is interpreted in the user's timezone.
        """
        if record_type not in ["income", "expense"]:
            raise ValueError("record_type must be 'income' or 'expense'")
        
        if amount <= 0:
            raise ValueError("amount must be positive")
        
        now = now_in_user_timezone()
        record_date_time = date_time if date_time else now
        
        record: Dict[str, Any] = {
            "record_type": record_type,
            "amount": float(amount),
            "category": category,
            "description": description,
            "date_time": record_date_time,
            "created_at": now,
            "updated_at": now,
        }
        record_id = self._store.insert(record)
        created = self._store.fetch_one(record_id)
        if not created:  # pragma: no cover - defensive
            raise RuntimeError("Failed to load record after insert")
        return created

    def update_record(
        self,
        record_id: int,
        *,
        record_type: Optional[str] = None,
        amount: Optional[float] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        date_time: Optional[datetime] = None,
    ) -> Optional[BookkeepingRecord]:
        """Update an existing bookkeeping record.
        
        The date_time parameter is interpreted in the user's timezone.
        """
        existing = self._store.fetch_one(record_id)
        if existing is None:
            return None

        if record_type and record_type not in ["income", "expense"]:
            raise ValueError("record_type must be 'income' or 'expense'")
        
        if amount is not None and amount <= 0:
            raise ValueError("amount must be positive")

        fields: Dict[str, Any] = {}
        if record_type is not None:
            fields["record_type"] = record_type
        if amount is not None:
            fields["amount"] = float(amount)
        if category is not None:
            fields["category"] = category
        if description is not None:
            fields["description"] = description
        if date_time is not None:
            fields["date_time"] = date_time

        if not fields:
            return existing

        fields["updated_at"] = now_in_user_timezone()
        updated = self._store.update(record_id, fields)
        return self._store.fetch_one(record_id) if updated else existing

    def delete_record(self, record_id: int) -> bool:
        """Delete a bookkeeping record."""
        return self._store.delete(record_id)

    def clear_all(self) -> None:
        """Clear all bookkeeping records."""
        self._store.clear_all()

    def list_records(
        self,
        *,
        record_type: Optional[str] = None,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
        category: Optional[str] = None,
    ) -> List[BookkeepingRecord]:
        """List bookkeeping records with optional filters.
        
        Date filters are interpreted in the user's timezone.
        """
        return self._store.list_records(
            record_type=record_type,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            category=category,
        )

    def get_expense_summary(
        self,
        *,
        start_date_time: datetime,
        end_date_time: datetime,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get summary of expenses for a date range."""
        return self._store.get_summary(
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            record_type="expense",
            category=category,
        )

    def get_cashflow(
        self,
        *,
        start_date_time: datetime,
        end_date_time: datetime,
    ) -> Dict[str, Any]:
        """Get cashflow (income vs expense) for a date range."""
        return self._store.get_cashflow(
            start_date_time=start_date_time,
            end_date_time=end_date_time,
        )


__all__ = ["BookkeepingService"]

