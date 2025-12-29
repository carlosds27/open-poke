"""Execution agent log management with structured XML-style tags."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape, unescape
from typing import Iterator, List, Optional, Tuple

from ..database.mongodb import MongoDB
from ...logging_config import logger
from ...utils.timezones import now_in_user_timezone


def _encode_payload(payload: str) -> str:
    """Encode payload for storage."""
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    """Decode payload from storage."""
    return unescape(payload).replace("\\n", "\n")


class ExecutionAgentLogStore:
    """Append-only journal for execution agents with XML-style tags."""

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("execution_agent_logs")
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for agent_name and sequence ordering
            self._collection.create_index([("agent_name", 1), ("sequence", 1)])
            # Index for listing distinct agents
            self._collection.create_index([("agent_name", 1)])
        except Exception as exc:
            logger.warning(
                "Execution agent log index creation failed",
                extra={"error": str(exc)},
            )

    def _get_next_sequence(self, agent_name: str) -> int:
        """Get the next sequence number for an agent."""
        max_doc = self._collection.find_one(
            {"agent_name": agent_name}, sort=[("sequence", -1)]
        )
        return 1 if max_doc is None else max_doc.get("sequence", 0) + 1

    def _append(self, agent_name: str, tag: str, payload: str) -> None:
        """Append an entry with the given tag."""
        timestamp = now_in_user_timezone("%Y-%m-%d %H:%M:%S")
        sequence = self._get_next_sequence(agent_name)
        encoded_payload = _encode_payload(str(payload))

        document = {
            "agent_name": agent_name,
            "tag": tag,
            "timestamp": timestamp,
            "payload": encoded_payload,
            "sequence": sequence,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            self._collection.insert_one(document)
        except Exception as exc:
            logger.error(
                "Failed to append to log",
                extra={"agent_name": agent_name, "error": str(exc)},
            )

    def record_request(self, agent_name: str, instructions: str) -> None:
        """Record an incoming request from the interaction agent."""
        self._append(agent_name, "agent_request", instructions)

    def record_action(self, agent_name: str, description: str) -> None:
        """Record an agent action (tool call)."""
        self._append(agent_name, "agent_action", description)

    def record_tool_response(
        self, agent_name: str, tool_name: str, response: str
    ) -> None:
        """Record the response from a tool."""
        self._append(agent_name, "tool_response", f"{tool_name}: {response}")

    def record_agent_response(self, agent_name: str, response: str) -> None:
        """Record the agent's final response."""
        self._append(agent_name, "agent_response", response)

    def iter_entries(self, agent_name: str) -> Iterator[Tuple[str, str, str]]:
        """Iterate over all log entries for an agent."""
        try:
            cursor = self._collection.find({"agent_name": agent_name}).sort(
                [("sequence", 1)]
            )
            for doc in cursor:
                decoded_payload = _decode_payload(doc["payload"])
                yield doc["tag"], doc.get("timestamp", ""), decoded_payload
        except Exception as exc:
            logger.error(
                "Failed to read log",
                extra={"agent_name": agent_name, "error": str(exc)},
            )

    def load_transcript(self, agent_name: str) -> str:
        """Load the full transcript for inclusion in system prompt."""
        parts: List[str] = []
        for tag, timestamp, payload in self.iter_entries(agent_name):
            escaped = escape(payload, quote=False)
            if timestamp:
                parts.append(f'<{tag} timestamp="{timestamp}">{escaped}</{tag}>')
            else:
                parts.append(f"<{tag}>{escaped}</{tag}>")
        return "\n".join(parts)

    def load_recent(
        self, agent_name: str, limit: int = 10
    ) -> list[tuple[str, str, str]]:
        """Load recent log entries."""
        entries = list(self.iter_entries(agent_name))
        return entries[-limit:] if entries else []

    def list_agents(self) -> list[str]:
        """List all agents with logs."""
        try:
            distinct_agents = self._collection.distinct("agent_name")
            return sorted(distinct_agents)
        except Exception as exc:
            logger.error(
                "Failed to list agents",
                extra={"error": str(exc)},
            )
            return []

    def clear_all(self) -> None:
        """Clear all execution agent logs."""
        try:
            result = self._collection.delete_many({})
            logger.info(
                "Cleared all execution agent logs",
                extra={"deleted_count": result.deleted_count},
            )
        except Exception as exc:
            logger.error(
                "Failed to clear execution logs",
                extra={"error": str(exc)},
            )


_execution_agent_logs = ExecutionAgentLogStore()


def get_execution_agent_logs() -> ExecutionAgentLogStore:
    """Get the singleton log store instance."""
    return _execution_agent_logs
