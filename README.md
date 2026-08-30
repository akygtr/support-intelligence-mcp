# Support Intelligence MCP Server

A Model Context Protocol (MCP) server that automates B2B technical support triage by pulling from 5 real data sources into a single diagnostic workflow — callable directly from Claude Desktop.

---

## The Problem

Support engineers waste time context-switching. A single ticket requires opening Jira, Slack, Confluence, Gmail, and a CRM — manually — before they can even start diagnosing. This project collapses that into one command.

---

## What It Does

One call to `diagnose_ticket` hits all 5 sources in sequence and returns a unified triage summary:

```
diagnose ticket SUP-1 for customer OPC
```

**Output:**
- Ticket details from Jira
- Internal Slack messages related to the issue
- Confluence documentation matches
- Customer email threads from Gmail
- Account info and contract status from Snowflake

---

## Quickstart

Runs with zero credentials in mock mode. All five sources return canned fixtures from `/fixtures`.

**1. Clone and install**

```bash
git clone https://github.com/akygtr/support-intelligence-mcp.git
cd support-intelligence-mcp
pip install -r requirements.txt
```

**2. Enable mock mode**

```bash
cp .env.example .env
```

`MOCK=true` is already set. Leave the API keys blank.

**3. Register with Claude Desktop**

Add to `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "support-intelligence": {
      "command": "python",
      "args": ["<ABSOLUTE_PATH>/support-intelligence-mcp/main.py"],
      "env": {
        "PYTHONPATH": "<ABSOLUTE_PATH>/support-intelligence-mcp"
      }
    }
  }
}
```

Replace `<ABSOLUTE_PATH>`. On Windows use escaped backslashes and point `command` at your `python.exe` if it isn't on PATH.

**4. Restart Claude Desktop, then ask:**

> Diagnose ticket SUP-1 for customer OPC

### Running against live systems

Set `MOCK=false` in `.env` and fill in credentials. Gmail also needs `gmail_credentials.json` from a Google Cloud OAuth desktop client. Both files are gitignored.

---

## Architecture

```
Claude Desktop
      │
      ▼
FastMCP Server (main.py)
      │
      ├── src/tools/jira.py        → Jira REST API v3
      ├── src/tools/slack.py       → Slack conversations.history
      ├── src/tools/confluence.py  → Confluence CQL search
      ├── src/tools/gmail.py       → Gmail API (OAuth2)
      └── src/tools/snowflake.py   → Snowflake connector
```

Each tool is independently callable or runs as part of the full `diagnose_ticket` orchestration.

---

## Tech Stack

- Python 3.10
- FastMCP
- Jira REST API v3
- Slack Web API
- Confluence REST API
- Gmail API (OAuth2)
- Snowflake Connector for Python
- Claude Desktop (MCP client)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/akygtr/support-intelligence-mcp
cd support-intelligence-mcp
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_BASE_URL=https://yourworkspace.atlassian.net

SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

SNOWFLAKE_ACCOUNT=your_account_id
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=PUBLIC
```

### 3. Gmail OAuth setup

- Go to [Google Cloud Console](https://console.cloud.google.com)
- Enable Gmail API → create OAuth2 credentials (Desktop app type)
- Download credentials JSON → rename to `gmail_credentials.json` → place in project root
- Run once to authorize: `python src/tools/gmail.py`
- This saves `gmail_token.json` — never needs to be repeated

### 4. Connect to Claude Desktop

Add this to your Claude Desktop config file:

**Windows:** `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "support-intelligence": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["C:\\path\\to\\support-intelligence-mcp\\main.py"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\support-intelligence-mcp"
      }
    }
  }
}
```

Restart Claude Desktop — the server appears under Settings → Developer.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `diagnose_ticket` | Full 5-source diagnostic workflow |
| `get_jira_ticket` | Fetch Jira ticket by ID |
| `get_slack_messages` | Search Slack support channel by keyword |
| `search_confluence` | Search Confluence pages via CQL |
| `search_gmail` | Search Gmail by keyword or query |
| `query_customer_data` | Look up customer account in Snowflake |
| `run_snowflake_query` | Run custom read-only SQL on Snowflake |

---

## Sample Output

```
Ticket: SUP-1 — Broken Binding
Status: Open | Priority: Medium
Reporter: Akshara Kumari | Created: Aug 19, 2026

Customer: OPC Systems (Enterprise, Active)
Contact: Carlos Rivera | Account Manager: Sarah Lee

Slack: 1 message — "Broken Binding, after Hardware change"
Confluence: Meeting notes matched, no KB article found
Gmail: No customer email thread found
```

---

## Project Context

Built as a portfolio project targeting Field/Sales Development Engineer roles at companies working at the intersection of OT and AI — Cognite, Sight Machine, Moveworks, Glean, C3.ai.

The workflow mirrors real support triage at industrial software companies where a single ticket touches multiple systems before a response goes out.

---

## What's Not Committed

```
.env
gmail_credentials.json
gmail_token.json
```

These contain credentials and are gitignored. See setup instructions above.

## Security

All credentials load from a gitignored `.env`. An OAuth client secret was committed early in development; it was rotated in Google Cloud and purged from git history with `git-filter-repo`. Fixture mode exists partly so the project can be demoed and tested with no credentials present.

---

## Roadmap

- [x] Five-source diagnostic orchestration
- [x] Fixture mode, runs with zero credentials
- [ ] Eval harness: golden set, faithfulness and hallucination metrics
- [ ] Tracing, cost and latency observability
- [ ] Agentic loop, model selects sources instead of fixed sequence
- [ ] Prompt injection and PII guardrails
- [ ] Semantic retrieval over Confluence