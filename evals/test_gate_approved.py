import asyncio, json
from src.actions import ProposedAction
from src.execute import execute_all

proposals = [
    ProposedAction("set_priority", {"ticket_id": "SUP-1", "priority": "High"},
                   "Approved by a human."),
    ProposedAction("close_ticket", {"ticket_id": "SUP-1"},
                   "Approved, but no executor exists."),
]

# Simulates a human approving both.
approved = {"set_priority", "close_ticket"}
print(json.dumps(asyncio.run(execute_all(proposals, approved)), indent=2))
