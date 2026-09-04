import asyncio
from src.agent import diagnose_agentic

for t, c in [("SUP-20", "Cobalt Systems"), ("SUP-1", "OPC"),
             ("SUP-13", "Aldercrest Manufacturing"), ("SUP-14", "Meridian Foods")]:
    r = asyncio.run(diagnose_agentic(t, c))
    slack = "slack" if "search_slack" in r["tools_used"] else "NO SLACK"
    print(f"{t:<8} {slack:<10} {r['tools_used']}")
