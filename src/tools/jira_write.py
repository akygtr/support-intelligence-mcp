"""
Jira write operations.

These are the only tools in the project that change state. They are annotated
honestly for that reason — the read tools carry readOnlyHint, and claiming the
same for a tool that posts a comment would be a lie the MCP client acts on.

Nothing here checks whether an action is a good idea. That decision belongs to
the approval gate in src/actions.py; these functions execute what has already
been approved. Keeping the two separate means the gate cannot be bypassed by
calling a tool directly.
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)
TIMEOUT = 20


def _adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format.

    Jira's v3 API rejects plain strings for rich-text fields.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": text}],
        }],
    }


async def add_comment(ticket_id: str, body: str) -> dict:
    """Post a comment on a ticket. Internal, visible, reversible."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}/comment"

    try:
        response = requests.post(
            url, auth=AUTH, timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
            json={"body": _adf(body)},
        )
    except Exception as e:
        return {"error": f"Comment failed: {type(e).__name__}: {e}"}

    if response.status_code not in (200, 201):
        return {"error": f"Comment failed. Status: {response.status_code}",
                "detail": response.text[:200]}

    data = response.json()
    return {
        "ok": True,
        "action": "add_comment",
        "ticket_id": ticket_id,
        "comment_id": data.get("id"),
        "url": f"{JIRA_BASE_URL}/browse/{ticket_id}",
    }


async def add_label(ticket_id: str, label: str) -> dict:
    """Add a label to a ticket. Additive, does not replace existing labels."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"

    try:
        response = requests.put(
            url, auth=AUTH, timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
            json={"update": {"labels": [{"add": label}]}},
        )
    except Exception as e:
        return {"error": f"Label failed: {type(e).__name__}: {e}"}

    if response.status_code != 204:
        return {"error": f"Label failed. Status: {response.status_code}",
                "detail": response.text[:200]}

    return {"ok": True, "action": "add_label",
            "ticket_id": ticket_id, "label": label}


async def set_priority(ticket_id: str, priority: str) -> dict:
    """Change ticket priority. Others triage against this, so it is medium tier."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{ticket_id}"

    try:
        response = requests.put(
            url, auth=AUTH, timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
            json={"fields": {"priority": {"name": priority}}},
        )
    except Exception as e:
        return {"error": f"Priority change failed: {type(e).__name__}: {e}"}

    if response.status_code != 204:
        return {"error": f"Priority change failed. Status: {response.status_code}",
                "detail": response.text[:200]}

    return {"ok": True, "action": "set_priority",
            "ticket_id": ticket_id, "priority": priority}


EXECUTORS = {
    "add_comment": add_comment,
    "add_label": add_label,
    "set_priority": set_priority,
}