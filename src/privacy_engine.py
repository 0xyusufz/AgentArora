"""Privacy boundary between raw Browser PageState and Agent-facing SanitizedPageState.

The engine owns the task-local placeholder mapping and performs an independent
post-sanitization verification pass. Raw values and the mapping never become
part of SanitizedPageState.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from .tokenizer import PrivacyTokenizer


class PrivacyEngine:
    """Task-scoped privacy gateway for Browser -> Agent state."""

    def __init__(self, tokenizer: Optional[PrivacyTokenizer] = None) -> None:
        self.tokenizer = tokenizer or PrivacyTokenizer()
        self._last_sanitized_state: Optional[Dict[str, Any]] = None

    def sanitize(self, page_state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(page_state, dict):
            raise TypeError("page_state must be a dictionary")

        sanitized_state = self.tokenizer.sanitize_page_state(page_state)
        if not self._independent_privacy_check(page_state, sanitized_state):
            sanitized_state["privacy_summary"]["verification_passed"] = False
            raise RuntimeError("PRIVACY VIOLATION: detectable sensitive content remains in Agent payload")

        sanitized_state["privacy_summary"]["verification_passed"] = True
        self._last_sanitized_state = sanitized_state
        return sanitized_state

    def _independent_privacy_check(
        self, raw_page_state: Dict[str, Any], sanitized_state: Dict[str, Any]
    ) -> bool:
        """Verify recognized sensitive spans from raw input are absent from output."""
        sanitized_serialized = json.dumps(sanitized_state, ensure_ascii=False, sort_keys=True)
        detected_raw_values = set()

        def walk(value: Any) -> None:
            if isinstance(value, str):
                for start, end, _category in self.tokenizer._span_matches(value):
                    candidate = value[start:end]
                    if candidate:
                        detected_raw_values.add(candidate)
                return
            if isinstance(value, dict):
                for child in value.values():
                    walk(child)
                return
            if isinstance(value, list):
                for child in value:
                    walk(child)

        walk(raw_page_state)
        detected_raw_values.update(self.tokenizer.local_mapping.values())
        return all(raw_value not in sanitized_serialized for raw_value in detected_raw_values)

    def restore_value(self, placeholder: str) -> Optional[str]:
        return self.tokenizer.local_mapping.get(placeholder)

    def restore_text(self, sanitized_text: str) -> str:
        return self.tokenizer.restore_tokens(sanitized_text)

    def get_local_mapping(self) -> Dict[str, str]:
        return dict(self.tokenizer.local_mapping)

    def clear_session(self) -> None:
        self.tokenizer.clear_local_memory()
        self._last_sanitized_state = None

    def get_privacy_stats(self) -> Dict[str, Any]:
        state = self._last_sanitized_state
        if not state:
            return {
                "status": "no_sanitization_performed",
                "redaction_count": 0,
                "categories": [],
                "placeholder_count": 0,
            }
        summary = state.get("privacy_summary", {})
        return {
            "status": "protected",
            "redaction_count": int(summary.get("redaction_count", 0)),
            "categories": list(summary.get("categories", [])),
            "placeholder_count": len(self.tokenizer.local_mapping),
            "sensitive_context_detected": bool(summary.get("sensitive_context_detected", False)),
            "verification_passed": bool(summary.get("verification_passed", False)),
        }


def sanitize_page_state(page_state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Compatibility helper; callers must keep the second return value local."""
    engine = PrivacyEngine()
    sanitized = engine.sanitize(page_state)
    return sanitized, engine.get_local_mapping()
