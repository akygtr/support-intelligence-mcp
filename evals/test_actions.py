from src.actions import ProposedAction, summarise
import json

proposals = [
    ProposedAction("add_comment", {"ticket_id": "SUP-1", "body": "Root cause: stale bindings."},
                   "Records the diagnosis where the assignee will see it."),
    ProposedAction("set_priority", {"ticket_id": "SUP-1", "priority": "High"},
                   "Slack reports the whole line down, not one device."),
    ProposedAction("close_ticket", {"ticket_id": "SUP-1"},
                   "Diagnosis complete."),
]

print(json.dumps(summarise(proposals), indent=2))

try:
    ProposedAction("delete_everything", {}, "no")
except ValueError as e:
    print("\nrejected:", e)
