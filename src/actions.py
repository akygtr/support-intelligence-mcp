"""
Proposed actions and the gate that decides whether they execute.

The agent does not call write tools. It proposes actions, and something else
decides whether they run. That separation exists because a decision and its
execution are the same event otherwise — you cannot inspect what the agent
wanted to do without it already having happened.

Proposals are tiered by blast radius. An internal comment is recoverable and
visible; a reply to a customer is neither. The tier determines whether a human
sees it first, not the agent's confidence in its own reasoning.
"""

import os
from dataclasses import dataclass, field
from enum import Enum

from dotenv import load_dotenv

load_dotenv()

# Nothing executes unless this is explicitly true. A portfolio project that
# writes to real systems by default is one careless run from a mess.
EXECUTE = os.getenv("EXECUTE", "").lower() == "true"


class Tier(str, Enum):
    """Blast radius, not confidence.

    LOW     internal, reversible, visible to the team
    MEDIUM  changes state others react to
    HIGH    customer-facing or closes the loop; never auto-executed
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Which actions the agent may propose, and what each costs if it is wrong.
ACTION_TIERS = {
    "add_comment": Tier.LOW,
    "add_label": Tier.LOW,
    "set_priority": Tier.MEDIUM,
    "assign_owner": Tier.MEDIUM,
    "reply_to_customer": Tier.HIGH,
    "close_ticket": Tier.HIGH,
}

AUTO_EXECUTE_TIERS = {Tier.LOW}


@dataclass
class ProposedAction:
    """One action the agent thinks should happen next.

    rationale is required. An action without a stated reason cannot be
    reviewed, and the reason is what a human is actually approving.
    """
    action: str
    params: dict
    rationale: str
    tier: Tier = field(init=False)

    def __post_init__(self):
        if self.action not in ACTION_TIERS:
            raise ValueError(f"Unknown action: {self.action}")
        self.tier = ACTION_TIERS[self.action]

    @property
    def needs_approval(self) -> bool:
        return self.tier not in AUTO_EXECUTE_TIERS

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "params": self.params,
            "rationale": self.rationale,
            "tier": self.tier.value,
            "needs_approval": self.needs_approval,
        }


def summarise(proposals: list) -> dict:
    """Split proposals into what would run and what needs a human.

    Returns both lists rather than filtering, so a caller can show a reviewer
    everything the agent wanted — including the parts that were auto-approved.
    """
    auto = [p for p in proposals if not p.needs_approval]
    held = [p for p in proposals if p.needs_approval]

    return {
        "execute_enabled": EXECUTE,
        "auto": [p.to_dict() for p in auto],
        "needs_approval": [p.to_dict() for p in held],
        "total": len(proposals),
    }