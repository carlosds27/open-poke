"""Aggregate execution agent tool schemas and registries."""

from __future__ import annotations

from typing import Any, Dict

from . import gmail
from ..tasks.search_email.tool import build_registry as _build_email_search_registry
from ..tasks.search_email.schemas import get_schemas as get_email_search_schemas


def get_tools() -> Dict[str, Any]:
    """Return all tools (MCP and OpenAI-compatible) that the execution agent can use"""

    return {
        "gmail_tool": {
            "type": "func",
            "schema": gmail.get_schemas() + get_email_search_schemas(),
            "registry": gmail.build_registry() | _build_email_search_registry,
        },
        "trigger_tool": {
            "type": "mcp",
            "url": "http://localhost:9141/triggers/mcp",
        },
        "bookkeeping_tool": {
            "type": "mcp",
            "url": "http://localhost:9142/bookkeeping/mcp",
        },
        "perplexity_tool": {
            "type": "mcp",
            "url": "http://localhost:9143/perplexity/mcp",
        },
    }


__all__ = [
    "get_tools",
]
