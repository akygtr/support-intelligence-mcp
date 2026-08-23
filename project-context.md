# Support Intelligence MCP Server — Project Context

## What This Project Is
An MCP (Model Context Protocol) server that automates B2B technical support triage. It connects multiple real data sources and runs a diagnose → summarize → draft response workflow. Built as a portfolio project targeting Field/Sales Development Engineer (FDE) roles at companies like Cognite, Sight Machine, Moveworks, Glean, and C3.ai.

---

## Current Status
**Week 1 complete.** Three MCP tools built and working. Full diagnostic workflow running end to end on real data.

---

## Tech Stack
- **Language**: Python 3.10
- **MCP Framework**: FastMCP
- **Environment**: VS Code, PowerShell, Windows
- **Credentials**: Stored in `.env`, never committed to GitHub

---

## Project Structure
```
support-intelligence-mcp/
├── src/
│   └── tools/
│       ├── jira.py         ✅ done
│       ├── slack.py        ✅ done
│       ├── confluence.py   ✅ done
│       ├── gmail.py        ⏳ next
│       └── snowflake.py    ⏳ next
├── .env                    (gitignored)
├── .gitignore
├── main.py                 ✅ orchestration working
├── requirements.txt
└── README.md
```

---

## GitHub Repo
`https://github.com/akygtr/support-intelligence-mcp`

---

## Data Sources & Credentials

### Jira
- Workspace: `kuakshara28.atlassian.net`
- Project key: `SUP`
- Test ticket: `SUP-1` ("Broken Binding")
- `.env` keys: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_BASE_URL`

### Slack
- Workspace: `n8n-work` (`n8n-workco.slack.com`)
- Bot name: `support-intelligence-bot`
- Support channel: `support-tickets` (ID: `C0BJRG60X8X`)
- Bot added to channel: yes
- `.env` key: `SLACK_BOT_TOKEN`
- Note: uses `conversations.history` not `search.messages` (bot token limitation)

### Confluence
- URL: `kuakshara28-1787334845421.atlassian.net/wiki`
- Space key: `~63e462c6614cb4ba53035d84`
- Test page: "2026-08-21 Meeting notes" (contains binding/OPC-UA content)
- Uses same credentials as Jira: `JIRA_EMAIL` + `JIRA_API_TOKEN`

### Gmail
- Not connected yet — Week 2

### Snowflake
- Not connected yet — Week 2

---

## Tools Built

### `src/tools/jira.py`
**Function**: `get_ticket_details(ticket_id: str) -> dict`
- Hits Jira REST API v3
- Returns: ticket_id, summary, status, priority, description, reporter, created
- Error handling: returns `{"error": ...}` on non-200 response
- Wrapped in `@mcp.tool()` decorator

### `src/tools/slack.py`
**Function**: `get_slack_messages(keyword: str) -> dict`
- Reads last 20 messages from `support-tickets` channel
- Filters by keyword (case insensitive)
- Returns: list of matching messages with text, timestamp, user ID
- Wrapped in `@mcp.tool()` decorator

### `src/tools/confluence.py`
**Function**: `search_confluence(query: str) -> dict`
- Uses Confluence CQL search: `type=page AND text~'{query}'`
- Returns: title, page_id, excerpt (HTML stripped), direct URL
- Wrapped in `@mcp.tool()` decorator

---

## Orchestration (`main.py`)
**Function**: `diagnose_ticket(ticket_id: str) -> dict`

Workflow:
1. Fetch Jira ticket by ID
2. Extract ticket summary as search keyword
3. Search Slack for related messages using that keyword
4. Search Confluence for related pages using that keyword
5. Return combined result: `{ticket, slack, confluence}`

**Tested with SUP-1 — working end to end.**

Sample output:
```
Ticket: Broken Binding
Status: Open
Priority: Medium
Description: Hardware Migration caused Broken Binding
Slack messages found: 1
  - Broken Binding, after Hardware change
Confluence pages found: 1
  - 2026-08-21 Meeting notes: [url]
```

---

## What's Next (Week 2)

### Gmail Tool
- Connect Gmail API
- Tool: `search_gmail(query: str)` — search emails by keyword
- Use case: find customer email threads related to the ticket

### Snowflake Tool
- Connect Snowflake via `snowflake-connector-python`
- Tool: `query_customer_data(customer_name: str)` — pull customer account info
- Use case: enrich ticket with customer history and contract data

### After Both Tools Are Connected
- Add Gmail and Snowflake to the `diagnose_ticket()` orchestration
- Full 5-source workflow: Jira → Slack → Confluence → Gmail → Snowflake
- Wrap everything in a single FastMCP server (`main.py` becomes the MCP entry point)
- Connect to Claude Desktop and test Claude calling all tools live
- Record Loom demo
- Write proper README with architecture diagram

---

## Key Technical Notes
- PowerShell is the terminal (not CMD) — use `New-Item` not `type nul`
- `.env` is gitignored — never commit credentials
- Confluence HTML response contains `&nbsp;` entities — needs cleanup (backlog)
- Slack `search.messages` requires user token — using `conversations.history` with bot token instead
- All tools use `@mcp.tool()` decorator from FastMCP
- Each tool file has `mcp.run()` at bottom for standalone testing

---

## 6-Month Goal
Ship this project + 1 more portfolio project, then apply to FDE roles at Cognite, Sight Machine, Moveworks, Glean, C3.ai. Project should be demoable in 5 minutes via Loom and GitHub by end of Month 2.
