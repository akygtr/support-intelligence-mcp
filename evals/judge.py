"""
LLM-as-judge for claim verification.

Substring matching cannot tell an assertion from a denial or a question.
Three cases in the first Anthropic run were flagged as hallucinations for
writing "the root cause is not the firmware", asking "was this user error?",
and saying a document was "too generic to confirm". All three were correct
diagnoses caught by a matcher that only sees characters.

The judge reads the diagnosis and answers whether a claim is actually
asserted. It is pinned to a specific model so scores stay comparable across
runs — changing the judge changes the scale, which would silently invalidate
every historical result.
"""

import json
import os
import re

from src.llm import call_llm

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM = """You verify whether a support diagnosis asserts specific claims.

For each claim, answer whether the diagnosis ASSERTS it as true.

A claim is NOT asserted when the diagnosis:
- denies it ("the root cause is not the firmware")
- raises it as an open question ("was this user error?")
- lists it as one unconfirmed possibility among several
- declines to rely on it ("too generic to confirm")
- attributes it to a source while doubting that source

A claim IS asserted when the diagnosis states it as fact, presents it as the
conclusion, or acts on it as established.

Return only a JSON object mapping each claim to true or false. No prose, no
markdown fences."""

TEMPLATE = """DIAGNOSIS:
{diagnosis}

CLAIMS TO CHECK:
{claims}

Return JSON: {{"claim text": true or false, ...}}"""


def _parse(raw: str) -> dict:
    """Pull a JSON object out of the response, fences or not."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except ValueError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def judge_claims(diagnosis: str, claims: list) -> list:
    """Return the subset of claims the diagnosis actually asserts.

    On a judge failure the claim list is returned unchanged — failing loud
    beats silently reporting zero hallucinations because the judge broke.
    """
    if not claims or not diagnosis:
        return []

    prompt = TEMPLATE.format(
        diagnosis=diagnosis,
        claims="\n".join(f"- {c}" for c in claims),
    )

    raw = call_llm(prompt, system=SYSTEM)
    verdicts = _parse(raw)

    return [c for c in claims if verdicts.get(c, True)]