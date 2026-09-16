from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .adapters import ReasoningAdapter, StubReasoningAdapter
from .context import ContextBuilder, load_sanitized_page_state_validator
from .errors import AgentContractError
from .parser import parse_action_plan
from .policy import ActionPolicy
from .validator import ActionPlanValidator


@dataclass(frozen=True)
class AgentOutput:
    action_plan: dict[str, Any] | None = None
    action_result: dict[str, Any] | None = None


class Agent:
    def __init__(self, adapter: ReasoningAdapter | None = None):
        self._adapter = adapter or StubReasoningAdapter()
        self._context_builder = ContextBuilder(load_sanitized_page_state_validator())
        self._action_plan_validator = ActionPlanValidator()
        self._action_policy = ActionPolicy()

    def create_plan(
        self,
        user_task: Mapping[str, Any],
        sanitized_page_state: Mapping[str, Any],
    ) -> AgentOutput:
        try:
            context = self._context_builder.build(user_task, sanitized_page_state)
            model_output = self._adapter.generate(context)
            action_plan = parse_action_plan(model_output)
            schema_valid_plan = self._action_plan_validator.validate(action_plan)
            approved_plan = self._action_policy.validate(
                schema_valid_plan, sanitized_page_state
            )
            return AgentOutput(action_plan=approved_plan)
        except AgentContractError as error:
            return AgentOutput(
                action_result=self._safe_failure(
                    error.code,
                    error.safe_message,
                )
            )
        except Exception:
            return AgentOutput(
                action_result=self._safe_failure(
                    "UNKNOWN", "Agent could not produce a valid action plan."
                )
            )

    @staticmethod
    def _safe_failure(code: str, message: str) -> dict[str, Any]:
        normalized_code = code if code in {
            "SCHEMA_VALIDATION_FAILED",
            "INVALID_ACTION",
            "POLICY_BLOCKED",
            "UNKNOWN",
        } else "UNKNOWN"
        status = "BLOCKED_BY_POLICY" if normalized_code == "POLICY_BLOCKED" else "INVALID_ACTION"
        return {
            "schema_version": "1.0",
            "action_plan_id": "AP_failure_001",
            "action_id": "ACT_failure_001",
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": status,
            "observed_change": "No browser action was executed.",
            "needs_fresh_page_state": False,
            "error": {
                "code": normalized_code,
                "message": message,
                "retryable": normalized_code == "SCHEMA_VALIDATION_FAILED",
            },
        }