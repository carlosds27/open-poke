import logging
from server.services.execution import get_agent_roster
from server.agents.execution_agent.tools.prompt import get_tool_prompts
from server.agents.execution_agent.tools.registry import get_tools

logger = logging.getLogger(__name__)

class ToolState:
    """State of the agent's tools."""
    def __init__(self):
        self.agent_roster = get_agent_roster()
        self.tool_prompts = get_tool_prompts()
        self.tools_dict = get_tools()

    def get_prompt_to_fetch_tool(self, tool_name: str) -> str:
        """Get the prompt to fetch the tool."""
        tool_description = self.tools_dict.get(tool_name, {}).get("description", "")
        return f"This agent has access to {tool_name}. Tool description: {tool_description}. To get full access to this tool, call get_{tool_name} function."

    async def get_tool_prompt_for_agent(self, agent_name: str) -> str:
        """Get the prompt for an agent."""
        final_prompt = ""
        agent_tool_state = await self.get_tool_state(agent_name)
        for tool_name in self.tools_dict:
            if tool_name in agent_tool_state:
                tool_prompt = self.tool_prompts.get(tool_name, "")
                tool_prompt = tool_prompt.strip()
                final_prompt += f"\n{tool_prompt}\n"
            else:
                tool_prompt = self.get_prompt_to_fetch_tool(tool_name)
                tool_prompt = tool_prompt.strip()
                final_prompt += f"\n{tool_prompt}\n"
        return final_prompt

    async def get_tool_state(self, agent_name: str) -> list:
        """Get the tool state for an agent."""
        tool_state = await self.agent_roster.get_agent_tool_state(agent_name)
        if tool_state:
            return tool_state
        else:
            return []

    async def set_tool_state(self, agent_name: str, tool_state: list) -> None:
        """Set the tool state for an agent."""
        try:
            await self.agent_roster.set_agent_tool_state(agent_name, tool_state)
            logger.info(f"Set tool state for {agent_name}: {', '.join(tool_state)}")
        except Exception as exc:
            logger.warning(
                "Failed to set tool state",
                extra={"error": str(exc), "agent_name": agent_name},
            )

_tool_state = ToolState()

def get_tool_state() -> ToolState:
    """Get the tool state for the execution agent."""
    return _tool_state