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

from evals.metrics import score_case, score_diagnosis  # noqa: E402
from src.diagnose import write_diagnosis  # noqa: E402
from main import diagnose_ticket, DiagnoseInput  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.jsonl"


def load_cases() -> list:
    return [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def run_one(case: dict, with_llm: bool) -> tuple:
    params = DiagnoseInput(
        ticket_id=case["ticket_id"],
        customer_name=case.get("customer_name", ""),
    )
    raw = await diagnose_ticket(params)
    sources = json.loads(raw)
    diagnosis = write_diagnosis(sources) if with_llm else ""
    return sources, diagnosis


async def main() -> int:
    with_llm = "--no-llm" not in sys.argv
    cases = load_cases()
    scores = []

    for case in cases:
        try:
            sources, diagnosis = await run_one(case, with_llm)
            row = score_case(sources, case)
            if with_llm:
                row.update(score_diagnosis(diagnosis, case))
                row["diagnosis"] = diagnosis
            scores.append(row)
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
        print(f"  ran {case['id']}", flush=True)

    print(f"\n{'ID':<9} {'CATEGORY':<18} {'RECALL':>7} {'MENTION':>8} {'HALLUC':>7}  NOTES")
    print("-" * 82)
    for s in scores:
        notes = []
        if s.get("crash"):
            notes.append(f"CRASH: {s['crash'][:28]}")
        if s.get("hallucinations"):
            notes.append(f"claimed: {','.join(s['hallucinations'])}")
        if s.get("injection_resisted") is False:
            notes.append("INJECTION NOT RESISTED")
        if s.get("injection_resisted") is True:
            notes.append("injection flagged")
        if s["errors_surfaced"]:
            notes.append(f"errors: {','.join(s['errors_surfaced'])}")

        mention = s.get("mention_compliance")
        halluc = len(s.get("hallucinations", []))
        print(f"{s['id']:<9} {s['category']:<18} {s['recall']:>7.2f} "
              f"{(f'{mention:.2f}' if mention is not None else '-'):>8} "
              f"{halluc:>7}  {'; '.join(notes)}")

    by_cat = defaultdict(list)
    for s in scores:
        by_cat[s["category"]].append(s)

    print(f"\n{'CATEGORY':<20} {'CASES':>6} {'RECALL':>8} {'MENTION':>9} {'HALLUC':>8}")
    print("-" * 55)
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        r = sum(x["recall"] for x in rows) / len(rows)
        m = [x["mention_compliance"] for x in rows if "mention_compliance" in x]
        h = sum(len(x.get("hallucinations", [])) for x in rows)
        m_str = f"{sum(m)/len(m):.2f}" if m else "-"
        print(f"{cat:<20} {len(rows):>6} {r:>8.2f} {m_str:>9} {h:>8}")

    total_halluc = sum(len(s.get("hallucinations", [])) for s in scores)
    crashes = sum(1 for s in scores if s.get("crash"))
    overall_recall = sum(s["recall"] for s in scores) / len(scores)

    print(f"\nOverall recall: {overall_recall:.2f}   "
          f"Hallucinations: {total_halluc}   Crashes: {crashes}")

    out = ROOT / "evals" / "last_run.json"
    out.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    print(f"Full results written to {out.relative_to(ROOT)}")

    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
    