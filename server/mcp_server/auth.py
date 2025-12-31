from server.services.database.mongodb import MongoDB
from datetime import datetime, timezone
import jwt

from server.config import get_settings

settings = get_settings()
JWT_SECRET = settings.jwt_secret

class MCPAuthenticator:
    def __init__(self):
        self.db = MongoDB.get_instance()
        self.exp_time = 3600

    def create_token(self, agent_name: str):
        current_time = datetime.now(timezone.utc).timestamp()
        payload = {
            "iat": current_time,
            "exp": current_time + self.exp_time,
            "agent_name": agent_name,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        return token

    def verify_token(self, token: str):
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return data.get("agent_name")
        except Exception as e:
            print(f"Error in verify_token: {e}")
            return None

_mcp_authenticator = MCPAuthenticator()

def get_mcp_authenticator():
    return _mcp_authenticator

__all__ = ["get_mcp_authenticator"]