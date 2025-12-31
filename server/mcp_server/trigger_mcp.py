from typing import Annotated, Optional, Dict, Any
import json
from server.mcp_server.base import OpenPokeMCP
from server.services.triggers import get_trigger_service, TriggerRecord
from server.services.timezone_store import get_timezone_store
from server.services.execution import get_execution_agent_logs

_TRIGGER_SERVICE = get_trigger_service()
_TIMEZONE_STORE = get_timezone_store()
_LOG_STORE = get_execution_agent_logs()

mcp = OpenPokeMCP(
    name="trigger_mcp", 
    version="1.0.0", 
    tags=["triggers"], 
    instructions="This server provides all the necessary tools related to triggers.",
    message_path="/triggers/messages/",
    streamable_http_path="/triggers/mcp/",
    debug=False,
    log_level="INFO",
)


async def _trigger_record_to_payload(record: TriggerRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "payload": record.payload,
        "start_time": record.start_time,
        "next_trigger": record.next_trigger,
        "recurrence_rule": record.recurrence_rule,
        "timezone": record.timezone,
        "status": record.status,
        "last_error": record.last_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }

@mcp.tool(name="createTrigger")
async def create_trigger(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    payload: Annotated[str, "Raw instruction text that should run when the trigger fires."], 
    recurrence_rule: Annotated[Optional[str], "iCalendar RRULE string describing how often to fire (optional)."], 
    start_time: Annotated[Optional[str], "ISO 8601 start time for the first firing. Defaults to now if omitted."], 
    status: Annotated[Optional[str], "Initial status; usually 'active' or 'paused'."],
) -> dict:
    """Create a reminder trigger for the current execution agent."""
    timezone_value = get_timezone_store().get_timezone()
    start_time = start_time.replace("Z", "") if start_time else None # LLM will always return a timestamp with a Z suffix
    summary_args = {
        "recurrence_rule": recurrence_rule,
        "start_time": start_time,
        "timezone": timezone_value,
        "status": status,
    }
    try:
        record = _TRIGGER_SERVICE.create_trigger(
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time,
            timezone_name=timezone_value,
            status=status,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"createTrigger failed | details={json.dumps(summary_args, ensure_ascii=False)} | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"createTrigger succeeded | trigger_id={record.id}",
    )
    return {
        "trigger_id": record.id,
        "status": record.status,
        "next_trigger": record.next_trigger,
        "start_time": record.start_time,
        "timezone": record.timezone,
        "recurrence_rule": record.recurrence_rule,
    }

@mcp.tool(name="updateTrigger")
async def update_trigger(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    trigger_id: Annotated[int, "Identifier returned when the trigger was created."],
    payload: Annotated[Optional[str], "Replace the instruction payload (optional)."],
    recurrence_rule: Annotated[Optional[str], "New RRULE definition (optional)."],
    start_time: Annotated[Optional[str], "New ISO 8601 start time for the schedule (optional)."],
    status: Annotated[Optional[str], "Set trigger status to 'active', 'paused', or 'completed'."],
) -> dict:
    """Update or pause an existing trigger owned by this execution agent."""
    try:
        trigger_id_int = int(trigger_id)
    except (TypeError, ValueError):
        return {"error": "trigger_id must be an integer"}
    try:
        timezone_value = get_timezone_store().get_timezone()
        start_time = start_time.replace("Z", "") if start_time else None # LLM will always return a timestamp with a Z suffix
        record = _TRIGGER_SERVICE.update_trigger(
            trigger_id_int,
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time,
            timezone_name=timezone_value,
            status=status,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"updateTrigger failed | id={trigger_id_int} | error={exc}",
        )
        return {"error": str(exc)}
    
    if record is None:
        return {"error": f"Trigger {trigger_id_int} not found"}

    _LOG_STORE.record_action(
        agent_name,
        description=f"updateTrigger succeeded | trigger_id={trigger_id_int}",
    )

    return {
        "trigger_id": record.id,
        "status": record.status,
        "next_trigger": record.next_trigger,
        "start_time": record.start_time,
        "timezone": record.timezone,
        "recurrence_rule": record.recurrence_rule,
        "last_error": record.last_error,
    }

@mcp.tool(name="listTriggers")
async def list_triggers(
    agent_name: Annotated[Optional[str], "Leave this blank."],
) -> dict:
    """List all triggers belonging to this execution agent."""
    try:
        record = _TRIGGER_SERVICE.list_triggers(
            agent_name=agent_name,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"listTriggers failed | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"listTriggers succeeded | count={len(record)}",
    )
    return {"triggers": [await _trigger_record_to_payload(record) for record in record]}

if __name__ == "__main__":
    mcp.run()