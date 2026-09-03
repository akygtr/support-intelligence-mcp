"""
Redact PII from tool output before it reaches the model.

Tool results go into the model's context and from there into diagnoses that
may be written back to a ticket. Anything sensitive that enters here can
leave in a place you did not intend, so it is stripped at the boundary rather
than trusted not to escape.

Deliberately conservative. A false positive costs a redacted token in a
diagnosis; a false negative costs a customer email address in a Jira comment
that anyone with access can read.
"""

import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"\b(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# Long hex or base64-ish runs: API keys, tokens, session ids.
SECRET = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")

# Fields whose values are replaced wholesale rather than pattern-matched.
SENSITIVE_KEYS = {"email", "phone", "ssn", "password", "token", "api_key"}
# Fields that hold a person's identity. Redacted structurally rather than by
# pattern — name detection in free text needs NER and produces false positives
# on product names and error strings, so only labelled fields are caught.
IDENTITY_KEYS = {"name", "contact", "reporter", "account_manager", "assignee", "user"}


def redact_text(text: str) -> str:
    """Replace PII patterns in a string."""
    text = EMAIL.sub("[EMAIL]", text)
    text = PHONE.sub("[PHONE]", text)
    text = IPV4.sub("[IP]", text)
    text = SECRET.sub("[REDACTED]", text)
    return text


def redact(payload):
    """Walk a payload and redact PII in place-equivalent form.

    Handles dicts, lists, and strings. Keys named in SENSITIVE_KEYS have their
    values replaced entirely — pattern matching on a field already labelled
    "password" is doing unnecessary work with a chance of missing.
    """
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            key = k.lower()
            if key in SENSITIVE_KEYS and isinstance(v, str):
                out[k] = "[REDACTED]"
            elif key in IDENTITY_KEYS and isinstance(v, str):
                out[k] = "[NAME]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(payload, list):
        return [redact(item) for item in payload]

    if isinstance(payload, str):
        return redact_text(payload)

    return payload