import asyncio, json
from src.actions import ProposedAction
from src.execute import execute_all

proposals = [
    ProposedAction("add_comment", {"ticket_id": "SUP-1", "body": "Gate test."},
                   "Low tier, would auto-execute if EXECUTE were on."),
    ProposedAction("set_priority", {"ticket_id": "SUP-1", "priority": "High"},
                   "Medium tier, needs approval."),
    ProposedAction("close_ticket", {"ticket_id": "SUP-1"},
                   "High tier, no executor exists."),
]

print(json.dumps(asyncio.run(execute_all(proposals)), indent=2))
