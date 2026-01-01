"""Aggregate execution agent tool schemas and registries."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from . import gmail, triggers
from ..tasks.search_email.tool import build_registry as _build_email_search_registry
from ..tasks.search_email.schemas import get_schemas as get_email_search_schemas

# Return OpenAI/OpenRouter-compatible tool schemas
def get_tool_schemas() -> Dict[str, Any]:
    """Return OpenAI/OpenRouter-compatible tool schemas."""

    return {
        "gmail_tool": gmail.get_schemas() + get_email_search_schemas(),
    }


# Return Python callables for executing tools by name
def get_tool_registry() -> Dict[str, Any]:
    """Return Python callables for executing tools by name."""

    return {
        "gmail_tool": gmail.build_registry() | _build_email_search_registry(),
    }


__all__ = [
    "get_tool_registry",
    "get_tool_schemas",
]
