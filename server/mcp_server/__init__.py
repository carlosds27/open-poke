from .auth import get_mcp_authenticator
from .base import OpenPokeMCP

__all__ = ["get_mcp_authenticator", "OpenPokeMCP"]

def get_mcp_server_mapping():
    return {
        "trigger_tool": "http://localhost:9141/triggers/mcp",
        "bookkeeping_tool": "http://localhost:9142/bookkeeping/mcp",
        "perplexity_tool": "http://localhost:9143/perplexity/mcp",
    }