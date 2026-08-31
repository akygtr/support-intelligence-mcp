"""
Deterministic retrieval metrics for the support-intelligence golden set.

No LLM involved. These score whether the right sources were queried, whether
failures were surfaced rather than swallowed, and whether sources that should
have been empty actually were. Faithfulness and hallucination scoring need a
generated diagnosis and live in the LLM judge layer, not here.
"""

SOURCE_KEYS = ["ticket", "slack", "confluence", "gmail", "snowflake"]

# diagnose_ticket returns Jira under the key "ticket"
KEY_TO_SOURCE = {
    "ticket": "jira",
    "slack": "slack",
    "confluence": "confluence",
    "gmail": "gmail",
    "snowflake": "snowflake",
}


def _is_error(payload: dict) -> bool:
    """A source that failed rather than returned nothing."""
    return isinstance(payload, dict) and "error" in payload


def _is_empty(payload: dict) -> bool:
    """A source that ran and legitimately found nothing."""
    if not isinstance(payload, dict):
        return True
    if _is_error(payload):
        return False
    if "results" in payload:
        return len(payload["results"]) == 0
    if "records" in payload:
        return len(payload["records"]) == 0
    # Jira returns a flat ticket dict, never empty when present
    return not bool(payload)


def sources_returned(result: dict) -> set:
    """Which sources came back with usable data."""
    found = set()
    for key in SOURCE_KEYS:
        payload = result.get(key)
        if payload is None:
            continue
        if _is_error(payload) or _is_empty(payload):
            continue
        found.add(KEY_TO_SOURCE[key])
    return found


def retrieval_recall(result: dict, case: dict) -> float:
    """Fraction of required sources that returned usable data.

    Cases with no required sources (eval_11) score 1.0 by definition —
    there was nothing to retrieve.
    """
    required = set(case.get("required_sources", []))
    if not required:
        return 1.0
    return len(required & sources_returned(result)) / len(required)


def errors_surfaced(result: dict) -> list:
    """Sources that failed. These must be reported, not treated as empty.

    The distinction between 'I looked and found nothing' and 'I could not
    look' is the whole point of eval_18 and eval_19.
    """
    return [
        KEY_TO_SOURCE[key]
        for key in SOURCE_KEYS
        if _is_error(result.get(key) or {})
    ]


def unexpected_sources(result: dict, case: dict) -> list:
    """Sources that returned data but were not expected to.

    Not automatically a failure — it flags the false-positive cases
    (eval_16, eval_17) where a source matched on a keyword but has
    nothing relevant to say.
    """
    required = set(case.get("required_sources", []))
    return sorted(sources_returned(result) - required - {"jira"})


def all_sources_attempted(result: dict) -> bool:
    """Every source key present in the payload, error or not.

    Catches a run that aborted partway instead of degrading gracefully.
    """
    return all(key in result for key in SOURCE_KEYS)


def score_case(result: dict, case: dict) -> dict:
    """Full deterministic scorecard for one case."""
    return {
        "id": case["id"],
        "ticket_id": case["ticket_id"],
        "category": case.get("category", "uncategorized"),
        "recall": retrieval_recall(result, case),
        "errors_surfaced": errors_surfaced(result),
        "unexpected_sources": unexpected_sources(result, case),
        "all_attempted": all_sources_attempted(result),
    }