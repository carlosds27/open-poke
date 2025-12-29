from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape, unescape
from typing import List, Optional, Tuple

from ...database.mongodb import MongoDB
from ....logging_config import logger
from ....utils.timezones import now_in_user_timezone
from .state import LogEntry, SummaryState


def _encode_payload(payload: str) -> str:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    return unescape(payload).replace("\\n", "\n")


def _format_line(tag: str, payload: str, timestamp: Optional[str] = None) -> str:
    encoded = _encode_payload(payload)
    if timestamp:
        return f'<{tag} timestamp="{timestamp}">{encoded}</{tag}>\n'
    return f"<{tag}>{encoded}</{tag}>\n"


def _current_timestamp() -> str:
    return now_in_user_timezone("%Y-%m-%d %H:%M:%S")


class WorkingMemoryLog:
    """Persisted working-memory MongoDB collection storing conversation summary and recent entries."""

    def __init__(self) -> None:
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("working_memory_log")
        self._ensure_indexes()
        self._initialize_collection()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for entry type and sequence ordering
            self._collection.create_index([("_type", 1), ("sequence", 1)])
            # Index for summary state lookup
            self._collection.create_index([("_type", 1)])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "working memory index creation failed",
                extra={"error": str(exc)},
            )

    def _initialize_collection(self) -> None:
        """Initialize collection with empty summary state if needed."""
        existing = self._collection.find_one({"_type": "summary_state"})
        if existing is not None:
            return
        initial_state = SummaryState.empty()
        summary_doc = {
            "_type": "summary_state",
            "summary_text": "",
            "last_index": initial_state.last_index,
            "updated_at": None,
        }
        try:
            self._collection.insert_one(summary_doc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "working memory initialization failed",
                extra={"error": str(exc)},
            )
            raise

    def _get_next_sequence(self) -> int:
        """Get the next sequence number for entries."""
        max_doc = self._collection.find_one({"_type": "entry"}, sort=[("sequence", -1)])
        return 1 if max_doc is None else max_doc.get("sequence", 0) + 1

    def append_entry(
        self, tag: str, payload: str, timestamp: Optional[str] = None
    ) -> None:
        sanitized_timestamp = timestamp or _current_timestamp()
        sequence = self._get_next_sequence()
        encoded_payload = _encode_payload(str(payload))

        entry_doc = {
            "_type": "entry",
            "tag": tag,
            "payload": encoded_payload,
            "timestamp": sanitized_timestamp,
            "sequence": sequence,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            self._collection.insert_one(entry_doc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "working memory append failed",
                extra={"error": str(exc), "tag": tag},
            )
            raise

    def load_summary_state(self) -> SummaryState:
        try:
            # Load summary state document
            summary_doc = self._collection.find_one({"_type": "summary_state"})
            if summary_doc is None:
                return SummaryState.empty()

            summary_text = summary_doc.get("summary_text", "")
            last_index = summary_doc.get("last_index", -1)
            updated_at_raw = summary_doc.get("updated_at")
            updated_at: Optional[datetime] = None
            if isinstance(updated_at_raw, str) and updated_at_raw:
                try:
                    updated_at = datetime.fromisoformat(updated_at_raw)
                except ValueError:
                    updated_at = None
            elif isinstance(updated_at_raw, datetime):
                updated_at = updated_at_raw

            # Load all entries
            entries: List[LogEntry] = []
            entry_cursor = self._collection.find({"_type": "entry"}).sort(
                [("sequence", 1)]
            )
            for entry_doc in entry_cursor:
                decoded_payload = _decode_payload(entry_doc.get("payload", ""))
                entries.append(
                    LogEntry(
                        tag=entry_doc.get("tag", ""),
                        payload=decoded_payload,
                        timestamp=entry_doc.get("timestamp"),
                    )
                )

            state = SummaryState(
                summary_text=summary_text,
                last_index=last_index,
                updated_at=updated_at,
                unsummarized_entries=entries,
            )
            return state
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "working memory read failed",
                extra={"error": str(exc)},
            )
            return SummaryState.empty()

    def write_summary_state(self, state: SummaryState) -> None:
        try:
            # Update or insert summary state document
            summary_doc = {
                "_type": "summary_state",
                "summary_text": state.summary_text or "",
                "last_index": state.last_index,
                "updated_at": (
                    state.updated_at.isoformat() if state.updated_at else None
                ),
            }
            self._collection.update_one(
                {"_type": "summary_state"},
                {"$set": summary_doc},
                upsert=True,
            )

            # Delete all existing entries
            self._collection.delete_many({"_type": "entry"})

            # Insert new entries
            if state.unsummarized_entries:
                entry_docs = []
                for idx, entry in enumerate(state.unsummarized_entries, start=1):
                    encoded_payload = _encode_payload(entry.payload)
                    entry_doc = {
                        "_type": "entry",
                        "tag": entry.tag,
                        "payload": encoded_payload,
                        "timestamp": entry.timestamp,
                        "sequence": idx,
                        "created_at": datetime.now(timezone.utc),
                    }
                    entry_docs.append(entry_doc)
                if entry_docs:
                    self._collection.insert_many(entry_docs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "working memory write failed",
                extra={"error": str(exc)},
            )
            raise

    def render_transcript(self, state: Optional[SummaryState] = None) -> str:
        snapshot = state or self.load_summary_state()
        parts: List[str] = []

        summary_text = (snapshot.summary_text or "").strip()
        if summary_text:
            safe_summary = escape(summary_text, quote=False)
            parts.append(f"<conversation_summary>{safe_summary}</conversation_summary>")

        for entry in snapshot.unsummarized_entries:
            safe_payload = escape(entry.payload, quote=False)
            if entry.timestamp:
                parts.append(
                    f'<{entry.tag} timestamp="{entry.timestamp}">{safe_payload}</{entry.tag}>'
                )
            else:
                parts.append(f"<{entry.tag}>{safe_payload}</{entry.tag}>")

        return "\n".join(parts)

    def clear(self) -> None:
        try:
            # Delete all documents
            self._collection.delete_many({})
            # Reinitialize with empty state
            self._initialize_collection()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "working memory clear failed",
                extra={"error": str(exc)},
            )


_working_memory_log: Optional[WorkingMemoryLog] = None


def get_working_memory_log() -> WorkingMemoryLog:
    global _working_memory_log
    if _working_memory_log is None:
        _working_memory_log = WorkingMemoryLog()
    return _working_memory_log


__all__ = ["WorkingMemoryLog", "get_working_memory_log"]
