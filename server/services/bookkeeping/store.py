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
            self._collection.create_index([("date_time", -1)])
            # Index for record_type and date queries
            self._collection.create_index([("record_type", 1), ("date_time", -1)])
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

    def clear_all(self) -> None:
        """Clear all bookkeeping records."""
        self._collection.delete_many({})

    def list_records(
        self,
        record_type: Optional[str] = None,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
        category: Optional[str] = None,
    ) -> List[BookkeepingRecord]:
        """List records with optional filters."""
        query: Dict[str, Any] = {}
        if record_type:
            query["record_type"] = record_type
        if category:
            query["category"] = category
        if start_date_time or end_date_time:
            query["date_time"] = {"$gte": start_date_time, "$lte": end_date_time}
        cursor = self._collection.find(query).sort([("date_time", -1), ("id", -1)])
        return [self._doc_to_record(doc) for doc in cursor]

    def get_summary(
        self,
        start_date_time: datetime,
        end_date_time: datetime,
        record_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for a date range."""
        # Build match stage
        match_conditions: Dict[str, Any] = {
            "date_time": {"$gte": start_date_time, "$lte": end_date_time}
        }
        if record_type:
            match_conditions["record_type"] = record_type
        if category:
            match_conditions["category"] = category

        # Aggregation pipeline: use facet to get both overall stats and category breakdown
        pipeline = [
            {"$match": match_conditions},
            {
                "$facet": {
                    "overall": [
                        {
                            "$group": {
                                "_id": None,
                                "total_amount": {"$sum": "$amount"},
                                "record_count": {"$sum": 1},
                            }
                        }
                    ],
                    "by_category": [
                        {
                            "$group": {
                                "_id": "$category",
                                "total_amount": {"$sum": "$amount"},
                                "record_count": {"$sum": 1},
                            }
                        }
                    ],
                }
            },
        ]

        result = list(self._collection.aggregate(pipeline))
        
        if not result or not result[0].get("overall"):
            return {
                "total_amount": 0.0,
                "record_count": 0,
                "by_category": {},
            }

        overall = result[0]["overall"][0]
        category_data = result[0]["by_category"]

        # Build by_category dictionary
        by_category: Dict[str, Dict[str, Any]] = {}
        for item in category_data:
            cat = item["_id"]
            by_category[cat] = {
                "total_amount": item.get("total_amount", 0.0),
                "record_count": item.get("record_count", 0),
            }

        return {
            "total_amount": overall.get("total_amount", 0.0),
            "record_count": overall.get("record_count", 0),
            "by_category": by_category,
        }

    def get_cashflow(
        self,
        start_date_time: datetime,
        end_date_time: datetime,
    ) -> Dict[str, Any]:
        """Get cashflow (income vs expense) for a date range."""
        # Aggregation pipeline
        pipeline = [
            {
                "$match": {
                    "date_time": {"$gte": start_date_time, "$lte": end_date_time}
                }
            },
            {
                "$group": {
                    "_id": "$record_type",
                    "total_amount": {"$sum": "$amount"},
                    "record_count": {"$sum": 1},
                }
            },
        ]

        result = list(self._collection.aggregate(pipeline))
        
        # Initialize defaults
        total_income = 0.0
        total_expense = 0.0
        income_count = 0
        expense_count = 0

        # Process results
        for item in result:
            record_type = item.get("_id")
            amount = item.get("total_amount", 0.0)
            count = item.get("record_count", 0)
            
            if record_type == "income":
                total_income = amount
                income_count = count
            elif record_type == "expense":
                total_expense = amount
                expense_count = count

        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_cashflow": total_income - total_expense,
            "income_count": income_count,
            "expense_count": expense_count,
        }

    def _doc_to_record(self, doc: Dict[str, Any]) -> BookkeepingRecord:
        data = {k: v for k, v in doc.items() if k != "_id"}
        data["date_time"] = data["date_time"].astimezone(resolve_user_timezone()) if data["date_time"] else None
        data["created_at"] = data["created_at"].astimezone(resolve_user_timezone()) if data["created_at"] else None
        data["updated_at"] = data["updated_at"].astimezone(resolve_user_timezone()) if data["updated_at"] else None
        return BookkeepingRecord.model_validate(data)
