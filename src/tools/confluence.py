import requests
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from src.fixtures import is_mock, load

load_dotenv()

CONFLUENCE_EMAIL = os.getenv("JIRA_EMAIL")
CONFLUENCE_API_TOKEN = os.getenv("JIRA_API_TOKEN")
CONFLUENCE_BASE_URL = "https://kuakshara28-1787334845421.atlassian.net/wiki"

mcp = FastMCP("support_intelligence_mcp")

@mcp.tool()
async def search_confluence(query: str, ticket_id: str = "") -> dict:
    """
    Search Confluence pages by keyword.
    Returns matching page titles and excerpts relevant to the query.
    """
    if is_mock():
        return load("confluence", ticket_id or query) 
    response = requests.get(
        f"{CONFLUENCE_BASE_URL}/rest/api/content/search",
        auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
        params={
            "cql": f"type=page AND text~'{query}'",
            "limit": 5,
            "expand": "body.storage"
        }
    )

    data = response.json()

    if "results" not in data:
        return {"error": "Confluence search failed"}

    pages = data.get("results", [])

    if not pages:
        return {"results": [], "message": f"No pages found for '{query}'"}

    results = []
    for page in pages:
        # extract plain text from page body safely
        body = ""
        try:
            body = page["body"]["storage"]["value"]
            # strip HTML tags roughly
            import re
            body = re.sub(r'<[^>]+>', ' ', body)
            body = body[:300].strip()
        except (KeyError, TypeError):
            body = "No content available"

        results.append({
            "title": page.get("title", ""),
            "page_id": page.get("id", ""),
            "excerpt": body,
            "url": CONFLUENCE_BASE_URL + page["_links"]["webui"]
        })

    return {"results": results, "total": len(results)}

if __name__ == "__main__":
    mcp.run()