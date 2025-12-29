"""Simple agent roster management - just a list of agent names."""

from ..database.mongodb import MongoDB
from ...logging_config import logger


class AgentRoster:
    """Simple roster that stores agent names in MongoDB."""

    _ROSTER_ID = "main"  # Fixed ID for the single roster document

    def __init__(self):
        self._mongodb = MongoDB.get_instance()
        self._collection = self._mongodb.get_collection_by_name("agent_roster")
        self._ensure_indexes()
        self.load()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Index for roster_id lookup
            self._collection.create_index([("roster_id", 1)], unique=True)
        except Exception as exc:
            logger.warning(
                "Agent roster index creation failed",
                extra={"error": str(exc)},
            )

    def load(self) -> None:
        """Load agent names from MongoDB."""
        try:
            doc = self._collection.find_one({"roster_id": self._ROSTER_ID})
            if doc is not None:
                agents = doc.get("agents", [])
                self._agents = [str(name) for name in agents if name]
            else:
                self._agents = []
                self.save()
        except Exception as exc:
            logger.warning(
                "Failed to load agent roster",
                extra={"error": str(exc)},
            )
            self._agents = []

    def save(self) -> None:
        """Save agent names to MongoDB."""
        try:
            self._collection.update_one(
                {"roster_id": self._ROSTER_ID},
                {"$set": {"agents": self._agents}},
                upsert=True,
            )
        except Exception as exc:
            logger.warning(
                "Failed to save agent roster",
                extra={"error": str(exc)},
            )

    def add_agent(self, agent_name: str) -> None:
        """Add an agent to the roster if not already present."""
        if agent_name not in self._agents:
            self._agents.append(agent_name)
            self.save()

    def get_agents(self) -> list[str]:
        """Get list of all agent names."""
        return list(self._agents)

    def clear(self) -> None:
        """Clear the agent roster."""
        self._agents = []
        try:
            self._collection.delete_one({"roster_id": self._ROSTER_ID})
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
