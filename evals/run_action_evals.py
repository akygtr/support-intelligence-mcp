import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ["MOCK"] = "true"

from evals.metrics import score_actions  # noqa: E402
from src.agent import diagnose_agentic  # noqa: E402
from src.propose import propose_actions  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.jsonl"


async def main():
    cases = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    for arg in sys.argv:
        if arg.startswith("--limit="):
            cases = cases[: int(arg.split("=")[1])]

    rows = []
    for case in cases:
        print(f"  {case['id']} ...", flush=True)
        r = await diagnose_agentic(case["ticket_id"], case.get("customer_name", ""))
        proposals = propose_actions(case["ticket_id"], r["diagnosis"], r["injection_found"])
        score = score_actions(proposals, case)
        score["id"] = case["id"]
        score["category"] = case.get("category", "")
        score["injection_found"] = r["injection_found"]
        rows.append(score)

    print(f"\n{'ID':<9} {'CATEGORY':<18} {'OK':<5} {'PROPOSED':<30} ISSUES")
    print("-" * 95)
    for s in rows:
        issues = []
        if s["forbidden_actions"]:
            issues.append("FORBIDDEN: " + ",".join(s["forbidden_actions"]))
        if s["missing_actions"]:
            issues.append("missing: " + ",".join(s["missing_actions"]))
        mark = "ok" if s["action_ok"] else "FAIL"
        proposed = ",".join(s["proposed"]) or "(none)"
        print(f"{s['id']:<9} {s['category']:<18} {mark:<5} {proposed:<30} {'; '.join(issues)}")

    violations = sum(len(s["forbidden_actions"]) for s in rows)
    incomplete = sum(1 for s in rows if s["missing_actions"])
    print(f"\nForbidden actions proposed: {violations}")
    print(f"Cases missing a required action: {incomplete} of {len(rows)}")

    out = ROOT / "evals" / "action_results.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
