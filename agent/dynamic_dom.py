from dataclasses import dataclass
from typing import Any, Mapping

from .agent import Agent, AgentOutput


MAX_STALE_RECOVERIES = 2


@dataclass(frozen=True)
class StaleRecoveryDecision:
    allowed: bool
    needs_fresh_page_state: bool
    result: dict[str, Any] | None = None
    reason: str = ""


class DynamicDOMOrchestrator:
    """Small Day 4 Step 3 coordinator for stale EL_xxx references.

    This class deliberately does not execute browser actions and does not turn
    Agent.create_plan() into an autonomous loop. It only decides whether a
    stale result may trigger one bounded fresh-state replan.
    """

    def __init__(self, max_stale_recoveries: int = MAX_STALE_RECOVERIES):
        if max_stale_recoveries < 1:
            raise ValueError("max_stale_recoveries must be at least 1")
        self.max_stale_recoveries = max_stale_recoveries

    def handle_action_result(
        self,
        action_result: Mapping[str, Any],
        original_action: Mapping[str, Any],
        stale_recoveries: int,
    ) -> StaleRecoveryDecision:
        """Decide whether a STALE_ELEMENT result may trigger a fresh-state replan."""
        if action_result.get("status") != "STALE_ELEMENT":
            return StaleRecoveryDecision(
                allowed=False,
                needs_fresh_page_state=False,
                result=dict(action_result),
                reason="No stale-element recovery is required.",
            )

        risk_level = original_action.get("risk_level")
        requires_confirmation = bool(original_action.get("requires_user_confirmation", False))
        if risk_level == "HIGH" or requires_confirmation:
            return StaleRecoveryDecision(
                allowed=False,
                needs_fresh_page_state=False,
                result=self._safe_stop(action_result, "Stale high-risk or confirmation-gated action requires review."),
                reason="Automatic retry is blocked for a high-risk or confirmation-gated action.",
            )

        if stale_recoveries >= self.max_stale_recoveries:
            return StaleRecoveryDecision(
                allowed=False,
                needs_fresh_page_state=False,
                result=self._safe_stop(action_result, "Stale-element recovery limit exceeded."),
                reason="Maximum stale-element recovery attempts have been exhausted.",
            )

        return StaleRecoveryDecision(
            allowed=True,
            needs_fresh_page_state=True,
            result=None,
            reason="Fresh PageState may be requested before replanning.",
        )

    def replan_after_refresh(
        self,
        agent: Agent,
        user_task: Mapping[str, Any],
        action_result: Mapping[str, Any],
        original_action: Mapping[str, Any],
        fresh_sanitized_page_state: Mapping[str, Any],
        stale_recoveries: int,
    ) -> AgentOutput:
        """Build a new plan against a fresh sanitized state after stale recovery."""
        decision = self.handle_action_result(action_result, original_action, stale_recoveries)
        if not decision.allowed:
            return AgentOutput(action_result=decision.result)

        new_state_id = fresh_sanitized_page_state.get("sanitized_state_id")
        if not isinstance(new_state_id, str) or not new_state_id:
            return AgentOutput(action_result=self._safe_stop(action_result, "Fresh sanitized page state is required."))

        output = agent.create_plan(user_task, fresh_sanitized_page_state)
        if output.action_plan is None:
            return output

        if output.action_plan.get("source_sanitized_state_id") != new_state_id:
            return AgentOutput(
                action_result=self._safe_stop(
                    action_result,
                    "Replanned action does not reference the refreshed sanitized state.",
                )
            )

        old_target_id = original_action.get("target_element_id")
        if old_target_id:
            reused_old_target = any(
                action.get("target_element_id") == old_target_id
                for action in output.action_plan.get("actions", [])
            )
            if reused_old_target:
                return AgentOutput(
                    action_result=self._safe_stop(
                        action_result,
                        "Replanned action reused a stale element ID from the previous state.",
                    )
                )

        return output

    @staticmethod
    def _safe_stop(action_result: Mapping[str, Any], message: str) -> dict[str, Any]:
        result = dict(action_result)
        result["status"] = "BLOCKED_BY_POLICY"
        result["needs_fresh_page_state"] = False
        result["observed_change"] = "No browser retry was executed."
        result["error"] = {
            "code": "POLICY_BLOCKED",
            "message": message,
            "retryable": False,
        }
        return result
