import json
import os
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


def is_mock() -> bool:
    """True when MOCK=true is set. Controls fixture vs live API."""
    return os.getenv("MOCK", "").lower() == "true"


def load(source: str, ticket_id: str) -> dict:
    """Load a canned response for a ticket. Fixtures are keyed by ticket id
    so one ticket maps to exactly one set of source responses."""
    slug = ticket_id.lower().replace(" ", "-")
    path = FIXTURES / f"{source}_{slug}.json"
    if not path.exists():
        return {
            "error": f"No fixture for {source}: {path.name}",
            "results": [],
            "total": 0,
        }
    return json.loads(path.read_text(encoding="utf-8"))
