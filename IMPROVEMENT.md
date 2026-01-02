# Improvement Documentation

**Authored:** Carlos (saputracarlos@gmail.com)

---

## 🐛 Bugs

### 1. Search Email Task Doesn't End Properly

**Context:** The search email task runs in a loop, refining the search query in each iteration to better match the user's request. At the end of the search process, it should call the `return_search_results` tool to return the emails back to the execution agent for processing.

**Issue:** The search email task sometimes fails to call `return_search_results` at the end of the search. Instead, it stops making tool calls, which results in no emails being returned to the execution agent.

**Fix:** If there are email candidates and the task stops making tool calls, that typically indicates the search has ended. We now force the task to call the `return_search_results` tool to forward the appropriate emails to the execution agent.

---

### 2. Too Many Emails Fetched in `importance_watcher.py`

**Context:** The process runs every 1 minute to fetch 50 emails from the user's inbox.

**Issue:** The API returns excessive data when fetching 50 emails.

**Fix:** Reduced the number of emails fetched to 20.

---

### 3. Next.js Vulnerable Version

**Context:** Recently, there was a vulnerability discovered in many Next.js versions. This project uses `next:^14.2.7`.

**Issue:** Security vulnerability detected.

**Fix:** Updated the version of Next.js to `next:14.2.35` (patched version).

---

### 4. Datetime Format

**Context:** The app currently uses ISO datetime format for Triggers. The app also requires the agent to use ISO format in tool parameters.

**Issue:** When storing ISO datetime in MongoDB, it's stored as a string. When computing `next_trigger` or calculating time, the agent compares strings rather than actual `datetime` objects, which can lead to incorrect results. Additionally, requiring the agent to provide ISO format datetime in tool parameters causes timezone issues. Since LLMs aren't particularly good with timezones, they typically treat everything as UTC, which causes confusion in LLM responses (e.g., "I set my timezone to America/Toronto, but the agent said that my trigger is at UTC"). Another example: when the agent calls the tool with an ISO datetime parameter, it uses 'Z' at the end, which indicates UTC.

**Fix:** The agent doesn't need to care about timezones, so instead of ISO format, the agent now uses a formatted datetime string (`YYYY-MM-DD HH:MM:SS`) with no timezone information. All operations are normalized as follows:

- **Agent** will only see date and time in the user's timezone (so it's relevant when talking to the user and they don't need to convert anything)
- **Database** will only store date and time in UTC (since MongoDB only allows UTC datetime objects to be stored; it will be automatically converted by MongoDB)
- The datetime will always be converted to the correct timezone when needed

---

## ✨ New Features

### 1. MongoDB Database Integration

**Context:** The app previously stored all logs and data in files (under `/server/data`).

**Summary:** Migrated all logs and data storage to MongoDB.

**What Changed:** All logs and data that were previously stored in files have been moved to a MongoDB database.

**Benefits:**

- Enables global access (not limited to local access only)
- Provides data persistence when the server is corrupted
- Allows monitoring software to query MongoDB for statistics
- Enables vector embedding search (feature provided by MongoDB)

---

### 2. Dynamic Agent Selection

**Context:** The current workflow creates a new agent when the agent name doesn't exist in the list of agents. The list of ALL agents is also provided to the interaction agent. This causes two problems:

1. If we continuously create new agents for new purposes or similar purposes (that already exist), we will end up with many agents that have similar usage. This also introduces problems with context usage.
2. When there are many agents available, the interaction agent has many agents to choose from. This causes issues with hallucination or not picking the right agent when needed. This also increases token usage.

**Summary:** The interaction agent now only receives the top 3 most recently-used execution agent names in the prompt. On new agent requests, we perform a vector search on the requested agent's description against all agent descriptions (in the agent roster) to find a matching agent.

**What Changed:**

