"""Agent roster management with vector search support - each agent stored as a separate document."""
import asyncio

from pydantic import BaseModel, Field
from ..database.mongodb import MongoDB
from ...logging_config import logger
from ...openrouter_client.client import generate_embedding
from ...config import get_settings

class AgentObject(BaseModel):
    """Object representing an agent in the roster."""
    name: str = Field(..., description="The name of the agent.")
    description: str = Field(..., description="The description of the agent.")

class AgentRoster:
    """Roster that stores each agent as a separate document in MongoDB with vector search support."""

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("agent_roster")
        self._vector_search_index = "agent_description_vector_index"
        self._vector_search_dimension = 1536
        self._embedding_model = "openai/text-embedding-3-small"
        settings = get_settings()
        self._openrouter_api_key = settings.openrouter_api_key
        self._agents: list[AgentObject] = []
        self._ensure_indexes()
        self.load()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for agent name lookup (unique to prevent duplicates)
            self._collection.create_index([("name", 1)], unique=True)
        except Exception as exc:
            logger.warning(
                "Agent roster index creation failed",
                extra={"error": str(exc)},
            )

    async def _generate_embedding(self, description: str) -> list[float]:
        """Generate an embedding for the description using the embedding model."""
        return await generate_embedding(self._embedding_model, description, api_key=self._openrouter_api_key)

    def load(self) -> None:
        """Load agent objects from MongoDB."""
        try:
            cursor = self._collection.find({})
            self._agents = []
            for doc in cursor:
                self._agents.append(
                    AgentObject(
                        name=doc["name"],
                        description=doc["description"],
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to load agent roster",
                extra={"error": str(exc)},
            )
            self._agents = []

    async def add_agent(self, agent_name: str, agent_description: str) -> None:
        """Add an agent to the roster if not already present."""
        if agent_name not in self.get_agent_names():
            agent = AgentObject(name=agent_name, description=agent_description)
            
            # Save to MongoDB as a separate document
            try:
                logger.info(f"Adding agent to roster: {agent_name} - {agent_description}. Generating embedding...")
                embedding = await self._generate_embedding(agent_description)
                self._collection.insert_one({
                    "name": agent_name,
                    "description": agent_description,
                    "embedding": embedding
                })
                # Only add to in-memory list if save was successful
                self._agents.append(agent)
            except Exception as exc:
                # Check if it's a duplicate key error (agent already exists in DB)
                if "duplicate key" in str(exc).lower() or "E11000" in str(exc):
                    logger.info(
                        "Agent already exists in database, reloading roster",
                        extra={"agent_name": agent_name},
                    )
                    self.load()  # Reload to sync with database
                else:
                    logger.warning(
                        "Failed to save agent to roster",
                        extra={"error": str(exc), "agent_name": agent_name},
                    )

    def get_agent_names(self) -> list[str]:
        """Get list of all agent names."""
        return [agent.name for agent in self._agents]

    async def search_agents_by_description(
        self, 
        query_description: str, 
        limit: int = 5,
        min_score: float = 0.0
    ) -> list[AgentObject]:
        """Search for agents using vector search on their descriptions.
        
        Args:
            query_description: The description to search for
            limit: Maximum number of results to return
            min_score: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of AgentObject instances sorted by relevance
        """
        try:
            # Generate placeholder embedding for query
            query_embedding = await self._generate_embedding(query_description)
            
            # Use $vectorSearch aggregation pipeline for MongoDB Atlas Vector Search
            # Note: This requires a vector search index to be created in Atlas
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self._vector_search_index,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": limit * 10,  # Search more candidates for better results
                        "limit": limit
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            results = []
            for doc in self._collection.aggregate(pipeline):
                logger.info(f"Found agent in vector search: {doc['name']} - {doc['description']} - {doc['score']}")
                results.append(
                    AgentObject(
                        name=doc["name"],
                        description=doc["description"],
                    )
                )
            
            return results
        except Exception as exc:
            logger.warning(
                "Vector search failed, falling back to simple text search",
                extra={"error": str(exc)},
            )
            return [
                agent for agent in self._agents
                if query_description.lower() in agent.description.lower()
            ][:limit]

    def clear(self) -> None:
        """Clear the agent roster."""
        self._agents = []
        try:
            self._collection.delete_many({})
            logger.info("Cleared agent roster")
        except Exception as exc:
            logger.warning(
                "Failed to clear agent roster",
                extra={"error": str(exc)},
            )


_agent_roster = AgentRoster()


def get_agent_roster() -> AgentRoster:
    """Get the singleton roster instance."""
    return _agent_roster
