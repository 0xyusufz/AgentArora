import json
from typing import Any, Mapping, Protocol


class ReasoningAdapter(Protocol):
    def generate(self, context: Mapping[str, Any]) -> str | Mapping[str, Any]:
        """Return one candidate ActionPlan without executing it."""


class StubReasoningAdapter:
    """Deterministic stand-in for a future model/provider integration."""

    def generate(self, context: Mapping[str, Any]) -> str:
        page_state = context["sanitized_page_state"]
        elements = page_state.get("elements", [])
        target = next(
            (
                element
                for element in elements
                if element.get("visible") is True and element.get("enabled") is True
            ),
            None,
        )

        if target is None:
            action = {
                "action_id": "ACT_stub_001",
                "action_type": "WAIT",
                "wait_ms": 100,
                "reason": "No enabled visible target is available yet.",
                "risk_level": "LOW",
            }
        else:
            action = {
                "action_id": "ACT_stub_001",
                "action_type": "CLICK",
                "target_element_id": target["element_id"],
                "reason": "Use the first enabled visible actionable element.",
                "risk_level": "LOW",
            }

        return json.dumps(
            {
                "schema_version": "1.0",
                "action_plan_id": "AP_stub_001",
                "source_sanitized_state_id": page_state["sanitized_state_id"],
                "created_at": "2026-09-13T00:00:00Z",
                "intent": context["user_task"]["natural_language_goal"],
                "actions": [action],
            }
        )