- **Workflow when sending messages to agents (using `send_to_agent` tool):**

  - **Previously:** The interaction agent was given a list of all previously created agents. The interaction agent then needed to call the `send_to_agent` tool with the agent's name as the parameter. If the agent existed, it was used. If it was new (no agent existed with that name), a new one was created.
  - **Now:** The interaction agent is given at most the top 3 most recently-used agents. The interaction agent then needs to call the `send_to_agent` tool with the agent's name and description as parameters. If the agent exists, it's used. If it's new (no agent existed with that name), a vector similarity search is performed on the agent roster (each agent's description). If a similar agent is found, that agent is used instead of creating a new one. If none is similar, a new agent is created with the description (and the description's embedding is stored for future similarity searches).

- The interaction agent is given only the top 3 most recently-used agents in the prompt (instead of the entire agent roster). If the interaction agent needs another agent (other than those 3), it will try to find a similar agent as mentioned above.

**Benefits:**

- Reduced token usage for the interaction agent
- Less confusion when the interaction agent is deciding which agent to use from the agent roster → better accuracy
- Prevents creation of similar agents → Context is more useful (e.g., if the agent creates 2 agents for replying to Carlos and creating draft emails for Carlos on certain events, it will lose context on the conversation history with Carlos. It will be divided into 2 agents and won't have full context on the contact Carlos)

---

### 3. MCP Server Support

**Context:** The app previously stored all tool schemas and tool registries in the same app context as the chat agent. This made maintaining tools somewhat difficult (harder to manage). It would also be difficult for people who want to add tools dynamically.

**Summary:** The execution agent now supports both in-app function tools and MCP tools (MCP server using Streamable HTTP Transport).

**What Changed:**

- The execution agent previously only supported in-app function tools. Now, the agent supports both in-app function tools and MCP tools (with MCP client).
- Previously, creating new tools required managing schemas and registries separately. Adding custom logic would also mean changing all existing tool logic. Now, we can create customized logic for each tool differently. MCP servers also automatically generate schemas and registries for us while adding a layer of authentication.

**Benefits:**

- Allows us to add external tools without having knowledge of the codebase by attaching the agent to an MCP server
- Enables easier tool management and more readable code
- Enable custom logic on parameter (ex: the `agent_name` field is automatically filled in based on the `x-openpoke` header when requesting to the MCP server)

---

### 4. Folder-like Tools

**Context:** The app currently exposes all tools to the execution agent. As the number of tools grows, the agent will have more tools to choose from, which might cause hallucination (wrong tool calls) and also increase token usage.

**Summary:** The app will only expose tools as "folders" where the agent can "open" to gain access to more tools. This way, the number of tool choices will increase as the instruction requires more capabilities.

**What Changed:**

- TODO TO FILL IN LATER

**Benefits:**

- TODO TO FILL IN LATER

---

## 🛠️ New Tools

### 1. Bookkeeping Tool

**MCP Server:** `bookkeeping_mcp`

**Description:** Provides comprehensive tools for bookkeeping and expense tracking. The agent can create, update, delete, and list financial records (both income and expenses), get expense summaries, and generate cashflow reports.

**Available Tools:**

- **`createRecord`** - Create a new bookkeeping record (income or expense)
  - Parameters: `record_type` (income/expense), `amount`, `category`, `description` (optional), `date_time` (optional, YYYY-MM-DD HH:MM:SS format)
- **`updateRecord`** - Update an existing bookkeeping record
  - Parameters: `record_id`, `record_type` (optional), `amount` (optional), `category` (optional), `description` (optional), `date_time` (optional)
- **`deleteRecord`** - Delete a bookkeeping record
  - Parameters: `record_id`
- **`listRecords`** - List all bookkeeping records with optional filters
  - Parameters: `record_type` (optional), `start_date_time` (optional), `end_date_time` (optional), `category` (optional)
- **`getExpenseSummary`** - Get a summary of expenses for a specific time period
  - Parameters: `start_date_time`, `end_date_time`, `category` (optional)
  - Returns: Total amount, record count, and breakdown by category
- **`getCashflow`** - Get cashflow report (income vs expenses) for a specific time period
  - Parameters: `start_date_time`, `end_date_time`
  - Returns: Total income, total expense, net cashflow, and record counts

**Features:**

- All datetime operations are normalized to the user's timezone
- Supports filtering by record type, date range, and category
- Provides comprehensive financial reporting capabilities

---

### 2. Internet Search Tool (with Perplexity Sonar Model)

**MCP Server:** `perplexity_mcp`

**Description:** Provides web search capabilities using Perplexity's search API. The tool can search the web for information with configurable recency filters and detail levels.

**Available Tools:**

- **`search`** - Search the web for information (default level of detail)
  - Parameters: `query` (required), `recency` (optional: 'day', 'week', 'month', or 'year')
- **`deep_search`** - Search the web for information with a deeper level of detail
  - Parameters: `query` (required), `recency` (optional: 'day', 'week', 'month', or 'year')

**Features:**

- Supports recency filtering to get recent information
- Two search modes: standard search and deep search for more detailed results
- Powered by Perplexity's advanced search capabilities

## 📝 How to Register/Create a New MCP Server for Execution Agent

1. Create a server in the `mcp_server` folder using the base `OpenPokeMCP` class for authentication and parameter validation.

2. Register the server in `server/mcp_server/__init__.py`.

3. Edit `server/agents/execution_agent/batch_manager.py` (around line 63) to include the key you just registered.

4. Done! Start the MCP server, and the execution agent should automatically connect to it when generating responses.

---

## 🚀 How to Run the Program

1. **Run the frontend** with:

   ```bash
   npm run dev --prefix web
   ```

2. **Run the backend (agents)** with:

   ```bash
   python -m server.server
   ```

3. **Run each MCP server** with:

   ```bash
   python -m server.mcp_server.<mcp_server_filename>
   ```

   For example:

   ```bash
   python -m server.mcp_server.perplexity_mcp
   ```

**Note:** Make sure to use `.venv` (virtual environment) when running the backend or MCP servers.

## 🔮 Future Improvements

1. **Use Mem0 for user preferences and information storage** - Instead of extracting user information from emails, use Mem0 to store and manage user preferences and information.

2. **Voice input support** - Allow users to speak instead of typing by implementing a "press-and-hold" button in the frontend to record their requests and transcribe them using a speech-to-text (STT) model.

3. **Multimodal input and output** - Support multiple media types including images, audio, and video for both input and output.
