"""Persist and expose the user's preferred timezone."""

from __future__ import annotations

from typing import Optional

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .database.mongodb import MongoDB
from ..logging_config import logger


class TimezoneStore:
    """Stores a single timezone string supplied by the client UI."""

    _TIMEZONE_ID = "main"  # Fixed ID for the single timezone document

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("timezone_store")
        self._ensure_indexes()
        self._cached: Optional[str] = None
        self._load()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for timezone_id lookup
            self._collection.create_index([("timezone_id", 1)], unique=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Timezone store index creation failed",
                extra={"error": str(exc)},
            )

    def _load(self) -> None:
        try:
            doc = self._collection.find_one({"timezone_id": self._TIMEZONE_ID})
            if doc is not None:
                value = doc.get("timezone")
                self._cached = value.strip() if value else None
            else:
                self._cached = None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to read timezone from MongoDB",
                extra={"error": str(exc)},
            )
            self._cached = None

    def get_timezone(self, default: str = "UTC") -> str:
        return self._cached or default

    def set_timezone(self, timezone_name: str) -> None:
        validated = self._validate(timezone_name)
        try:
            self._collection.update_one(
                {"timezone_id": self._TIMEZONE_ID},
                {"$set": {"timezone": validated}},
                upsert=True,
            )
            self._cached = validated
            logger.info("updated timezone preference", extra={"timezone": validated})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to save timezone to MongoDB",
                extra={"error": str(exc)},
            )
            raise

    def clear(self) -> None:
        self._cached = None
        try:
            self._collection.delete_one({"timezone_id": self._TIMEZONE_ID})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to clear timezone from MongoDB",
                extra={"error": str(exc)},
            )

    def _validate(self, timezone_name: str) -> str:
        candidate = (timezone_name or "").strip()
        if not candidate:
            raise ValueError("timezone must be a non-empty string")
        try:
            ZoneInfo(candidate)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {candidate}") from exc
        return candidate


_timezone_store = TimezoneStore()


def get_timezone_store() -> TimezoneStore:
    return _timezone_store


__all__ = ["TimezoneStore", "get_timezone_store"]
