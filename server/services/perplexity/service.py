import logging
from server.openrouter_client.client import request_chat_completion
from server.config import get_settings
from server.services.perplexity.models import PerplexitySearchResponse
from typing import List, Dict, Any
from server.services.perplexity.store import PerplexityStore

logger = logging.getLogger("PerplexityService")

class PerplexityService:
    """Service for Perplexity operations."""

    def __init__(self, store: PerplexityStore):
        self._store = store
        self.model = get_settings().internet_search_model
        self.deep_model = get_settings().internet_search_deep_model
        self.api_key = get_settings().openrouter_api_key
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")

    def _parse_citations(self, citations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        parsed_citations: List[Dict[str, str]] = []
        for id, citation in enumerate(citations):
            parsed_citations.append({
                "id": id + 1,
                "title": citation.get("url_citation", {}).get("title", ""),
                "url": citation.get("url_citation", {}).get("url", ""),
            })
        return parsed_citations

    async def clear_all(self) -> None:
        """Clear all Perplexity search history records."""
        await self._store.clear_all()
        logger.info("Cleared all Perplexity search history records")

    async def parse_response(self, response: Dict[str, Any]) -> PerplexitySearchResponse:
        """Parse the response from the Perplexity API."""
        response_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = response.get("choices", [{}])[0].get("message", {}).get("annotations", [])
        parsed_citations = self._parse_citations(citations)
        usage_metadata = response.get("usage", {})
        return PerplexitySearchResponse(response=response_content, citations=parsed_citations, usage_metadata=usage_metadata)

    async def deep_search(self, agent_name: str, query: str, recency: str) -> PerplexitySearchResponse:
        """Search the web for information with a deeper level of detail."""
        logger.info(f"[PERPLEXITY] [{agent_name}] Searching the web for information with a deeper level of detail: {query}")
        additional_payload = {"recency": recency} if recency else {}
        response = await request_chat_completion(
            model=self.deep_model,
            messages=[{"role": "system", "content": "Be detailed. Provide as much information as possible."}, {"role": "user", "content": f"Find information about: {query}"}],
            api_key=self.api_key,
            additional_payload=additional_payload,
        )
        response_obj = await self.parse_response(response)
        await self._store.insert(agent_name=agent_name, model=self.deep_model, query=query, recency=recency, response=response_obj)
        logger.info(f"[PERPLEXITY] [{agent_name}] Deep search results: {response_obj.response[:100]}")
        return response_obj

    async def search(self, agent_name: str, query: str, recency: str) -> PerplexitySearchResponse:
        """Search the web for information."""
        logger.info(f"[PERPLEXITY] [{agent_name}] Searching the web for information: {query}")
        additional_payload = {"recency": recency} if recency else {}
        response = await request_chat_completion(
            model=self.model,
            messages=[{"role": "system", "content": "Be detailed. Provide a concise summary of the query."}, {"role": "user", "content": f"Find information about: {query}"}],
            api_key=self.api_key,
            additional_payload=additional_payload,
        )
        response_obj = await self.parse_response(response)
        await self._store.insert(agent_name=agent_name, model=self.model, query=query, recency=recency, response=response_obj)
        logger.info(f"[PERPLEXITY] [{agent_name}] Search results: {response_obj.response[:100]}")
        return response_obj

_perplexity_store = PerplexityStore()
_perplexity_service = PerplexityService(_perplexity_store)

def get_perplexity_service() -> PerplexityService:
    """Get the Perplexity service."""
    return _perplexity_service