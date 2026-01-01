import asyncio
from datetime import datetime, timezone, timedelta
import logging
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp import Client
from server.mcp_server.auth import get_mcp_authenticator
from server.mcp_server import get_mcp_server_mapping
from mcp.types import TextContent, ImageContent, EmbeddedResource
from typing import List

logger = logging.getLogger("MCPClient")
MCP_AUTHENTICATOR = get_mcp_authenticator()
MCP_SERVER_MAPPING = get_mcp_server_mapping()

class SimpleMCPClient:
    """Simple MCP client that connects directly to MCP servers"""

    def __init__(self, mcp_server_name: str, agent_name: str):
        self.mcp_server_name = mcp_server_name
        self.mcp_url = MCP_SERVER_MAPPING[mcp_server_name]

        transport = StreamableHttpTransport(
            url=self.mcp_url,
            headers={
                "x-openpoke": f"{MCP_AUTHENTICATOR.create_token(agent_name)}"
            },
        )
        self.client = Client(transport)
        self.expired_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.tools = []

    async def _is_client_expired(self):
        return datetime.now(timezone.utc) >= self.expired_at

    async def _refresh_client(self):
        if await self._is_client_expired():
            transport = StreamableHttpTransport(
                url=self.mcp_url,
                headers={
                    "x-openpoke": f"{MCP_AUTHENTICATOR.create_token(self.agent_name)}"
                },
            )
            self.client = Client(transport)
            self.expired_at = datetime.now(timezone.utc) + timedelta(hours=1)

    async def connect(self):
        """Connect to MCP server and get available tools"""
        try:
            await self._refresh_client()
            async with self.client:
                tools = await self.client.list_tools()
                self.tools = tools
        except Exception as e:
            logger.error(
                f"Error connecting to MCP server {self.mcp_url}: {e}"
            )
            raise

    async def call_tool(self, tool_name: str, arguments: dict) -> List[TextContent|ImageContent|EmbeddedResource]:
        """Call a specific tool on the MCP server"""
        try:
            await self._refresh_client()
            async with self.client:
                result = await self.client.call_tool(tool_name, arguments)
                logger.info(
                    f"[{datetime.now(timezone.utc)}] called tool {tool_name} with arguments {arguments} and result {result}"
                )
                return result
        except Exception as e:
            logger.error(
                f"Error calling tool {tool_name}: {e} and arguments {arguments}"
            )
            return f"Error: {str(e)}"

    def get_tools(self):
        """Get list of available tools"""
        return self.tools

    async def cleanup(self):
        """Clean up client resources (for both async and sync close methods)."""
        if not hasattr(self, "client"):
            return

        try:
            # Prefer async close if provided by the client implementation.
            if hasattr(self.client, "aclose") and callable(
                getattr(self.client, "aclose")
            ):
                await self.client.aclose()  # type: ignore[attr-defined]
            # Fallback to synchronous close if available.
            elif hasattr(self.client, "close") and callable(
                getattr(self.client, "close")
            ):
                await self.client.close()  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Error cleaning up MCP client: {e}")

# async def main():
#     client2 = SimpleMCPClient("trigger_mcp", "agent_1")
#     await client2.connect()
#     print(await convert_mcp_tool_to_tool_schema(client2.get_tools()[0]))

# if __name__ == "__main__":
#     asyncio.run(main())
