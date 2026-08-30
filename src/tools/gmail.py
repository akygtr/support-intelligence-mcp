import os
import json
import base64
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from src.fixtures import is_mock, load

# Google OAuth / API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

mcp = FastMCP("gmail_mcp")

# Only need read access for this tool
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "gmail_credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "gmail_token.json")         # auto-created after first auth


def _get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None

    # Re-use existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh or re-auth if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_message_body(payload: dict) -> str:
    """Extract plain text body from a Gmail message payload."""
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return body.strip()


def _extract_header(headers: list, name: str) -> str:
    """Pull a specific header value by name from Gmail headers list."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


class GmailSearchInput(BaseModel):
    """Input model for Gmail search tool."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid"
    )

    query: str = Field(
        ...,
        description="Gmail search query — supports full Gmail syntax e.g. 'OPC-UA error', 'from:customer@example.com', 'subject:broken binding'",
        min_length=1,
        max_length=500
    )
    max_results: Optional[int] = Field(
        default=5,
        description="Max number of emails to return (1-20)",
        ge=1,
        le=20
    )


@mcp.tool(
    name="search_gmail",
    annotations={
        "title": "Search Gmail Emails",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def search_gmail(params: GmailSearchInput) -> str:
    """Search Gmail for emails matching a keyword or query.

    Supports full Gmail search syntax. Returns subject, sender, date,
    and a snippet of the email body for each match.

    Args:
        params (GmailSearchInput): Validated input with:
            - query (str): Search terms or Gmail query string
            - max_results (int): How many emails to return (default 5)

    Returns:
        str: JSON with list of matching emails, each containing:
            - message_id, subject, sender, date, snippet, body_preview
    """
    if is_mock():
        return json.dumps(load("gmail", params.query))
    try:
        service = _get_gmail_service()

        # Run the search
        result = service.users().messages().list(
            userId="me",
            q=params.query,
            maxResults=params.max_results
        ).execute()

        messages = result.get("messages", [])

        if not messages:
            return json.dumps({"query": params.query, "count": 0, "emails": []})

        emails = []
        for msg in messages:
            # Fetch full message
            full_msg = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()

            headers = full_msg.get("payload", {}).get("headers", [])
            body = _decode_message_body(full_msg.get("payload", {}))

            emails.append({
                "message_id": msg["id"],
                "subject": _extract_header(headers, "Subject"),
                "sender": _extract_header(headers, "From"),
                "date": _extract_header(headers, "Date"),
                "snippet": full_msg.get("snippet", ""),
                "body_preview": body[:500] if body else ""
            })

        return json.dumps({
            "query": params.query,
            "count": len(emails),
            "emails": emails
        }, indent=2)

    except FileNotFoundError:
        return json.dumps({
            "error": f"'{CREDENTIALS_FILE}' not found. Download it from Google Cloud Console and place it in the project root."
        })
    except Exception as e:
        return json.dumps({"error": f"Gmail search failed: {str(e)}"})


if __name__ == "__main__":
    mcp.run()
