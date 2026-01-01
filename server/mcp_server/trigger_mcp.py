from typing import Annotated, Optional, Dict, Any
import json
from server.mcp_server.base import OpenPokeMCP
from server.services.triggers import get_trigger_service, TriggerRecord
from server.services.execution import get_execution_agent_logs
from server.utils.timezones import format_datetime_for_mcp, parse_datetime_from_mcp
from datetime import datetime

_TRIGGER_SERVICE = get_trigger_service()
_LOG_STORE = get_execution_agent_logs()

mcp = OpenPokeMCP(
    name="trigger_mcp", 
    version="1.0.0", 
    instructions="This server provides all the necessary tools related to triggers.",
    debug=False,
    log_level="INFO",
)


async def _trigger_record_to_payload(record: TriggerRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "payload": record.payload,
        "start_time": format_datetime_for_mcp(record.start_time) if isinstance(record.start_time, datetime) else record.start_time,
        "next_trigger": format_datetime_for_mcp(record.next_trigger) if isinstance(record.next_trigger, datetime) else record.next_trigger,
        "recurrence_rule": record.recurrence_rule,
        "timezone": record.timezone,
        "status": record.status,
        "last_error": record.last_error,
        "created_at": format_datetime_for_mcp(record.created_at) if isinstance(record.created_at, datetime) else str(record.created_at),
        "updated_at": format_datetime_for_mcp(record.updated_at) if isinstance(record.updated_at, datetime) else str(record.updated_at),
    }

@mcp.tool(name="createTrigger")
async def create_trigger(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    payload: Annotated[str, "Raw instruction text that should run when the trigger fires."], 
    recurrence_rule: Annotated[Optional[str], "iCalendar RRULE string describing how often to fire (optional)."], 
    start_time: Annotated[Optional[str], "Start time in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone). Defaults to now if omitted."], 
    status: Annotated[Optional[str], "Initial status; usually 'active' or 'paused'."],
) -> dict:
    """Create a reminder trigger for the current execution agent."""
    summary_args = {
        "recurrence_rule": recurrence_rule,
        "start_time": start_time,
        "status": status,
    }
    try:
        start_time_dt = parse_datetime_from_mcp(start_time) if start_time else None
        record = _TRIGGER_SERVICE.create_trigger(
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time_dt,
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
    return await _trigger_record_to_payload(record)

@mcp.tool(name="updateTrigger")
async def update_trigger(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    trigger_id: Annotated[int, "Identifier returned when the trigger was created."],
    payload: Annotated[Optional[str], "Replace the instruction payload (optional)."],
    recurrence_rule: Annotated[Optional[str], "New RRULE definition (optional)."],
    start_time: Annotated[Optional[str], "New start time in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone, optional)."],
    status: Annotated[Optional[str], "Set trigger status to 'active', 'paused', or 'completed'."],
) -> dict:
    """Update or pause an existing trigger owned by this execution agent."""
    try:
        trigger_id_int = int(trigger_id)
    except (TypeError, ValueError):
        return {"error": "trigger_id must be an integer"}
    try:
        start_time_dt = parse_datetime_from_mcp(start_time) if start_time else None
        record = _TRIGGER_SERVICE.update_trigger(
            trigger_id_int,
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time_dt,
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

    return await _trigger_record_to_payload(record)

@mcp.tool(name="listTriggers")
async def list_triggers(
    agent_name: Annotated[Optional[str], "Leave this blank."],
) -> dict:
    """List all triggers belonging to this execution agent."""
    try:
        print(f"Listing triggers for agent {agent_name}")
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
    import uvicorn
    mcp_server = mcp.http_app(path="/triggers/mcp")
    uvicorn.run(mcp_server, host="0.0.0.0", port=9141)