"""
Span-based tracing for tool and model calls.

Deliberately not tied to a vendor SDK. Spans are written as JSONL, one line
per operation, so the trace format is inspectable, diffable, and loadable
into anything.
"""

import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TRACES = Path(__file__).parent.parent / "traces"

_run_id = None
_case_id = None
_path = None


def start_run(case_id: str = "", run_id: str = "") -> str:
    """Begin a traced run. Spans until the next start_run belong to this one."""
    global _run_id, _case_id, _path

    _case_id = case_id
    if run_id or _run_id is None:
        _run_id = run_id or uuid.uuid4().hex[:12]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        TRACES.mkdir(exist_ok=True)
        _path = TRACES / f"run_{stamp}_{_run_id}.jsonl"

    return _run_id


class Span:
    """One traced operation. Extra fields are attached via record()."""

    def __init__(self, name: str, kind: str):
        self.name = name
        self.kind = kind
        self.extra = {}

    def record(self, **fields) -> None:
        self.extra.update(fields)


@contextmanager
def span(name: str, kind: str = "tool"):
    """Time an operation and append a span record.

    Exceptions are recorded and re-raised. A failed call is a trace event,
    not a gap in the trace.
    """
    if _path is None:
        start_run()

    s = Span(name, kind)
    started = time.time()
    ok = True
    error = ""

    try:
        yield s
    except Exception as e:
        ok = False
        error = f"{type(e).__name__}: {e}"[:200]
        raise
    finally:
        record = {
            "run_id": _run_id,
            "case_id": _case_id,
            "span_name": name,
            "kind": kind,
            "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
            "duration_ms": round((time.time() - started) * 1000, 1),
            "ok": ok,
            "error": error,
        }
        record.update(s.extra)
        with _path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def current_trace_path() -> Optional[Path]:
    return _path