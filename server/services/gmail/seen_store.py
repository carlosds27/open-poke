"""Persistence helper for tracking recently processed Gmail message IDs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from ..database.mongodb import MongoDB
from ...logging_config import logger


class GmailSeenStore:
    """Maintain a bounded set of Gmail message IDs backed by MongoDB."""

    def __init__(self, max_entries: int = 300) -> None:
        self._max_entries = max_entries
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("gmail_seen")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for message_id lookups
            self._collection.create_index([("message_id", 1)], unique=True)
            # Index for timestamp-based ordering and pruning
            self._collection.create_index([("seen_at", 1)])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Gmail seen-store index creation failed",
                extra={"error": str(exc)},
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def has_entries(self) -> bool:
        count = self._collection.count_documents({})
        return count > 0

    def is_seen(self, message_id: str) -> bool:
        normalized = self._normalize(message_id)
        if not normalized:
            return False
        doc = self._collection.find_one({"message_id": normalized})
        return doc is not None

    def mark_seen(self, message_ids: Iterable[str]) -> None:
        normalized_ids = [
            mid for mid in (self._normalize(mid) for mid in message_ids) if mid
        ]
        if not normalized_ids:
            return

        now = datetime.now(timezone.utc)
        for message_id in normalized_ids:
            # Upsert: update seen_at if exists, insert if new
            self._collection.update_one(
                {"message_id": message_id},
                {"$set": {"message_id": message_id, "seen_at": now}},
                upsert=True,
            )

        self._prune()

    def snapshot(self) -> List[str]:
        """Return all message IDs in order of recency (oldest first)."""
        cursor = self._collection.find({}).sort([("seen_at", 1)])
        return [doc["message_id"] for doc in cursor]

    def clear(self) -> None:
        self._collection.delete_many({})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalize(self, message_id: Optional[str]) -> str:
        if not message_id:
            return ""
        return str(message_id).strip()

    def _prune(self) -> None:
        """Remove oldest entries if we exceed max_entries."""
        count = self._collection.count_documents({})
        if count <= self._max_entries:
            return

        # Find the oldest entries to remove
        excess = count - self._max_entries
        oldest_docs = self._collection.find({}).sort([("seen_at", 1)]).limit(excess)
        oldest_ids = [doc["_id"] for doc in oldest_docs]
        if oldest_ids:
            self._collection.delete_many({"_id": {"$in": oldest_ids}})


__all__ = ["GmailSeenStore"]
