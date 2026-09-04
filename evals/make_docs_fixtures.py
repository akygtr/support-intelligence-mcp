import json
from pathlib import Path

FIXTURES = Path("fixtures")
GOLDEN = Path("evals/golden_set.jsonl")

cases = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]

# search_docs was added after the fixtures were built. Documentation is not in
# required_sources for any case, so an empty result is correct everywhere: the
# corpus genuinely has nothing ticket-specific in it.
empty = {"results": [], "total": 0, "strong_matches": 0}

for case in cases:
    path = FIXTURES / f"docs_{case['ticket_id'].lower()}.json"
    path.write_text(json.dumps(empty, indent=2), encoding="utf-8")

print(f"Wrote {len(cases)} docs fixtures")
