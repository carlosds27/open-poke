from server.openrouter_client.client import request_chat_completion
from server.config import get_settings
from server.services.perplexity.models import PerplexitySearchResponse
from typing import List, Dict, Any

class PerplexityService:
    """Service for Perplexity operations."""

    def __init__(self):
        self.model = get_settings().internet_search_model
        self.deep_model = get_settings().internet_search_deep_model
        self.api_key = get_settings().openrouter_api_key
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")

    def _parse_citations(self, citations: List[Dict[str, Any]]) -> List[str]:
        parsed_citations: List[Dict[str, str]] = []
        for citation in citations:
            parsed_citations.append({
                "title": citation.get("url_citation", {}).get("title", ""),
                "url": citation.get("url_citation", {}).get("url", ""),
            })
        return parsed_citations

    async def parse_response(self, response: Dict[str, Any]) -> PerplexitySearchResponse:
        """Parse the response from the Perplexity API."""
        response_content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = response.get("choices", [{}])[0].get("message", {}).get("annotations", [])
        parsed_citations = self._parse_citations(citations)
        usage_metadata = response.get("usage", {})
        return PerplexitySearchResponse(response=response_content, citations=parsed_citations, usage_metadata=usage_metadata)

    async def deep_search(self, query: str, recency: str) -> PerplexitySearchResponse:
        """Search the web for information with a deeper level of detail."""
        response = await request_chat_completion(
            model=self.deep_model,
            messages=[{"role": "system", "content": "Be detailed. Provide as much information as possible."}, {"role": "user", "content": query}],
            api_key=self.api_key,
            additional_payload={"recency": recency},
        )
        return self.parse_response(response)

    async def search(self, query: str, recency: str) -> PerplexitySearchResponse:
        """Search the web for information."""
        response = await request_chat_completion(
            model=self.model,
            messages=[{"role": "system", "content": "Be detailed. Provide a concise summary of the query."}, {"role": "user", "content": query}],
            api_key=self.api_key,
            additional_payload={"recency": recency},
        )
        return self.parse_response(response)

_perplexity_service = PerplexityService()

def get_perplexity_service() -> PerplexityService:
    """Get the Perplexity service."""
    return _perplexity_service