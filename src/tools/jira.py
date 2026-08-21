import requests
import os
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")

mcp = FastMCP("support_intelligence_mcp")

@mcp.tool()
def get_ticket_details(ticket_id: str) -> dict:
    """
    Fetch details of a Jira support ticket by ticket ID.
    Returns summary, status, priority, description and reporter.
    """
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"

    response = requests.get(
        url,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN)
    )

    if response.status_code != 200:
        return {"error": f"Failed to fetch ticket. Status: {response.status_code}"}

    data = response.json()
    fields = data["fields"]

    description = ""
    try:
        description = fields["description"]["content"][0]["content"][0]["text"]
    except (TypeError, KeyError, IndexError):
        description = "No description provided"

    return {
        "ticket_id": ticket_id,
        "summary": fields.get("summary", ""),
        "status": fields["status"]["name"],
        "priority": fields["priority"]["name"],
        "description": description,
        "reporter": fields["reporter"]["displayName"],
        "created": fields.get("created", "")
    }

if __name__ == "__main__":
    mcp.run()