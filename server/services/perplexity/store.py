from server.services.database.mongodb import MongoDB
from datetime import datetime, timezone
from server.services.perplexity.models import PerplexitySearchResponse
from typing import Optional, List

class PerplexityStore:
    """Store for Perplexity operations."""

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("perplexity_search_history")

    async def insert(self, agent_name: str, model: str, query: str, recency: Optional[str], response: PerplexitySearchResponse) -> None:
        """Insert a new Perplexity search history record."""
        document = {
            "agent_name": agent_name,
            "model": model,
            "query": query,
            "recency": recency,
            "response": response.model_dump(),
            "created_at": datetime.now(timezone.utc),
        }
        self._collection.insert_one(document)

    async def fetch_all(self) -> List[PerplexitySearchResponse]:
        """Fetch all Perplexity search history records."""
        documents = self._collection.find()
        return [PerplexitySearchResponse.model_validate(document) for document in documents]

    async def clear_all(self) -> None:
        """Clear all Perplexity search history records."""
        self._collection.delete_many({})