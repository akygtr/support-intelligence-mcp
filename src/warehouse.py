"""
Load trace spans into a SQL warehouse.

The connection string is the only warehouse-specific thing here. The schema
and the insert are standard SQL, so the same loader targets SQL Server today
and Snowflake or Postgres with a config change — traces should not be coupled
to where they happen to land.

Usage:
    python -m src.warehouse                 # load the newest trace file
    python -m src.warehouse traces/run_x.jsonl
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TRACES = Path(__file__).parent.parent / "traces"

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;DATABASE=support_intelligence;Trusted_Connection=yes;"
)

COLUMNS = [
    "run_id", "case_id", "span_name", "kind", "started_at", "duration_ms",
    "ok", "error", "source_ok", "source_error", "bytes", "hits",
    "tokens_in", "tokens_out", "provider", "attempt",
]

INSERT = (
    f"INSERT INTO dbo.TRACES ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(COLUMNS))})"
)


def _connect():
    import pyodbc
    return pyodbc.connect(os.getenv("WAREHOUSE_CONN", DEFAULT_CONN))


def latest_trace() -> Path:
    files = sorted(TRACES.glob("run_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit("No trace files found. Run the evals first.")
    return files[-1]


def _row(span: dict) -> tuple:
    """Flatten a span to the column order. Missing fields become NULL.

    started_at arrives as a timezone-aware ISO string. It goes in as a real
    datetime — passing the string lets the driver guess a buffer width and
    truncate, which fails on the offset suffix.
    """
    values = []
    for col in COLUMNS:
        v = span.get(col)
        if col == "started_at" and isinstance(v, str):
            v = datetime.fromisoformat(v).replace(tzinfo=None)
        values.append(v)
    return tuple(values)


def load(path: Path) -> int:
    spans = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not spans:
        return 0

    run_id = spans[0]["run_id"]
    rows = [_row(s) for s in spans]

    with _connect() as conn:
        cur = conn.cursor()
        # Re-loading the same trace file should not duplicate it.
        cur.execute("DELETE FROM dbo.TRACES WHERE run_id = ?", run_id)
        cur.fast_executemany = True
        cur.executemany(INSERT, rows)
        conn.commit()

    return len(rows)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_trace()
    count = load(path)
    print(f"Loaded {count} spans from {path.name} into dbo.TRACES")


if __name__ == "__main__":
    main()