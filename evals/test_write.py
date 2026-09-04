import asyncio, json
from src.tools.jira_write import add_comment

result = asyncio.run(add_comment(
    "SUP-1",
    "Automated test from support-intelligence-mcp. Layer 7 write path check."
))
print(json.dumps(result, indent=2))
