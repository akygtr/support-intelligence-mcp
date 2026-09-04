"""
Execute approved actions.

Two gates stand between a proposal and a write. EXECUTE must be true, and the
action's tier must be auto-executable or explicitly approved. Both are checked
here rather than trusted from the caller, because the caller is sometimes the
agent and an agent that can approve its own actions has no gate at all.

Every attempt is traced, including the ones that were skipped. A refusal is a
decision worth recording — "the agent proposed closing a ticket and the gate
declined" is exactly what someone reviewing this needs to see.
"""

from src.actions import EXECUTE, ProposedAction
from src.tools.jira_write import EXECUTORS
from src.trace import span


async def execute_action(proposal: ProposedAction, approved: bool = False) -> dict:
    """Run one proposal if it is permitted to run.

    approved reflects a human decision made elsewhere. It is required for
    anything above LOW tier and ignored for actions with no executor.
    """
    result = {
        "action": proposal.action,
        "tier": proposal.tier.value,
        "executed": False,
        "reason": "",
    }

    if not EXECUTE:
        result["reason"] = "EXECUTE is not enabled"
    elif proposal.needs_approval and not approved:
        result["reason"] = f"{proposal.tier.value} tier requires approval"
    elif proposal.action not in EXECUTORS:
        result["reason"] = "no executor — this action is performed by a human"
    else:
        with span(f"execute_{proposal.action}", kind="action") as sp:
            outcome = await EXECUTORS[proposal.action](**proposal.params)
            sp.record(
                tier=proposal.tier.value,
                approved=approved,
                ok="error" not in outcome,
            )
        result["executed"] = "error" not in outcome
        result["outcome"] = outcome
        result["reason"] = "executed" if result["executed"] else "executor failed"
        return result

    with span(f"skipped_{proposal.action}", kind="action") as sp:
        sp.record(tier=proposal.tier.value, reason=result["reason"])

    return result


async def execute_all(proposals: list, approved_actions: set = None) -> dict:
    """Run a batch of proposals, returning what ran and what did not."""
    approved_actions = approved_actions or set()

    results = []
    for p in proposals:
        results.append(await execute_action(p, approved=p.action in approved_actions))

    return {
        "execute_enabled": EXECUTE,
        "executed": [r for r in results if r["executed"]],
        "skipped": [r for r in results if not r["executed"]],
        "total": len(results),
    }