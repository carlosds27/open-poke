from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database.mongodb import MongoDB
from ...logging_config import logger
from ...utils.timezones import resolve_user_timezone
from .models import BookkeepingRecord


class BookkeepingStore:
    """Low-level persistence for bookkeeping records backed by MongoDB."""

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("bookkeeping_records")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for date queries
            self._collection.create_index([("date", -1)])
            # Index for record_type and date queries
            self._collection.create_index([("record_type", 1), ("date", -1)])
            # Index for category queries
            self._collection.create_index([("category", 1)])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "bookkeeping index creation failed",
                extra={"error": str(exc)},
            )

    def insert(self, payload: Dict[str, Any]) -> int:
        """Insert a new bookkeeping record and return its ID."""
        # Dummy implementation - generate next sequential ID
        max_doc = self._collection.find_one(sort=[("id", -1)])
        next_id = 1 if max_doc is None else max_doc.get("id", 0) + 1

        document = {
            "id": next_id,
            **payload,
        }
        self._collection.insert_one(document)
        return next_id

    def fetch_one(self, record_id: int) -> Optional[BookkeepingRecord]:
        """Fetch a single record by ID."""
        document = self._collection.find_one({"id": record_id})
        return self._doc_to_record(document) if document else None

    def update(self, record_id: int, fields: Dict[str, Any]) -> bool:
        """Update a record with the given fields."""
        result = self._collection.update_one(
            {"id": record_id}, {"$set": fields}
        )
        return result.modified_count > 0

    def delete(self, record_id: int) -> bool:
        """Delete a record by ID."""
        result = self._collection.delete_one({"id": record_id})
        return result.deleted_count > 0

    def list_records(
        self,
        record_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
    ) -> List[BookkeepingRecord]:
        """List records with optional filters."""
        query: Dict[str, Any] = {}
        if record_type:
            query["record_type"] = record_type
        if category:
            query["category"] = category
        if start_date or end_date:
            query["date"] = {"$gte": start_date, "$lte": end_date}
        cursor = self._collection.find(query).sort([("date", -1), ("id", -1)])
        return [self._doc_to_record(doc) for doc in cursor]

    def get_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        record_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for a date range."""
        # TODO: Implement this
        return {
            "total_amount": 0.0,
            "record_count": 0,
            "by_category": {},
        }

    def get_cashflow(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Get cashflow (income vs expense) for a date range."""
        # TODO: Implement this
        return {
            "total_income": 0.0,
            "total_expense": 0.0,
            "net_cashflow": 0.0,
            "income_count": 0,
            "expense_count": 0,
        }

    def _doc_to_record(self, doc: Dict[str, Any]) -> BookkeepingRecord:
        data = {k: v for k, v in doc.items() if k != "_id"}
        data["date"] = data["date"].astimezone(resolve_user_timezone()) if data["date"] else None
        data["created_at"] = data["created_at"].astimezone(resolve_user_timezone()) if data["created_at"] else None
        data["updated_at"] = data["updated_at"].astimezone(resolve_user_timezone()) if data["updated_at"] else None
        return BookkeepingRecord.model_validate(data)
