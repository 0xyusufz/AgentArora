from typing import Any, Mapping


SENSITIVE_ROLES = {"password", "textbox-password", "creditcard"}
SUBMIT_LIKE_LABELS = {
    "submit",
    "pay",
    "purchase",
    "buy",
    "transfer",
    "send",
    "confirm",
    "delete",
    "remove",
    "save",
    "authorize",
}


def classify_action(action: Mapping[str, Any], target: Mapping[str, Any] | None) -> tuple[str, bool]:
    """Return deterministic (risk_level, requires_user_confirmation)."""
    risk = action.get("risk_level", "LOW")
    requires_confirmation = bool(action.get("requires_user_confirmation", False))

    action_type = action.get("action_type")
    if action_type in {"TYPE", "SELECT"} and target:
        role = str(target.get("role", "")).lower()
        sensitivity = str(target.get("sensitivity", "NONE")).upper()
        label = str(target.get("label", "")).strip().lower()
        if role in SENSITIVE_ROLES or sensitivity != "NONE":
            risk = "HIGH"
            requires_confirmation = True
        elif action_type == "TYPE" and target.get("sensitivity") == "REDACTED":
            risk = "HIGH"
            requires_confirmation = True

    if action_type == "CLICK" and target:
        label = str(target.get("label", "")).strip().lower()
        if any(term == label or term in label for term in SUBMIT_LIKE_LABELS):
            risk = "HIGH"
            requires_confirmation = True

    if action_type in {"PRESS_KEY", "SCROLL", "WAIT"} and risk == "HIGH":
        requires_confirmation = True

    return risk, requires_confirmation
