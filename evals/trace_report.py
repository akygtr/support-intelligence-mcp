"""
Summarise a trace file: latency, source health, and token cost.

Reads the most recent traces/run_*.jsonl unless a path is given.

Usage:
    python evals/trace_report.py
    python evals/trace_report.py traces/run_20260901T231506_27d61891a5b4.jsonl
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRACES = ROOT / "traces"

# Gemini Flash pricing per million tokens. Update if the tier changes.
COST_IN_PER_M = 0.075
COST_OUT_PER_M = 0.30


def latest_trace() -> Path:
    files = sorted(TRACES.glob("run_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit("No trace files found. Run the evals first.")
    return files[-1]


def percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(len(ordered) * pct), len(ordered) - 1)
    return ordered[idx]


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_trace()
    spans = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    print(f"\nTrace: {path.name}")
    print(f"Spans: {len(spans)}   Cases: {len(set(s['case_id'] for s in spans))}")

    # --- Per-source latency and health ------------------------------------
    by_source = defaultdict(list)
    for s in spans:
        if s["kind"] == "tool":
            by_source[s["span_name"]].append(s)

    print(f"\n{'SOURCE':<14} {'CALLS':>6} {'MEAN ms':>9} {'P95 ms':>8} "
          f"{'FAILED':>7} {'MEAN BYTES':>11}")
    print("-" * 60)
    for name in sorted(by_source):
        rows = by_source[name]
        durations = [r["duration_ms"] for r in rows]
        failed = sum(1 for r in rows if not r.get("source_ok", True))
        sizes = [r.get("bytes", 0) for r in rows]
        print(f"{name:<14} {len(rows):>6} {sum(durations)/len(durations):>9.1f} "
              f"{percentile(durations, 0.95):>8.1f} {failed:>7} "
              f"{sum(sizes)/len(sizes):>11.0f}")

    # --- Failures in detail -----------------------------------------------
    failures = [s for s in spans if not s.get("source_ok", True)]
    if failures:
        print(f"\nSource failures: {len(failures)} spans across "
              f"{len(set(f['span_name'] for f in failures))} sources")
        seen = set()
        for f in failures:
            key = (f["span_name"], f.get("source_error", "")[:60])
            if key in seen:
                continue
            seen.add(key)
            cases = [x["case_id"] for x in failures if x["span_name"] == f["span_name"]]
            print(f"  {f['span_name']}: {f.get('source_error', '')[:80]}")
            print(f"    affected: {', '.join(sorted(set(cases)))}")

    # --- Model calls and cost ---------------------------------------------
    llm = [s for s in spans if s["kind"] == "llm"]
    if llm:
        tin = sum(s.get("tokens_in", 0) for s in llm)
        tout = sum(s.get("tokens_out", 0) for s in llm)
        durations = [s["duration_ms"] for s in llm]
        retries = sum(s.get("attempt", 1) - 1 for s in llm)
        cost = (tin / 1_000_000 * COST_IN_PER_M) + (tout / 1_000_000 * COST_OUT_PER_M)

        print(f"\n{'MODEL CALLS':<20} {len(llm)}")
        print(f"{'Mean latency':<20} {sum(durations)/len(durations):.0f} ms")
        print(f"{'P95 latency':<20} {percentile(durations, 0.95):.0f} ms")
        print(f"{'Tokens in / out':<20} {tin:,} / {tout:,}")
        print(f"{'Retries':<20} {retries}")
        print(f"{'Est. cost this run':<20} ${cost:.4f}")
        if llm:
            print(f"{'Est. cost per case':<20} ${cost/len(llm):.5f}")
    else:
                print("\nNo model calls in this trace. Either --no-llm was used, "
              "or every diagnosis was served from cache.")

    # --- Guardrails --------------------------------------------------------
    guards = [s for s in spans if s["kind"] == "guardrail"]
    if guards:
        print(f"\nGuardrail triggers: {len(guards)}")
        for g in guards:
            case = g.get("case_id") or "(no case)"
            print(f"  {g['span_name']} [{case}]: {g.get('detail', '')[:80]}")
    # --- Time split --------------------------------------------------------
    tool_ms = sum(s["duration_ms"] for s in spans if s["kind"] == "tool")
    llm_ms = sum(s["duration_ms"] for s in llm)
    total = tool_ms + llm_ms
    if total:
        print(f"\nTime split: retrieval {tool_ms/total*100:.1f}%  "
              f"generation {llm_ms/total*100:.1f}%")


if __name__ == "__main__":
    main()