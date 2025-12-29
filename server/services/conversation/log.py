from __future__ import annotations

from datetime import datetime, timezone
from html import escape, unescape
from typing import Iterator, List, Optional, Protocol, Tuple

from ...config import get_settings
from ..database.mongodb import MongoDB
from ...logging_config import logger
from ...models import ChatMessage
from ...utils.timezones import now_in_user_timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from .summarization import WorkingMemoryLog


class TranscriptFormatter(Protocol):
    def __call__(
        self, tag: str, timestamp: str, payload: str
    ) -> str:  # pragma: no cover - typing protocol
        ...


def _encode_payload(payload: str) -> str:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    return unescape(payload).replace("\\n", "\n")


def _resolve_working_memory_log() -> "WorkingMemoryLog":
    from .summarization import get_working_memory_log

    return get_working_memory_log()


class ConversationLog:
    """Append-only conversation log persisted to MongoDB for the interaction agent."""

    def __init__(self, formatter: Optional[TranscriptFormatter] = None):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("conversation_log")
        self._formatter = formatter
        self._ensure_indexes()
        self._working_memory_log = _resolve_working_memory_log()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for sequence ordering
            self._collection.create_index([("sequence", 1)])
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "conversation log index creation failed",
                extra={"error": str(exc)},
            )

    def _get_next_sequence(self) -> int:
        """Get the next sequence number."""
        max_doc = self._collection.find_one(sort=[("sequence", -1)])
        return 1 if max_doc is None else max_doc.get("sequence", 0) + 1

    def _append(self, tag: str, payload: str) -> str:
        timestamp = now_in_user_timezone("%Y-%m-%d %H:%M:%S")
        sequence = self._get_next_sequence()
        encoded_payload = _encode_payload(str(payload))

        document = {
            "tag": tag,
            "timestamp": timestamp,
            "payload": encoded_payload,
            "sequence": sequence,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            self._collection.insert_one(document)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "conversation log append failed",
                extra={"error": str(exc), "tag": tag},
            )
            raise
        self._notify_summarization()
        return timestamp

    def iter_entries(self) -> Iterator[Tuple[str, str, str]]:
        try:
            cursor = self._collection.find({}).sort([("sequence", 1)])
            for doc in cursor:
                decoded_payload = _decode_payload(doc["payload"])
                yield doc["tag"], doc.get("timestamp", ""), decoded_payload
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "conversation log read failed",
                extra={"error": str(exc)},
            )
            raise

    def load_transcript(self) -> str:
        parts: List[str] = []
        for tag, timestamp, payload in self.iter_entries():
            safe_payload = escape(payload, quote=False)
            if timestamp:
                parts.append(f'<{tag} timestamp="{timestamp}">{safe_payload}</{tag}>')
            else:
                parts.append(f"<{tag}>{safe_payload}</{tag}>")
        return "\n".join(parts)

    def record_user_message(self, content: str) -> None:
        timestamp = self._append("user_message", content)
        self._working_memory_log.append_entry("user_message", content, timestamp)

    def record_agent_message(self, content: str) -> None:
        timestamp = self._append("agent_message", content)
        self._working_memory_log.append_entry("agent_message", content, timestamp)

    def record_reply(self, content: str) -> None:
        timestamp = self._append("poke_reply", content)
        self._working_memory_log.append_entry("poke_reply", content, timestamp)

    def record_wait(self, reason: str) -> None:
        """Record a wait marker that should not reach the user-facing chat history."""
        timestamp = self._append("wait", reason)
        self._working_memory_log.append_entry("wait", reason, timestamp)

    def _notify_summarization(self) -> None:
        settings = get_settings()
        if not settings.summarization_enabled:
            return

        try:
            from .summarization import schedule_summarization  # type: ignore import-not-found
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "summarization scheduler unavailable",
                extra={"error": str(exc)},
            )
            return

        try:
            schedule_summarization()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to schedule summarization",
                extra={"error": str(exc)},
            )

    def to_chat_messages(self) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        for tag, timestamp, payload in self.iter_entries():
            normalized_timestamp = timestamp or None
            if tag == "user_message":
                messages.append(
                    ChatMessage(
                        role="user", content=payload, timestamp=normalized_timestamp
                    )
                )
            elif tag == "poke_reply":
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=payload,
                        timestamp=normalized_timestamp,
                    )
                )
            elif tag == "wait":
                # Wait markers are orchestration metadata and must not surface to the user
                continue
        return messages

    def clear(self) -> None:
        try:
            self._collection.delete_many({})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "conversation log clear failed",
                extra={"error": str(exc)},
            )
        try:
            self._working_memory_log.clear()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "working memory clear skipped",
                extra={"error": str(exc)},
            )


_conversation_log = ConversationLog()


def get_conversation_log() -> ConversationLog:
    return _conversation_log


__all__ = ["ConversationLog", "get_conversation_log"]
