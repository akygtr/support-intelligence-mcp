import requests
import os
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SUPPORT_CHANNEL = "C0BJRG60X8X"

mcp = FastMCP("support_intelligence_mcp")

@mcp.tool()
async def get_slack_messages(keyword: str) -> dict:
    """
    Fetch recent messages from the support-tickets Slack channel.
    Filters messages containing the keyword and returns matches.
    """
    response = requests.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        params={"channel": SLACK_SUPPORT_CHANNEL, "limit": 20}
    )

    data = response.json()

    if not data.get("ok"):
        return {"error": data.get("error", "Failed to fetch messages")}

    messages = data.get("messages", [])

    # filter messages that contain the keyword
    matches = []
    for msg in messages:
        text = msg.get("text", "")
        if keyword.lower() in text.lower():
            matches.append({
                "text": text,
                "timestamp": msg.get("ts", ""),
                "user": msg.get("user", "")
            })

    if not matches:
        return {"results": [], "message": f"No messages found containing '{keyword}'"}

    return {"results": matches, "total": len(matches)}

if __name__ == "__main__":
    mcp.run()