from typing import Annotated, Optional, List, Dict, Any
from fastmcp import FastMCP
import json
from server.services.execution import get_execution_agent_logs
from server.services.gmail import execute_gmail_tool, get_active_gmail_user_id
from server.agents.execution_agent.tasks.search_email.tool import task_email_search

_GMAIL_AGENT_NAME = "gmail-execution-agent"
_LOG_STORE = get_execution_agent_logs()

mcp = FastMCP(
    name="gmail_mcp",
    version="1.0.0",
    instructions="This server provides all the necessary tools related to Gmail operations.",
)

async def _execute_gmail_tool(tool_name: str, composio_user_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Gmail tool and record the action for the execution agent journal."""

    payload = {k: v for k, v in arguments.items() if v is not None}
    payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else "{}"
    try:
        result = execute_gmail_tool(tool_name, composio_user_id, arguments=payload)
    except Exception as exc:
        _LOG_STORE.record_action(
            _GMAIL_AGENT_NAME,
            description=f"{tool_name} failed | args={payload_str} | error={exc}",
        )
        return {"error": str(exc)}

    _LOG_STORE.record_action(
        _GMAIL_AGENT_NAME,
        description=f"{tool_name} succeeded | args={payload_str}",
    )
    return result

@mcp.tool(name="gmail_create_draft")
async def gmail_create_draft(
    recipient_email: Annotated[str, "Primary recipient email for the draft."],
    subject: Annotated[str, "Email subject."],
    body: Annotated[str, "Email body. Use HTML markup when is_html is true."],
    cc: Annotated[Optional[List[str]], "Optional list of CC recipient emails."] = None,
    bcc: Annotated[Optional[List[str]], "Optional list of BCC recipient emails."] = None,
    extra_recipients: Annotated[Optional[List[str]], "Additional recipients if the draft should include more addresses."] = None,
    is_html: Annotated[Optional[bool], "Set true when the body contains HTML content."] = None,
    thread_id: Annotated[Optional[str], "Existing Gmail thread id if this draft belongs to a thread."] = None,
    attachment: Annotated[Optional[Dict[str, Any]], "Single attachment metadata (requires Composio-uploaded asset)."] = None,
) -> dict:
    """Create a Gmail draft via Composio, supporting html/plain bodies, cc/bcc, and attachments."""
    arguments: Dict[str, Any] = {
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "cc": cc,
        "bcc": bcc,
        "extra_recipients": extra_recipients,
        "is_html": is_html,
        "thread_id": thread_id,
        "attachment": attachment,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_CREATE_EMAIL_DRAFT", composio_user_id, arguments)


@mcp.tool(name="gmail_execute_draft")
async def gmail_execute_draft(
    draft_id: Annotated[str, "Identifier of the Gmail draft to send."],
) -> dict:
    """Send a previously created Gmail draft using Composio."""
    arguments: Dict[str, Any] = {
        "draft_id": draft_id,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_SEND_DRAFT", composio_user_id, arguments)


@mcp.tool(name="gmail_forward_email")
async def gmail_forward_email(
    message_id: Annotated[str, "Gmail message id to forward."],
    recipient_email: Annotated[str, "Email address to receive the forwarded message."],
    additional_text: Annotated[Optional[str], "Optional text to prepend when forwarding."] = None,
) -> dict:
    """Forward an existing Gmail message with optional additional context."""
    arguments: Dict[str, Any] = {
        "message_id": message_id,
        "recipient_email": recipient_email,
        "additional_text": additional_text,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_FORWARD_MESSAGE", composio_user_id, arguments)


@mcp.tool(name="gmail_reply_to_thread")
async def gmail_reply_to_thread(
    thread_id: Annotated[str, "Gmail thread id to reply to."],
    recipient_email: Annotated[str, "Primary recipient for the reply (usually the original sender)."],
    message_body: Annotated[str, "Reply body. Use HTML markup when is_html is true."],
    cc: Annotated[Optional[List[str]], "Optional list of CC recipient emails."] = None,
    bcc: Annotated[Optional[List[str]], "Optional list of BCC recipient emails."] = None,
    extra_recipients: Annotated[Optional[List[str]], "Additional recipients if needed."] = None,
    is_html: Annotated[Optional[bool], "Set true when the body contains HTML content."] = None,
    attachment: Annotated[Optional[Dict[str, Any]], "Single attachment metadata (requires Composio-uploaded asset)."] = None,
) -> dict:
    """Send a reply within an existing Gmail thread via Composio."""
    arguments: Dict[str, Any] = {
        "thread_id": thread_id,
        "recipient_email": recipient_email,
        "message_body": message_body,
        "cc": cc,
        "bcc": bcc,
        "extra_recipients": extra_recipients,
        "is_html": is_html,
        "attachment": attachment,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_REPLY_TO_THREAD", composio_user_id, arguments)



@mcp.tool(name="gmail_delete_draft")
async def gmail_delete_draft(
    draft_id: Annotated[str, "Identifier of the Gmail draft to delete."],
) -> dict:
    """Delete a specific Gmail draft using the Composio Gmail integration."""
    arguments: Dict[str, Any] = {
        "draft_id": draft_id,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_DELETE_DRAFT", composio_user_id, arguments)



@mcp.tool(name="gmail_get_contacts")
async def gmail_get_contacts(
    resource_name: Annotated[Optional[str], "Resource name to read contacts from, defaults to people/me."] = None,
    person_fields: Annotated[Optional[str], "Comma-separated People API fields to include (e.g. emailAddresses,names)."] = None,
    include_other_contacts: Annotated[Optional[bool], "Include other contacts (directory suggestions) when true."] = None,
    page_token: Annotated[Optional[str], "Pagination token for retrieving the next page of contacts."] = None,
) -> dict:
    """Retrieve Google contacts (connections) available to the authenticated Gmail account."""
    arguments: Dict[str, Any] = {
        "resource_name": resource_name,
        "person_fields": person_fields,
        "include_other_contacts": include_other_contacts,
        "page_token": page_token,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_GET_CONTACTS", composio_user_id, arguments)



@mcp.tool(name="gmail_get_people")
async def gmail_get_people(
    resource_name: Annotated[Optional[str], "Resource name to fetch (defaults to people/me)."] = None,
    person_fields: Annotated[Optional[str], "Comma-separated People API fields to include in the response."] = None,
    page_size: Annotated[Optional[int], "Maximum number of people records to return per page."] = None,
    page_token: Annotated[Optional[str], "Token to continue fetching the next set of results."] = None,
    sync_token: Annotated[Optional[str], "Sync token for incremental sync requests."] = None,
    other_contacts: Annotated[Optional[bool], "Set true to list other contacts instead of connections."] = None,
) -> dict:
    """Retrieve detailed Google People records or other contacts via Composio."""
    arguments: Dict[str, Any] = {
        "resource_name": resource_name,
        "person_fields": person_fields,
        "page_size": page_size,
        "page_token": page_token,
        "sync_token": sync_token,
        "other_contacts": other_contacts,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_GET_PEOPLE", composio_user_id, arguments)



@mcp.tool(name="gmail_list_drafts")
async def gmail_list_drafts(
    max_results: Annotated[Optional[int], "Maximum number of drafts to return."] = None,
    page_token: Annotated[Optional[str], "Pagination token from a previous drafts list call."] = None,
    verbose: Annotated[Optional[bool], "Include full draft details such as subject and body when true."] = None,
) -> dict:
    """List Gmail drafts for the connected account using Composio."""
    arguments: Dict[str, Any] = {
        "max_results": max_results,
        "page_token": page_token,
        "verbose": verbose,
    }
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_LIST_DRAFTS", composio_user_id, arguments)



@mcp.tool(name="gmail_search_people")
async def gmail_search_people(
    query: Annotated[str, "Search query to match against names, emails, phone numbers, etc."],
    person_fields: Annotated[Optional[str], "Comma-separated fields from the People API to include in results."] = None,
    page_size: Annotated[Optional[int], "Maximum number of people records to return."] = None,
    other_contacts: Annotated[Optional[bool], "Include other contacts results when true."] = None,
    page_token: Annotated[Optional[str], "Pagination token to continue a previous search."] = None,
) -> dict:
    """Search Google contacts and other people records associated with the Gmail account."""
    arguments: Dict[str, Any] = {
        "query": query,
        "person_fields": person_fields,
        "other_contacts": other_contacts,
    }
    if page_size is not None:
        arguments["pageSize"] = page_size
    if page_token is not None:
        arguments["pageToken"] = page_token
    composio_user_id = get_active_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return await _execute_gmail_tool("GMAIL_SEARCH_PEOPLE", composio_user_id, arguments)



@mcp.tool(name="task_email_search")
async def task_email_search_mcp(
    search_query: Annotated[str, "Raw search request describing the emails to find."],
) -> dict:
    """Expand a raw Gmail search request into multiple targeted queries and return relevant emails."""
    return await task_email_search(search_query)

if __name__ == "__main__":
    import uvicorn

    mcp_server = mcp.http_app(path="/gmail/mcp")
    uvicorn.run(mcp_server, host="0.0.0.0", port=9142)
