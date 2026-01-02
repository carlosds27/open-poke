GMAIL_TOOL_PROMPT = """
You have access to the following Gmail tools:
- gmail_create_draft: Create an email draft
- gmail_execute_draft: Send a previously created draft
- gmail_forward_email: Forward an existing email
- gmail_reply_to_thread: Reply to an email thread
"""

TRIGGER_TOOL_PROMPT = """
You also manage reminder triggers for this agent:
- createTrigger: Store a reminder by providing the payload to run later. Supply `start_time` and an iCalendar `RRULE` when recurrence is needed.
- updateTrigger: Change an existing trigger (use `status="paused"` to cancel or `status="active"` to resume).
- listTriggers: Inspect all triggers assigned to this agent.
"""

BOOKKEEPING_TOOL_PROMPT = """
You have access to the following bookkeeping tools:
- createRecord: Create a new bookkeeping record (income or expense). Use general categories (e.g., "food", "transportation", "entertainment", "salary", "freelance") rather than specific ones, as there will be many distinct categories later on.
- updateRecord: Update an existing bookkeeping record by ID.
- deleteRecord: Delete a bookkeeping record by ID.
- listRecords: List all bookkeeping records with optional filters (record_type, date range, category).
- getExpenseSummary: Get a summary of expenses for a specific time period, including total amount, record count, and breakdown by category.
- getCashflow: Get cashflow report (income vs expenses) for a specific time period, including net cashflow and counts.

IMPORTANT: When creating or updating records, always use general, high-level categories (e.g., "food", "transportation", "utilities", "salary", "freelance") rather than specific or detailed categories. This ensures consistency as the number of distinct categories grows over time.
"""

PERPLEXITY_TOOL_PROMPT = """
You have access to the following perplexity tools:
- search: Search the internet for information. Use this tool by default for basic questions and most queries. This tool provides a standard level of detail suitable for most information needs.
- deep_search: Search the internet with a deeper level of detail. Only use this tool if the instructions explicitly require deep search, more detailed search, or if an initial normal search did not provide sufficient information.

IMPORTANT: Use highly specific queries for more targeted results. For example, instead of searching for “AI”, use a detailed query like “artificial intelligence machine learning healthcare applications 2024”. Specific queries with context, time frames, and precise terminology yield more relevant and actionable results.
"""

TOOL_PROMPTS = {
    "gmail_tool": GMAIL_TOOL_PROMPT,
    "trigger_tool": TRIGGER_TOOL_PROMPT,
    "bookkeeping_tool": BOOKKEEPING_TOOL_PROMPT,
    "perplexity_tool": PERPLEXITY_TOOL_PROMPT,
}

def get_tool_prompts() -> dict:
    """Get the tool prompts for the execution agent."""
    return TOOL_PROMPTS