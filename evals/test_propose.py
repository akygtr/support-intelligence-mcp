import asyncio, json
from src.agent import diagnose_agentic
from src.propose import propose_actions
from src.actions import summarise

for ticket, customer in [("SUP-20", "Cobalt Systems"), ("SUP-11", "OPC")]:
    result = asyncio.run(diagnose_agentic(ticket, customer))
    proposals = propose_actions(ticket, result["diagnosis"])

    print("=" * 70)
    print(ticket)
    print("-" * 70)
    for p in proposals:
        print(f"  [{p.tier.value:>6}] {p.action}")
        print(f"           {p.rationale[:110]}")
    if not proposals:
        print("  (no actions proposed)")
    print()
