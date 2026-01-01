from fastmcp import FastMCP
from fastapi import Request, HTTPException
from typing import Any
from mcp.types import TextContent, ImageContent, EmbeddedResource
from fastmcp.server.dependencies import get_http_request
from server.mcp_server.auth import get_mcp_authenticator

MCP_AUTHENTICATOR = get_mcp_authenticator()

class OpenPokeMCP(FastMCP):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)

    async def get_tools(self):
        request: Request = get_http_request()
        headers = request.headers

        openpoke_mcp_auth_token = headers.get("x-openpoke")
        if not openpoke_mcp_auth_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        agent_name = MCP_AUTHENTICATOR.verify_token(openpoke_mcp_auth_token)
        if not agent_name:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return await super().get_tools()

    async def _mcp_call_tool(
        self, key: str, arguments: dict[str, Any]
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        # Get the conversation id from the token
        request: Request = get_http_request()
        headers = request.headers
        openpoke_mcp_auth_token = headers.get("x-openpoke")
        if not openpoke_mcp_auth_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        agent_name = MCP_AUTHENTICATOR.verify_token(openpoke_mcp_auth_token)
        if not agent_name:
            raise HTTPException(status_code=401, detail="Unauthorized")
        filtered_arguments = await self.check_tool_parameters(key, arguments, agent_name)
        return await super()._mcp_call_tool(key, filtered_arguments)

    async def check_tool_parameters(
        self, key: str, arguments: dict[str, Any], agent_name: str
    ) -> dict[str, Any]:
        """
        Check if the tool parameters are valid
        If there are extra parameter in the arguments, filter them out and return the valid parameters (the only ones that are in the tool schema
        """
        tool = self._tool_manager.get_tool(key)
        tool_parameters = tool.parameters
        tool_properties = tool_parameters.get("properties", {})
        valid_parameters = set(tool_properties.keys())
        # Filter out the extra parameters
        filtered_arguments = {
            k: v for k, v in arguments.items() if k in valid_parameters
        }
        # If agent_name in valid_parameters, fill it in automatically with the agent_name
        if "agent_name" in valid_parameters:
            filtered_arguments["agent_name"] = agent_name
        return filtered_arguments
