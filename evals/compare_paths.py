"""
Score the fixed-sequence path against the agentic path on the same cases.

The fixed path queries all five sources every time. The agent chooses. This
runs both over the golden set and reports what that choice costs and buys:
tool calls, tokens, and whether the eval scores hold.

A drop in tool calls is only a win if quality holds. Both numbers are printed
together for that reason.

Usage:
    python evals/compare_paths.py
    python evals/compare_paths.py --limit=5
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ["MOCK"] = "true"

from evals.judge import judge_claims  # noqa: E402
from evals.metrics import score_case, score_diagnosis  # noqa: E402
from src.agent import diagnose_agentic  # noqa: E402
from src.diagnose import write_diagnosis  # noqa: E402
from main import DiagnoseInput, diagnose_ticket  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.jsonl"
FIXED_SOURCES = 5


def load_cases() -> list:
    cases = [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for arg in sys.argv:
        if arg.startswith("--limit="):
            cases = cases[: int(arg.split("=")[1])]
    return cases


def _judged_hallucinations(diagnosis: str, case: dict) -> list:
    flagged = score_diagnosis(diagnosis, case).get("hallucinations", [])
    return judge_claims(diagnosis, flagged) if flagged else []


async def run_fixed(case: dict) -> dict:
    params = DiagnoseInput(
        ticket_id=case["ticket_id"],
        customer_name=case.get("customer_name", ""),
    )
    sources = json.loads(await diagnose_ticket(params))
    diagnosis = write_diagnosis(sources)

    scored = score_case(sources, case)
    scored.update(score_diagnosis(diagnosis, case))
    scored["hallucinations"] = _judged_hallucinations(diagnosis, case)
    scored["tool_calls"] = FIXED_SOURCES
    return scored


async def run_agentic(case: dict) -> dict:
    result = await diagnose_agentic(
        case["ticket_id"], case.get("customer_name", "")
    )
    diagnosis = result["diagnosis"]

    scored = score_diagnosis(diagnosis, case)
    scored["hallucinations"] = _judged_hallucinations(diagnosis, case)
    scored["tool_calls"] = len(result["tools_used"]) + 1  # +1 for the Jira fetch
    scored["iterations"] = result["iterations"]
    scored["tools_used"] = result["tools_used"]
    scored["hit_limit"] = result.get("hit_limit", False)
    return scored


async def main() -> None:
    cases = load_cases()
    rows = []

    for case in cases:
        print(f"  {case['id']} ...", flush=True)
        try:
            fixed = await run_fixed(case)
            agent = await run_agentic(case)
        except Exception as e:
            print(f"    failed: {type(e).__name__}: {e}")
            continue
        rows.append({"case": case, "fixed": fixed, "agent": agent})

    print(f"\n{'ID':<9} {'CATEGORY':<18} {'CALLS f/a':>10} "
          f"{'MENTION f/a':>13} {'HALLUC f/a':>12}  AGENT CHOSE")
    print("-" * 100)
    for r in rows:
        f, a = r["fixed"], r["agent"]
        chose = ",".join(t.replace("search_", "").replace("lookup_", "")
                         for t in a["tools_used"]) or "none"
        if a.get("hit_limit"):
            chose += " [LIMIT]"
        print(
            f"{r['case']['id']:<9} {r['case'].get('category', ''):<18} "
            f"{f['tool_calls']:>4} /{a['tool_calls']:>4} "
            f"{f['mention_compliance']:>6.2f} /{a['mention_compliance']:>5.2f} "
            f"{len(f['hallucinations']):>5} /{len(a['hallucinations']):>5}  {chose}"
        )

    n = len(rows)
    if not n:
        return

    fixed_calls = sum(r["fixed"]["tool_calls"] for r in rows)
    agent_calls = sum(r["agent"]["tool_calls"] for r in rows)
    fixed_mention = sum(r["fixed"]["mention_compliance"] for r in rows) / n
    agent_mention = sum(r["agent"]["mention_compliance"] for r in rows) / n
    fixed_halluc = sum(len(r["fixed"]["hallucinations"]) for r in rows)
    agent_halluc = sum(len(r["agent"]["hallucinations"]) for r in rows)
    agent_iters = sum(r["agent"]["iterations"] for r in rows) / n

    print(f"\n{'':<22}{'FIXED':>10}{'AGENTIC':>10}{'DELTA':>10}")
    print("-" * 52)
    print(f"{'Tool calls':<22}{fixed_calls:>10}{agent_calls:>10}"
          f"{agent_calls - fixed_calls:>+10}")
    print(f"{'Mention compliance':<22}{fixed_mention:>10.2f}{agent_mention:>10.2f}"
          f"{agent_mention - fixed_mention:>+10.2f}")
    print(f"{'Hallucinations':<22}{fixed_halluc:>10}{agent_halluc:>10}"
          f"{agent_halluc - fixed_halluc:>+10}")
    print(f"{'Mean iterations':<22}{'1':>10}{agent_iters:>10.1f}")

    out = ROOT / "evals" / "path_comparison.json"
    out.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())