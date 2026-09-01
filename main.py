"""
Support Intelligence MCP Server
================================
A FastMCP server that automates B2B technical support triage.
Connects Jira, Slack, Confluence, Gmail, and Snowflake into a single
diagnose → summarize → draft workflow.

Run standalone:   python main.py
Claude Desktop:   see claude_desktop_config.json
"""

import json
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Import all tool modules — each registers its own tools on its own mcp instance,
# but we also call their core functions directly for the orchestration tool below.
from src.tools.jira import get_ticket_details
from src.tools.slack import get_slack_messages
from src.tools.confluence import search_confluence
from src.tools.gmail import search_gmail, GmailSearchInput
from src.tools.snowflake import query_customer_data, CustomerQueryInput
from src.trace import span, start_run

# Single FastMCP server — all tools live here for Claude Desktop
mcp = FastMCP("support_intelligence_mcp")


# ── Re-export individual tools so Claude Desktop sees them ──────────────────

@mcp.tool(
    name="get_jira_ticket",
    annotations={
        "title": "Get Jira Ticket Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_jira_ticket(ticket_id: str) -> str:
    """Fetch full details for a Jira support ticket by ID.

    Args:
        ticket_id (str): Jira ticket ID e.g. 'SUP-1', 'SUP-42'

    Returns:
        str: JSON with ticket_id, summary, status, priority, description,
             reporter, and created date. Returns error key on failure.
    """
    result = await get_ticket_details(ticket_id)
    return json.dumps(result, indent=2)


@mcp.tool(
    name="get_slack_messages",
    annotations={
        "title": "Search Slack Support Channel",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def slack_search(keyword: str) -> str:
    """Search recent Slack messages in the support-tickets channel by keyword.

    Reads last 20 messages and filters by keyword (case-insensitive).

    Args:
        keyword (str): Word or phrase to match against message text

    Returns:
        str: JSON with matched messages including text, timestamp, and user ID.
    """
    result = await get_slack_messages(keyword)
    return json.dumps(result, indent=2)


@mcp.tool(
    name="search_confluence",
    annotations={
        "title": "Search Confluence Knowledge Base",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def confluence_search(query: str) -> str:
    """Search Confluence pages for technical documentation and meeting notes.

    Uses CQL full-text search across all pages in the workspace.

    Args:
        query (str): Search terms e.g. 'OPC-UA binding', 'KEPServerEX migration'

    Returns:
        str: JSON with matching pages including title, page_id, excerpt, and URL.
    """
    result = await search_confluence(query)
    return json.dumps(result, indent=2)


@mcp.tool(
    name="search_gmail",
    annotations={
        "title": "Search Gmail for Customer Emails",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def gmail_search(query: str, max_results: int = 5) -> str:
    """Search Gmail for emails related to a support issue.

    Supports full Gmail search syntax (from:, subject:, etc.)

    Args:
        query (str): Search query e.g. 'broken binding OPC-UA', 'from:customer@acme.com'
        max_results (int): Max emails to return (default 5, max 20)

    Returns:
        str: JSON with matching emails including subject, sender, date, and body preview.
    """
    params = GmailSearchInput(query=query, max_results=max_results)
    return await search_gmail(params)


@mcp.tool(
    name="query_customer_data",
    annotations={
        "title": "Query Customer Account Data from Snowflake",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def snowflake_customer(customer_name: str, max_results: int = 5) -> str:
    """Look up customer account info from Snowflake by company name.

    Returns account details, contract status, and customer history.

    Args:
        customer_name (str): Company name (partial match supported)
        max_results (int): Max records to return (default 5)

    Returns:
        str: JSON with matching customer records from Snowflake CUSTOMERS table.
    """
    params = CustomerQueryInput(customer_name=customer_name, max_results=max_results)
    return await query_customer_data(params)


# ── Orchestration: full 5-source diagnostic workflow ───────────────────────

def _source_health(payload) -> dict:
    """Distinguish a completed call from a healthy one.

    Tools return errors as data rather than raising, so a span that did not
    throw is not evidence the source worked. Without this, a dashboard shows
    100% health while Gmail is dead.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return {"source_ok": True}

    if isinstance(payload, dict) and "error" in payload:
        return {"source_ok": False, "source_error": str(payload["error"])[:200]}

    return {"source_ok": True}
class DiagnoseInput(BaseModel):
    """Input model for the full diagnostic workflow tool."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    ticket_id: str = Field(
        ...,
        description="Jira ticket ID to diagnose e.g. 'SUP-1'",
        min_length=1,
        max_length=50
    )
    customer_name: str = Field(
        default="",
        description="Optional customer/company name for Snowflake lookup. If blank, extracted from ticket.",
        max_length=200
    )


@mcp.tool(
    name="diagnose_ticket",
    annotations={
        "title": "Full Ticket Diagnostic — All 5 Sources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def diagnose_ticket(params: DiagnoseInput) -> str:
    """Run a full support ticket diagnostic across all 5 data sources.

    Workflow:
        1. Fetch Jira ticket details
        2. Use ticket summary as search keyword
        3. Search Slack for related messages
        4. Search Confluence for related documentation
        5. Search Gmail for related customer emails
        6. Pull Snowflake customer account data

    Every source fetch is traced with its own span, so latency and failures
    are attributable per integration rather than to the run as a whole.

    Args:
        params (DiagnoseInput): Validated input with:
            - ticket_id (str): Jira ticket ID e.g. 'SUP-1'
            - customer_name (str): Optional company name for Snowflake lookup

    Returns:
        str: JSON with combined results from all sources:
            {
                "ticket": { ...jira fields... },
                "slack": { ...matching messages... },
                "confluence": { ...matching pages... },
                "gmail": { ...matching emails... },
                "snowflake": { ...customer records... }
            }
    """
    start_run(params.ticket_id)

    # Step 1: Jira
    with span("jira", kind="tool") as sp:
        ticket = await get_ticket_details(params.ticket_id)
        sp.record(bytes=len(json.dumps(ticket)), **_source_health(ticket))

    if "error" in ticket:
        return json.dumps({"error": f"Jira fetch failed: {ticket['error']}"})

    # Step 2: Extract keyword from ticket summary
    keyword = ticket.get("summary", params.ticket_id)

    # Step 3: Slack
    with span("slack", kind="tool") as sp:
        slack = await get_slack_messages(keyword, params.ticket_id)
        sp.record(bytes=len(json.dumps(slack)), hits=slack.get("total", 0),
                  **_source_health(slack))

    # Step 4: Confluence
    with span("confluence", kind="tool") as sp:
        confluence = await search_confluence(keyword, params.ticket_id)
        sp.record(bytes=len(json.dumps(confluence)), hits=confluence.get("total", 0),
                  **_source_health(confluence))

    # Step 5: Gmail
    gmail_params = GmailSearchInput(query=keyword, max_results=5)
    with span("gmail", kind="tool") as sp:
        gmail_raw = await search_gmail(gmail_params, params.ticket_id)
        sp.record(bytes=len(gmail_raw), **_source_health(gmail_raw))

    # Step 6: Snowflake — use provided customer_name or fall back to ticket reporter
    lookup_name = params.customer_name or ticket.get("reporter", keyword)
    sf_params = CustomerQueryInput(customer_name=lookup_name, max_results=5)
    with span("snowflake", kind="tool") as sp:
        snowflake_raw = await query_customer_data(sf_params, params.ticket_id)
        sp.record(bytes=len(snowflake_raw), **_source_health(snowflake_raw))
    snowflake = json.loads(snowflake_raw)

    return json.dumps({
        "ticket": ticket,
        "slack": slack,
        "confluence": confluence,
        "gmail": gmail,
        "snowflake": snowflake
    }, indent=2)



if __name__ == "__main__":
    # stdio transport — required for Claude Desktop
    mcp.run()
