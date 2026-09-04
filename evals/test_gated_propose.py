import asyncio
from src.agent import diagnose_agentic
from src.propose import propose_actions

for ticket, customer in [("SUP-20", "Cobalt Systems"), ("SUP-1", "OPC")]:
    r = asyncio.run(diagnose_agentic(ticket, customer))
    proposals = propose_actions(ticket, r["diagnosis"], r["injection_found"])

    print("=" * 70)
    print(f"{ticket}  injection_found={r['injection_found']}")
    print("-" * 70)
    for p in proposals:
        print(f"  [{p.tier.value:>6}] {p.action}")
    if not proposals:
        print("  (none)")
    print()
