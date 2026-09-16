import re
from typing import Any, Mapping

from .errors import AgentContractError


ALLOWED_ACTION_TYPES = {
    "CLICK",
    "TYPE",
    "SCROLL",
    "SELECT",
    "PRESS_KEY",
    "WAIT",
}
TARGET_ACTION_TYPES = {"CLICK", "TYPE", "SELECT"}
COMMON_ACTION_FIELDS = {"action_id", "action_type", "reason", "risk_level", "requires_user_confirmation"}
ACTION_FIELDS = {
    "CLICK": COMMON_ACTION_FIELDS | {"target_element_id"},
    "TYPE": COMMON_ACTION_FIELDS | {"target_element_id", "input"},
    "SELECT": COMMON_ACTION_FIELDS | {"target_element_id", "select"},
    "PRESS_KEY": COMMON_ACTION_FIELDS | {"key"},
    "SCROLL": COMMON_ACTION_FIELDS | {"scroll"},
    "WAIT": COMMON_ACTION_FIELDS | {"wait_ms"},
}

FORBIDDEN_CONTENT = re.compile(
    r"(?:javascript\s*:|<\s*/?\s*script\b|(?:document|window)\s*\.\s*|"
    r"querySelector\s*\(|xpath|css\s+selector|https?://|www\.|"
    r"(?:cmd|powershell|bash|sh)\s+(?:/c|-c)|\b(?:curl|wget)\b|\beval\s*\()",
    re.IGNORECASE,
)
SENSITIVE_LITERAL = re.compile(
    r"(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b\d{3}[-. ]?\d{3}[-. ]?\d{4}\b|"
    r"\b(?:\d[ -]*?){13,19}\b|\b(?:password|passwd|secret|token|api[_ -]?key)\s*[:=])",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(r"^\[[A-Z0-9_]+(?:_[0-9]+)?\]$")


class ActionPolicy:
    """Deterministic action policy applied after ActionPlan schema validation."""

    def __init__(self, risk_classifier=None):
        if risk_classifier is None:
            from .risk_policy import classify_action
            risk_classifier = classify_action
        self._risk_classifier = risk_classifier

    def validate(
        self,
        action_plan: Mapping[str, Any],
        sanitized_page_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if action_plan["source_sanitized_state_id"] != sanitized_page_state["sanitized_state_id"]:
            self._reject("Action plan references a different sanitized page state.")

        elements = {
            element["element_id"]: element
            for element in sanitized_page_state.get("elements", [])
        }
        action_ids = set()
        normalized_actions = []
        for action in action_plan["actions"]:
            action_type = action["action_type"]
            if action_type not in ALLOWED_ACTION_TYPES:
                self._reject("Action type is not allowed by policy.")
            if action["action_id"] in action_ids:
                self._reject("Action IDs must be unique.")
            action_ids.add(action["action_id"])

            if not set(action).issubset(ACTION_FIELDS[action_type]):
                self._reject("Action contains unsupported or mixed fields.")

            self._check_strings(action)
            self._check_sensitive_literals(action)

            target = None
            if action_type in TARGET_ACTION_TYPES:
                target_id = action["target_element_id"]
                target = elements.get(target_id)
                if target is None:
                    self._reject("Action target is not present in sanitized page state.")
                if not target["visible"] or not target["enabled"]:
                    self._reject("Action target is not visible and enabled.")

            risk_level, requires_confirmation = self._risk_classifier(action, target)
            if risk_level == "HIGH" and not requires_confirmation:
                requires_confirmation = True
            if requires_confirmation and risk_level == "LOW":
                risk_level = "MEDIUM"

            normalized = dict(action)
            normalized["risk_level"] = risk_level
            if requires_confirmation:
                normalized["requires_user_confirmation"] = True
            normalized_actions.append(normalized)

        return {**dict(action_plan), "actions": normalized_actions}

    @staticmethod
    def _reject(message: str) -> None:
        raise AgentContractError("POLICY_BLOCKED", message)

    def _check_strings(self, value: Any) -> None:
        if isinstance(value, str) and FORBIDDEN_CONTENT.search(value):
            self._reject("Action contains unsupported executable or navigation content.")
        if isinstance(value, Mapping):
            for nested in value.values():
                self._check_strings(nested)
        elif isinstance(value, list):
            for nested in value:
                self._check_strings(nested)

    def _check_sensitive_literals(self, action: Mapping[str, Any]) -> None:
        input_value = action.get("input")
        if not isinstance(input_value, Mapping):
            return
        source = input_value.get("source")
        value = input_value.get("value")
        if source == "PLACEHOLDER" and isinstance(value, str) and PLACEHOLDER.fullmatch(value):
            return
        if isinstance(value, str) and SENSITIVE_LITERAL.search(value):
            self._reject("Action contains an unnecessary raw sensitive value.")
