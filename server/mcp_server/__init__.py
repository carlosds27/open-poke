from .auth import get_mcp_authenticator
from .base import OpenPokeMCP

__all__ = ["get_mcp_authenticator", "OpenPokeMCP"]

def get_mcp_server_mapping():
    return {
        "gmail_mcp": "http://localhost:9142/gmail/mcp",
        "trigger_mcp": "http://localhost:9141/triggers/mcp",
    }