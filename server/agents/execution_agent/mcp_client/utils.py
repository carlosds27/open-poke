from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from typing import List
import json

async def convert_mcp_tool_to_tool_schema(mcp_tool: Tool) -> dict:
    """Convert an MCP tool to a tool schema"""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema | {"additionalProperties": False},
        },
    }

async def convert_mcp_tool_result_to_dict(mcp_tool_result: List[TextContent|ImageContent|EmbeddedResource]) -> dict | str:
    """Convert an MCP tool result to a dictionary (or string if it's not a dictionary)"""
    try:
        if isinstance(mcp_tool_result[0], TextContent):
            result = mcp_tool_result[0].text
            result_json = json.loads(result)
            return result_json
        elif isinstance(mcp_tool_result[0], ImageContent):
            return mcp_tool_result[0].data
        elif isinstance(mcp_tool_result[0], EmbeddedResource):
            return mcp_tool_result[0].resource
        else:
            return str(mcp_tool_result[0])
    except Exception as e:
        return str(mcp_tool_result[0])