from typing import Annotated, Optional, Dict, Any
import json
from datetime import datetime
from server.mcp_server.base import OpenPokeMCP
from server.services.bookkeeping import get_bookkeeping_service, BookkeepingRecord
from server.services.execution import get_execution_agent_logs
from server.utils.timezones import format_datetime_for_mcp, parse_datetime_from_mcp

_BOOKKEEPING_SERVICE = get_bookkeeping_service()
_LOG_STORE = get_execution_agent_logs()

mcp = OpenPokeMCP(
    name="bookkeeping_mcp", 
    version="1.0.0", 
    instructions="This server provides all the necessary tools related to bookkeeping and expense tracking. You can create, update, delete, and list financial records (both income and expenses), get expense summaries, and generate cashflow reports.",
    debug=False,
    log_level="INFO",
)


async def _bookkeeping_record_to_payload(record: BookkeepingRecord) -> Dict[str, Any]:
    """Convert BookkeepingRecord to payload, ensuring datetime fields are in user timezone."""
    # Record datetime fields are already in user timezone from the service/store
    return {
        "id": record.id,
        "record_type": record.record_type,
        "amount": record.amount,
        "category": record.category,
        "description": record.description,
        "date": format_datetime_for_mcp(record.date) if isinstance(record.date, datetime) else str(record.date),
        "created_at": format_datetime_for_mcp(record.created_at) if isinstance(record.created_at, datetime) else str(record.created_at),
        "updated_at": format_datetime_for_mcp(record.updated_at) if isinstance(record.updated_at, datetime) else str(record.updated_at),
    }


@mcp.tool(name="createRecord")
async def create_record(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    record_type: Annotated[str, "Type of record: 'income' or 'expense'."],
    amount: Annotated[float, "Amount of money (must be positive)."],
    category: Annotated[str, "Category of the record (e.g., 'food', 'grocery', 'gift', 'salary', 'freelance', etc.)."],
    description: Annotated[Optional[str], "Optional description of the record."],
    date: Annotated[Optional[str], "Date in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone). Defaults to today if omitted."],
) -> dict:
    """Create a new bookkeeping record (income or expense)."""
    summary_args = {
        "record_type": record_type,
        "amount": amount,
        "category": category,
        "description": description,
        "date": date,
    }
    try:
        date_dt = parse_datetime_from_mcp(date) if date else None
        record = _BOOKKEEPING_SERVICE.create_record(
            record_type=record_type,
            amount=amount,
            category=category,
            description=description,
            date=date_dt,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"createRecord failed | details={json.dumps(summary_args, ensure_ascii=False)} | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"createRecord succeeded | record_id={record.id} | type={record_type} | amount={amount} | category={category}",
    )
    return await _bookkeeping_record_to_payload(record)


@mcp.tool(name="updateRecord")
async def update_record(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    record_id: Annotated[int, "Identifier returned when the record was created."],
    record_type: Annotated[Optional[str], "Update the record type to 'income' or 'expense' (optional)."],
    amount: Annotated[Optional[float], "Update the amount (optional, must be positive)."],
    category: Annotated[Optional[str], "Update the category (optional)."],
    description: Annotated[Optional[str], "Update the description (optional)."],
    date: Annotated[Optional[str], "Update the date in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone, optional)."],
) -> dict:
    """Update an existing bookkeeping record."""
    try:
        record_id_int = int(record_id)
    except (TypeError, ValueError):
        return {"error": "record_id must be an integer"}
    try:
        date_dt = parse_datetime_from_mcp(date) if date else None
        record = _BOOKKEEPING_SERVICE.update_record(
            record_id_int,
            record_type=record_type,
            amount=amount,
            category=category,
            description=description,
            date=date_dt,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"updateRecord failed | id={record_id_int} | error={exc}",
        )
        return {"error": str(exc)}
    
    if record is None:
        return {"error": f"Record {record_id_int} not found"}

    _LOG_STORE.record_action(
        agent_name,
        description=f"updateRecord succeeded | record_id={record_id_int}",
    )

    return await _bookkeeping_record_to_payload(record)


