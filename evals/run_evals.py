"""
Run the golden set through diagnose_ticket in mock mode and print a scorecard.

Usage:
    python evals/run_evals.py
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force mock mode before importing anything that reads the env.
os.environ["MOCK"] = "true"

from evals.metrics import score_case  # noqa: E402
from main import diagnose_ticket, DiagnoseInput  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.jsonl"


def load_cases() -> list:
    return [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def run_one(case: dict) -> dict:
    params = DiagnoseInput(
        ticket_id=case["ticket_id"],
        customer_name=case.get("customer_name", ""),
    )
    raw = await diagnose_ticket(params)
    return json.loads(raw)


async def main() -> int:
    cases = load_cases()
    scores = []

    for case in cases:
        try:
            result = await run_one(case)
            scores.append(score_case(result, case))
        except Exception as e:
            scores.append({
                "id": case["id"],
                "ticket_id": case["ticket_id"],
                "category": case.get("category", "uncategorized"),
                "recall": 0.0,
                "errors_surfaced": [],
                "unexpected_sources": [],
                "all_attempted": False,
                "crash": str(e),
            })

    print(f"\n{'ID':<9} {'TICKET':<8} {'CATEGORY':<18} {'RECALL':>7}  NOTES")
    print("-" * 78)
    for s in scores:
        notes = []
        if s.get("crash"):
            notes.append(f"CRASH: {s['crash'][:30]}")
        if s["errors_surfaced"]:
            notes.append(f"errors: {','.join(s['errors_surfaced'])}")
        if s["unexpected_sources"]:
            notes.append(f"extra: {','.join(s['unexpected_sources'])}")
        if not s["all_attempted"]:
            notes.append("incomplete")
        print(f"{s['id']:<9} {s['ticket_id']:<8} {s['category']:<18} "
              f"{s['recall']:>7.2f}  {'; '.join(notes)}")

    by_cat = defaultdict(list)
    for s in scores:
        by_cat[s["category"]].append(s["recall"])

    print(f"\n{'CATEGORY':<20} {'CASES':>6} {'MEAN RECALL':>12}")
    print("-" * 40)
    for cat in sorted(by_cat):
        vals = by_cat[cat]
        print(f"{cat:<20} {len(vals):>6} {sum(vals)/len(vals):>12.2f}")

    overall = sum(s["recall"] for s in scores) / len(scores)
    crashes = sum(1 for s in scores if s.get("crash"))
    incomplete = sum(1 for s in scores if not s["all_attempted"])

    print(f"\nOverall recall: {overall:.2f}   Crashes: {crashes}   Incomplete: {incomplete}")

    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
    