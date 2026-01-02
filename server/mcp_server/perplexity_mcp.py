from server.mcp_server.base import OpenPokeMCP
from typing import Annotated, Optional, Dict, Any
from server.services.perplexity import get_perplexity_service
mcp = OpenPokeMCP(
    name="perplexity_mcp",
    version="1.0.0",
    instructions="This server provides the Perplexity search tool. You can use this tool to search the web for information.",
)

_PERPLEXITY_SERVICE = get_perplexity_service()

@mcp.tool(name="search")
async def search(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    query: Annotated[str, "The query to search for."],
    recency: Annotated[Optional[str], "The recency of the search results. Can be 'day', 'week', 'month', or 'year'. If not needed, leave it blank."],
) -> Dict[str, Any]:
    """Search the web for information. Default level of detail."""
    if recency is not None and recency not in ['day', 'week', 'month', 'year']:
        return {"error": "Invalid recency. Must be 'day', 'week', 'month', or 'year' or leave it blank."}
    perplexity_response = await _PERPLEXITY_SERVICE.search(query=query, recency=recency)
    return perplexity_response.model_dump()

@mcp.tool(name="deep_search")
async def deep_search(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    query: Annotated[str, "The query to search for."],
    recency: Annotated[Optional[str], "The recency of the search results. Can be 'day', 'week', 'month', or 'year'. If not needed, leave it blank."],
) -> Dict[str, Any]:
    """Search the web for information with a deeper level of detail."""
    if recency is not None and recency not in ['day', 'week', 'month', 'year']:
        return {"error": "Invalid recency. Must be 'day', 'week', 'month', or 'year' or leave it blank."}
    perplexity_response = await _PERPLEXITY_SERVICE.deep_search(query=query, recency=recency)
    return perplexity_response.model_dump()

if __name__ == "__main__":
    import uvicorn
    mcp_server = mcp.http_app(path="/perplexity/mcp")
    uvicorn.run(mcp_server, host="0.0.0.0", port=9143)