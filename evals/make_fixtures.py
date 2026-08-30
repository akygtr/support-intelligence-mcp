"""
Generate baseline fixtures for every ticket in the golden set.

Emits jira/slack/confluence/gmail/snowflake files per ticket, shaped to match
each case's `required_sources`. Sources NOT listed in required_sources get an
empty result, which is what the empty_source and source_down cases expect.

Signal-carrying cases (contradictions, false positives, injection) are written
by hand afterwards and are skipped here. See SKIP below.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIXTURES = ROOT / "fixtures"
GOLDEN = ROOT / "evals" / "golden_set.jsonl"

# Hand-written cases. The generator must not overwrite these.
SKIP = {"eval_13", "eval_14", "eval_15", "eval_16", "eval_17", "eval_18", "eval_20"}

EMPTY = {"results": [], "total": 0}


def slug(text: str) -> str:
    return text.lower().replace(" ", "-")


def jira(case: dict) -> dict:
    return {
        "ticket_id": case["ticket_id"],
        "summary": case["expected_root_cause"][:60],
        "status": "Open",
        "priority": "Medium",
        "description": case["expected_root_cause"],
        "reporter": "Support Engineer",
        "created": "2026-08-19T20:06:33.699-0700",
    }


def slack(case: dict) -> dict:
    return {
        "results": [
            {
                "text": f"Seeing this on {case['customer_name']}: {case['expected_root_cause'][:80]}",
                "timestamp": "1787334451.246929",
                "user": "U000000000",
            }
        ],
        "total": 1,
    }


def confluence(case: dict) -> dict:
    return {
        "results": [
            {
                "title": f"Runbook: {case['expected_root_cause'][:40]}",
                "page_id": "100000",
                "excerpt": f"Troubleshooting steps for {case['expected_root_cause'][:80]}",
                "url": "https://example.atlassian.net/wiki/spaces/demo/pages/100000/Runbook",
            }
        ],
        "total": 1,
    }


def gmail(case: dict) -> dict:
    return {
        "results": [
            {
                "message_id": "msg000",
                "subject": f"Re: {case['ticket_id']}",
                "sender": "customer@example.com",
                "date": "2026-08-19",
                "snippet": case["expected_root_cause"][:80],
            }
        ],
        "total": 1,
    }


def snowflake(case: dict) -> dict:
    return {
        "customer_name": case["customer_name"],
        "count": 1,
        "records": [
            {
                "ID": 1,
                "NAME": "Account Contact",
                "COMPANY": case["customer_name"],
                "EMAIL": "contact@example.com",
                "CONTRACT_STATUS": "Active",
                "PLAN": "Enterprise",
                "ACCOUNT_MANAGER": "Account Manager",
                "CREATED_DATE": "2024-08-01",
            }
        ],
    }


BUILDERS = {
    "jira": (jira, lambda c: c["ticket_id"]),
    "slack": (slack, lambda c: c["expected_root_cause"][:30]),
    "confluence": (confluence, lambda c: c["expected_root_cause"][:30]),
    "gmail": (gmail, lambda c: c["expected_root_cause"][:30]),
    "snowflake": (snowflake, lambda c: c["customer_name"]),
}


def main() -> None:
    cases = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    written = skipped = 0

    for case in cases:
        if case["id"] in SKIP:
            skipped += 1
            continue

        required = set(case.get("required_sources", []))

        for source, (build, key_of) in BUILDERS.items():
            # Jira always exists — every ticket has one.
            payload = build(case) if (source in required or source == "jira") else EMPTY
            path = FIXTURES / f"{source}_{slug(key_of(case))}.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            written += 1

    print(f"Wrote {written} fixtures. Skipped {skipped} hand-written cases: {sorted(SKIP)}")


if __name__ == "__main__":
    main()