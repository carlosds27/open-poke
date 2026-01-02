"""Simplified Execution Agent Runtime."""

import inspect
import json
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass

from .agent import ExecutionAgent
from .tools import get_tools
from .tools.state import get_tool_state
from ...config import get_settings
from ...openrouter_client import request_chat_completion
from ...logging_config import logger
from .mcp_client import (
    SimpleMCPClient,
    convert_mcp_tool_to_tool_schema,
    convert_mcp_tool_result_to_dict,
)

_TOOL_STATE = get_tool_state()

@dataclass
class ExecutionResult:
    """Result from an execution agent."""

    agent_name: str
    success: bool
    response: str
    error: Optional[str] = None
    tools_executed: List[str] = None


class ExecutionAgentRuntime:
    """Manages the execution of a single agent request."""

    MAX_TOOL_ITERATIONS = 8

    # Initialize execution agent runtime with settings, tools, and agent instance
    def __init__(self, agent_name: str):
        settings = get_settings()
        self.agent = ExecutionAgent(agent_name)
        self.api_key = settings.openrouter_api_key
        self.model = settings.execution_agent_model
        # There will be 3 types of tools:
        self.tools_dict = get_tools()
        self.tool_state = [] # Keep track of the tools that is expanded
        self.tool_schemas: Dict[str, List[Dict[str, Any]]] = {} # Keep track of the tool schemas for each tool_name
        # 1. MCP tools
        self.mcp_tools: List[str] = [] # Keep track of the tool_name that is an MCP tool
        self.tool_name_to_mcp_client: Dict[str, SimpleMCPClient] = {} # Keep track of the MCP client for each tool_name
        # 2. Direct tools
        self.app_tools: List[str] = [] # Keep track of the tool_name that is an app tool
        self.tool_name_to_app_tool: Dict[str, Callable[..., Any]] = {} # Keep track of the function for each tool_name
        # 3. Unexpanded tools
        self.unexpanded_tools: Dict[str, str] = {} # Keep track of the tool_name that is an unexpanded tool and the function name
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable."
            )
        self.system_prompt = ""

    async def initialize(self) -> None:
        """Initialize the execution agent runtime."""
        await self._get_tool_state()
        await self._identify_tools()
        await self._init_tool_schema()

    async def _get_tool_state(self) -> None:
        """Get the tool state for the agent."""
        self.tool_state = await _TOOL_STATE.get_tool_state(self.agent.name)

    async def _identify_tools(self) -> None:
        """Identify the requested tools. Whether they are MCP tools or app tools."""
        for tool_name in self.tools_dict.keys():
            # Check if in App first
            if tool_name in self.tools_dict:
                if self.tools_dict[tool_name]["type"] == "func":
                    self.app_tools.append(tool_name)
                elif self.tools_dict[tool_name]["type"] == "mcp":
                    self.mcp_tools.append(tool_name)
            else:
                logger.warning(f"[{self.agent.name}] Unknown tool: {tool_name}")

    # Main execution loop for running agent with LLM calls and tool execution
    async def execute(self, instructions: str) -> ExecutionResult:
        """Execute the agent with given instructions."""
        try:
            # Build system prompt with history
            self.system_prompt = await self.agent.build_system_prompt_with_history()

            # Start conversation with the instruction
            messages = [{"role": "user", "content": instructions}]
            tools_executed: List[str] = []
            final_response: Optional[str] = None

            for iteration in range(self.MAX_TOOL_ITERATIONS):
                logger.info(
                    f"[{self.agent.name}] Requesting plan (iteration {iteration + 1})"
                )
                response = await self._make_llm_call(
                    self.system_prompt, messages, with_tools=True
                )
                assistant_message = response.get("choices", [{}])[0].get("message", {})

                if not assistant_message:
                    raise RuntimeError(
                        "LLM response did not include an assistant message"
                    )

                raw_tool_calls = assistant_message.get("tool_calls", []) or []
                parsed_tool_calls = self._extract_tool_calls(raw_tool_calls)

                assistant_entry: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_message.get("content", "") or "",
                }
                if raw_tool_calls:
                    assistant_entry["tool_calls"] = raw_tool_calls
                messages.append(assistant_entry)

                if not parsed_tool_calls:
                    final_response = assistant_entry["content"] or "No action required."
                    break

                for tool_call in parsed_tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("arguments", {})
                    call_id = tool_call.get("id")

                    if not tool_name:
                        logger.warning("Tool call missing name: %s", tool_call)
                        failure = {
                            "error": "Tool call missing name; unable to execute."
                        }
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": call_id or "unknown_tool",
                            "content": self._format_tool_result(
                                tool_name or "<unknown>", False, failure, tool_args
                            ),
                        }
                        messages.append(tool_message)
                        continue

                    tools_executed.append(tool_name)
                    logger.info(f"[{self.agent.name}] Executing tool: {tool_name}")

                    success, result = await self._execute_tool(tool_name, tool_args)

                    if success:
                        logger.info(
                            f"[{self.agent.name}] Tool {tool_name} completed successfully"
                        )
                        record_payload = self._safe_json_dump(result)
                    else:
                        error_detail = (
                            result.get("error")
                            if isinstance(result, dict)
                            else str(result)
                        )
                        logger.warning(
                            f"[{self.agent.name}] Tool {tool_name} failed: {error_detail}"
                        )
                        record_payload = error_detail

                    self.agent.record_tool_execution(
                        tool_name, self._safe_json_dump(tool_args), record_payload
                    )

                    tool_message = {
                        "role": "tool",
                        "tool_call_id": call_id or tool_name,
                        "content": self._format_tool_result(
                            tool_name, success, result, tool_args
                        ),
                    }
                    messages.append(tool_message)

            else:
                raise RuntimeError(
                    "Reached tool iteration limit without final response"
                )

            if final_response is None:
                raise RuntimeError("LLM did not return a final response")

            self.agent.record_response(final_response)

            return ExecutionResult(
                agent_name=self.agent.name,
                success=True,
                response=final_response,
                tools_executed=tools_executed,
            )

        except Exception as e:
            logger.error(f"[{self.agent.name}] Execution failed: {e}")
            error_msg = str(e)
            failure_text = f"Failed to complete task: {error_msg}"
            self.agent.record_response(f"Error: {error_msg}")

            return ExecutionResult(
                agent_name=self.agent.name,
                success=False,
                response=failure_text,
                error=error_msg,
            )

    # Execute OpenRouter API call with system prompt, messages, and optional tool schemas
    def _expand_tool_schemas(self) -> List[Dict[str, Any]]:
        """Expand the tool schema for the agent."""
        expanded_tool_schemas = []
        for tool_name in self.tool_schemas.keys():
            expanded_tool_schemas.extend(self.tool_schemas[tool_name])
        return expanded_tool_schemas

    async def _make_llm_call(
        self, system_prompt: str, messages: List[Dict], with_tools: bool
    ) -> Dict:
        """Make an LLM call."""
        tools_to_send = self._expand_tool_schemas() if with_tools else None
        logger.info(
            f"[{self.agent.name}] Calling LLM with model: {self.model}, tools: {len(tools_to_send) if tools_to_send else 0}"
        )
        return await request_chat_completion(
            model=self.model,
            messages=messages,
            system=system_prompt,
            api_key=self.api_key,
            tools=tools_to_send,
        )

    # Parse and validate tool calls from LLM response into structured format
    def _extract_tool_calls(
        self, raw_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract tool calls from an assistant message."""
        tool_calls: List[Dict[str, Any]] = []

        for tool in raw_tools:
            function = tool.get("function", {})
            name = function.get("name", "")
            args = function.get("arguments", "")

            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {}

            if name:
                tool_calls.append(
                    {
                        "id": tool.get("id"),
                        "name": name,
                        "arguments": args,
                    }
                )

        return tool_calls

    # Safely convert objects to JSON with fallback to string representation
    def _safe_json_dump(self, payload: Any) -> str:
        """Serialize payload to JSON, falling back to string representation."""
        try:
            return json.dumps(payload, default=str)
        except TypeError:
            return str(payload)

    # Format tool execution results into JSON structure for LLM consumption
    def _format_tool_result(
        self,
        tool_name: str,
        success: bool,
        result: Any,
        arguments: Dict[str, Any],
    ) -> str:
        """Build a structured string for tool responses."""
        if success:
            payload: Dict[str, Any] = {
                "tool": tool_name,
                "status": "success",
                "arguments": arguments,
                "result": result,
            }
        else:
            error_detail = (
                result.get("error") if isinstance(result, dict) else str(result)
            )
            payload = {
                "tool": tool_name,
                "status": "error",
                "arguments": arguments,
                "error": error_detail,
            }
        return self._safe_json_dump(payload)

    async def _expanded_tool_schema(self, tool_name: str) -> List[Dict[str, Any]]:
        """Initialize the expanded tool schemas."""
        if tool_name in self.app_tools:
            tool_schema = self.tools_dict[tool_name]["schema"]
            tool_registry = self.tools_dict[tool_name]["registry"]
            self.tool_name_to_app_tool.update(tool_registry)
            return tool_schema
        elif tool_name in self.mcp_tools:
            mcp_url = self.tools_dict[tool_name]["url"]
            client = SimpleMCPClient(mcp_url=mcp_url, agent_name=self.agent.name)
            await client.connect()
            tools = client.get_tools()
            tool_schemas = []
            for tool in tools:
                tool_name = tool.name
                tool_schema = await convert_mcp_tool_to_tool_schema(tool)
                tool_schemas.append(tool_schema)
                self.tool_name_to_mcp_client[tool_name] = client
            return tool_schemas
        else:
            logger.warning(f"[{self.agent.name}] Unknown tool: {tool_name}")
            return []

    async def _unexpanded_tool_schema(self, tool_name: str) -> List[Dict[str, Any]]:
        """Initialize the unexpanded tool schema."""
        tool_schema = {
            "type": "function",
            "function": {
                "name": f"get_{tool_name}",
                "description": f"Get the {tool_name} tool. To get full access to this tool, call this function.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        }
        return [tool_schema]

    async def _init_tool_schema_helper(self, tool_name: str) -> None:
        """Initialize the tool schema for the agent."""
        if tool_name in self.tool_state:
            tool_schemas = await self._expanded_tool_schema(tool_name)
            self.tool_schemas[tool_name] = tool_schemas
        else:
            tool_schemas = await self._unexpanded_tool_schema(tool_name)
            self.tool_schemas[tool_name] = tool_schemas
            self.unexpanded_tools[f"get_{tool_name}"] = tool_name

    async def _init_tool_schema(self) -> None:
        """Initialize the tool schema for the agent."""
        for tool_name in self.tools_dict.keys():
            await self._init_tool_schema_helper(tool_name)

    async def _execute_tool(self, tool_name: str, arguments: Dict) -> Tuple[bool, Any]:
        """Execute a tool. Returns (success, result)."""
        if tool_name in self.tool_name_to_app_tool:
            return await self._execute_app_tool(tool_name, arguments)
        elif tool_name in self.tool_name_to_mcp_client:
            return await self._execute_mcp_tool(tool_name, arguments)
        elif tool_name in self.unexpanded_tools:
            return await self._execute_unexpanded_tool(tool_name)
        else:
            return False, {"error": f"Unknown tool: {tool_name}"}

    # Execute tool function from registry with error handling and async support
    async def _execute_app_tool(
        self, tool_name: str, arguments: Dict
    ) -> Tuple[bool, Any]:
        """Execute a tool. Returns (success, result)."""
        tool_func = self.tool_name_to_app_tool.get(tool_name)
        if not tool_func:
            return False, {"error": f"Unknown tool: {tool_name}"}

        try:
            result = tool_func(**arguments)
            if inspect.isawaitable(result):
                result = await result
            return True, result
        except Exception as e:
            return False, {"error": str(e)}

    # MCP Client functions
    async def _execute_mcp_tool(
        self, tool_name: str, arguments: Dict
    ) -> Tuple[bool, Any]:
        """Execute an MCP tool. Returns (success, result)."""
        try:
            mcp_client = self.tool_name_to_mcp_client.get(tool_name)
            if not mcp_client:
                return False, {"error": f"Unknown tool: {tool_name}"}

            result = await mcp_client.call_tool(tool_name, arguments)
            result_dict = await convert_mcp_tool_result_to_dict(result)
            if isinstance(result_dict, str) and "error" in result_dict.lower():
                return False, {"error": result_dict}
            elif isinstance(result_dict, dict) and "error" in result_dict:
                return False, {"error": result_dict["error"]}
            return True, result_dict
        except Exception as e:
            return False, {"error": str(e)}

    async def _execute_unexpanded_tool(self, tool_func_name: str) -> Tuple[bool, Any]:
        """Execute an unexpanded tool. Returns (success, result)."""
        logger.info(f"[EXPAND TOOL for {self.agent.name}] Executing unexpanded tool: {tool_func_name}")
        tool_name = self.unexpanded_tools[tool_func_name]
        try:
            # Append the tool to the tool state
            self.tool_state.append(tool_name)
            # Initialize the tool schema
            await self._init_tool_schema_helper(tool_name)
            # Set the tool state
            await _TOOL_STATE.set_tool_state(self.agent.name, self.tool_state)
            # Delete the unexpanded tool from the unexpanded tools dictionary
            del self.unexpanded_tools[tool_func_name]
            # Reload the system prompt
            self.system_prompt = await self.agent.build_system_prompt_with_history()
            # Return the result
            return True, {"message": f"Tool {tool_name} has been expanded and is now available."}
        except Exception as e:
            import traceback
            logger.error(f"[EXPAND TOOL for {self.agent.name}] Error executing unexpanded tool: {tool_func_name} - {traceback.format_exc()}")
            return False, {"error": str(e)}
        