@mcp.tool(name="deleteRecord")
async def delete_record(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    record_id: Annotated[int, "Identifier of the record to delete."],
) -> dict:
    """Delete a bookkeeping record."""
    try:
        record_id_int = int(record_id)
    except (TypeError, ValueError):
        return {"error": "record_id must be an integer"}
    try:
        success = _BOOKKEEPING_SERVICE.delete_record(
            record_id_int,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"deleteRecord failed | id={record_id_int} | error={exc}",
        )
        return {"error": str(exc)}
    
    if not success:
        return {"error": f"Record {record_id_int} not found or could not be deleted"}

    _LOG_STORE.record_action(
        agent_name,
        description=f"deleteRecord succeeded | record_id={record_id_int}",
    )

    return {
        "success": True,
        "record_id": record_id_int,
    }


@mcp.tool(name="listRecords")
async def list_records(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    record_type: Annotated[Optional[str], "Filter by record type: 'income' or 'expense' (optional)."],
    start_date: Annotated[Optional[str], "Filter records from this date in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone, optional)."],
    end_date: Annotated[Optional[str], "Filter records until this date in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone, optional)."],
    category: Annotated[Optional[str], "Filter by category (optional)."],
) -> dict:
    """List all bookkeeping records with optional filters."""
    try:
        start_date_dt = parse_datetime_from_mcp(start_date) if start_date else None
        end_date_dt = parse_datetime_from_mcp(end_date) if end_date else None
        records = _BOOKKEEPING_SERVICE.list_records(
            record_type=record_type,
            start_date=start_date_dt,
            end_date=end_date_dt,
            category=category,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"listRecords failed | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"listRecords succeeded | count={len(records)}",
    )
    return {"records": [await _bookkeeping_record_to_payload(record) for record in records]}


@mcp.tool(name="getExpenseSummary")
async def get_expense_summary(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    start_date: Annotated[str, "Start date for the summary period in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone)."],
    end_date: Annotated[str, "End date for the summary period in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone)."],
    category: Annotated[Optional[str], "Filter by specific category (optional)."],
) -> dict:
    """Get a summary of expenses for a specific time period."""
    try:
        start_date_dt = parse_datetime_from_mcp(start_date) if start_date else None
        end_date_dt = parse_datetime_from_mcp(end_date) if end_date else None
        summary = _BOOKKEEPING_SERVICE.get_expense_summary(
            start_date=start_date_dt,
            end_date=end_date_dt,
            category=category,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"getExpenseSummary failed | start_date={start_date} | end_date={end_date} | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"getExpenseSummary succeeded | start_date={start_date} | end_date={end_date}",
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_amount": summary.get("total_amount", 0.0),
        "record_count": summary.get("record_count", 0),
        "by_category": summary.get("by_category", {}),
    }


@mcp.tool(name="getCashflow")
async def get_cashflow(
    agent_name: Annotated[Optional[str], "Leave this blank."],
    start_date: Annotated[str, "Start date for the cashflow period in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone)."],
    end_date: Annotated[str, "End date for the cashflow period in YYYY-MM-DD HH:MM:SS format (interpreted in user's timezone)."],
) -> dict:
    """Get cashflow report (income vs expenses) for a specific time period."""
    try:
        cashflow = _BOOKKEEPING_SERVICE.get_cashflow(
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"getCashflow failed | start_date={start_date} | end_date={end_date} | error={exc}",
        )
        return {"error": str(exc)}
    _LOG_STORE.record_action(
        agent_name,
        description=f"getCashflow succeeded | start_date={start_date} | end_date={end_date}",
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income": cashflow.get("total_income", 0.0),
        "total_expense": cashflow.get("total_expense", 0.0),
        "net_cashflow": cashflow.get("net_cashflow", 0.0),
        "income_count": cashflow.get("income_count", 0),
        "expense_count": cashflow.get("expense_count", 0),
    }


if __name__ == "__main__":
    import uvicorn
    mcp_server = mcp.http_app(path="/bookkeeping/mcp")
    uvicorn.run(mcp_server, host="0.0.0.0", port=9142)

