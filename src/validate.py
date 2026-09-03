"""
Validate a generated diagnosis before it is returned or written anywhere.

Input redaction is not sufficient on its own. The model can reconstruct or
paraphrase something the redactor stripped, and once the diagnosis is written
to a ticket it is published. This is the last gate before that.

Validation reports rather than raises. A diagnosis that fails a check is still
useful to a human reviewing it — silently discarding it would lose the
analysis along with the problem.
"""

import re
from dataclasses import dataclass, field

from src.redact import EMAIL, IPV4, PHONE, SECRET

MAX_CHARS = 2000
MIN_CHARS = 80

# Markdown structure, when the prompt asked for plain prose.
HEADER = re.compile(r"^#{1,6}\s", re.MULTILINE)
BULLET = re.compile(r"^\s*[-*•]\s", re.MULTILINE)


@dataclass
class ValidationResult:
    ok: bool = True
    leaks: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def fail(self, kind: str, detail: str) -> None:
        self.ok = False
        (self.leaks if kind == "leak" else self.issues).append(detail)


def validate_diagnosis(text: str) -> ValidationResult:
    """Check a diagnosis for PII leakage and structural problems."""
    result = ValidationResult()

    if not text or not text.strip():
        result.fail("issue", "empty diagnosis")
        return result

    stripped = text.strip()

    if len(stripped) < MIN_CHARS:
        result.fail("issue", f"too short: {len(stripped)} chars")
    if len(stripped) > MAX_CHARS:
        result.fail("issue", f"too long: {len(stripped)} chars")

    for name, pattern in (
        ("email address", EMAIL),
        ("phone number", PHONE),
        ("IP address", IPV4),
        ("token-shaped string", SECRET),
    ):
        found = pattern.findall(stripped)
        if found:
            result.fail("leak", f"{name}: {len(found)} occurrence(s)")

    if HEADER.search(stripped):
        result.fail("issue", "contains markdown headers")
    if BULLET.search(stripped):
        result.fail("issue", "contains bullet lists")

    return result