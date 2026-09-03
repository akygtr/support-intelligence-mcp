"""
Flag prompt-injection patterns in tool output.

This is detection, not prevention. Pattern matching catches obvious payloads
and misses anything phrased carefully, so it does not replace the trust
boundary in the prompt — it runs alongside it.

The value is determinism. The model has flagged every injection in the golden
set so far, but that is a behaviour, not a guarantee: a different model, a
different provider, or a more careful payload could slip past it silently.
A regex either matches or it does not, and either way the result is in the
trace.
"""

import re

# Instruction-shaped language aimed at an assistant rather than a reader.
PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
     "override attempt"),
    (r"disregard\s+(all\s+)?(previous|prior|above|the)\s+\w+",
     "override attempt"),
    (r"\b(system|admin|administrator)\s+(notice|message|override|instruction)",
     "false authority"),
    (r"do\s+not\s+(mention|reveal|tell|report|disclose)\s+(this|these|that|it)",
     "concealment request"),
    (r"\byou\s+(must|should|will)\s+(now\s+)?(mark|close|resolve|reply|respond)",
     "action directive"),
    (r"\b(mark|set)\s+(this|the)\s+(ticket|case|issue)\s+as\s+resolved",
     "action directive"),
    (r"new\s+(instructions?|task|directive)\s*[:.]",
     "instruction injection"),
    (r"\bact\s+as\s+(if|though|a)\b",
     "role override"),
    (r"</?(system|instructions?|prompt)>",
     "delimiter injection"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in PATTERNS]


def scan_text(text: str) -> list:
    """Return labels for injection patterns found in a string."""
    if not text:
        return []
    return sorted({label for pattern, label in COMPILED if pattern.search(text)})


def scan(payload, path: str = "") -> list:
    """Walk a tool payload and report where injection patterns appear.

    Returns a list of {"where": ..., "labels": [...], "excerpt": ...} so a
    finding can be traced back to the field it came from, not just the source.
    """
    findings = []

    if isinstance(payload, dict):
        for k, v in payload.items():
            findings.extend(scan(v, f"{path}.{k}" if path else k))

    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            findings.extend(scan(item, f"{path}[{i}]"))

    elif isinstance(payload, str):
        labels = scan_text(payload)
        if labels:
            findings.append({
                "where": path or "(root)",
                "labels": labels,
                "excerpt": payload[:160],
            })

    return findings