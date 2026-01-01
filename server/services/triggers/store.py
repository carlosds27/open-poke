from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..database.mongodb import MongoDB
from ...logging_config import logger
from ...utils.timezones import resolve_user_timezone
from .models import TriggerRecord


class TriggerStore:
    """Low-level persistence for triggers backed by MongoDB."""

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("triggers")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for agent_name and next_trigger queries
            self._collection.create_index([("agent_name", 1), ("next_trigger", 1)])
            # Index for status and next_trigger queries (for fetch_due)
            self._collection.create_index([("status", 1), ("next_trigger", 1)])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "trigger index creation failed",
                extra={"error": str(exc)},
            )

    def insert(self, payload: Dict[str, Any]) -> int:
        # Generate next sequential ID
        max_doc = self._collection.find_one(sort=[("id", -1)])
        next_id = 1 if max_doc is None else max_doc.get("id", 0) + 1

        document = {
            "id": next_id,
            **payload,
        }
        self._collection.insert_one(document)
        return next_id

    def fetch_one(self, trigger_id: int, agent_name: str) -> Optional[TriggerRecord]:
        document = self._collection.find_one(
            {"id": trigger_id, "agent_name": agent_name}
        )
        return self._doc_to_record(document) if document else None

    def update(self, trigger_id: int, agent_name: str, fields: Dict[str, Any]) -> bool:
        if not fields:
            return False
        update_fields = {
            **fields,
            "updated_at": datetime.now(timezone.utc),
        }
        result = self._collection.update_one(
            {"id": trigger_id, "agent_name": agent_name}, {"$set": update_fields}
        )
        return result.modified_count > 0

    def list_for_agent(self, agent_name: str) -> List[TriggerRecord]:
        # Sort: nulls last, then by next_trigger ascending
        cursor = self._collection.find({"agent_name": agent_name}).sort(
            [("next_trigger", 1)]  # MongoDB sorts nulls last by default
        )
        return [self._doc_to_record(doc) for doc in cursor]

    def fetch_due(
        self, agent_name: Optional[str], before: datetime
    ) -> List[TriggerRecord]:
        # Convert datetime to UTC string for query
        before_utc = before.astimezone(timezone.utc)
        query: Dict[str, Any] = {
            "status": "active",
            "next_trigger": {"$ne": None, "$lte": before_utc},
        }
        if agent_name:
            query["agent_name"] = agent_name

        cursor = self._collection.find(query).sort([("next_trigger", 1), ("id", 1)])
        return [self._doc_to_record(doc) for doc in cursor]

    def clear_all(self) -> None:
        self._collection.delete_many({})

    def _doc_to_record(self, doc: Dict[str, Any]) -> TriggerRecord:
        # Remove MongoDB's _id field if present, keep our id field
        data = {k: v for k, v in doc.items() if k != "_id"}
        data["start_time"] = data["start_time"].astimezone(resolve_user_timezone()) if data["start_time"] else None
        data["next_trigger"] = data["next_trigger"].astimezone(resolve_user_timezone()) if data["next_trigger"] else None
        data["created_at"] = data["created_at"].astimezone(resolve_user_timezone()) if data["created_at"] else None
        data["updated_at"] = data["updated_at"].astimezone(resolve_user_timezone()) if data["updated_at"] else None
        return TriggerRecord.model_validate(data)


__all__ = ["TriggerStore"]
