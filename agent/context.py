from copy import deepcopy
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker, RefResolver

from .errors import AgentContractError


class ContextBuilder:
    """Builds the only context Member 3 may send to its reasoning adapter."""

    def __init__(self, sanitized_page_state_validator: Draft202012Validator):
        self._validator = sanitized_page_state_validator

    def build(
        self,
        user_task: Mapping[str, Any],
        sanitized_page_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(user_task, Mapping):
            raise AgentContractError("SCHEMA_VALIDATION_FAILED", "User task must be an object.")
        if not isinstance(sanitized_page_state, Mapping):
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED", "Sanitized page state must be an object."
            )

        required_task_fields = ("task_id", "natural_language_goal")
        if any(
            not isinstance(user_task.get(field), str) or not user_task[field]
            for field in required_task_fields
        ):
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED",
                "User task requires task_id and natural_language_goal.",
            )

        errors = list(self._validator.iter_errors(sanitized_page_state))
        if errors:
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED", "Sanitized page state failed contract validation."
            )

        task = {
            "task_id": user_task["task_id"],
            "natural_language_goal": user_task["natural_language_goal"],
        }
        if "constraints" in user_task:
            task["constraints"] = deepcopy(user_task["constraints"])

        return {
            "user_task": task,
            "sanitized_page_state": deepcopy(dict(sanitized_page_state)),
        }


def load_sanitized_page_state_validator() -> Draft202012Validator:
    from pathlib import Path
    import json

    contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in contracts_dir.glob("*.schema.json")
    }
    schema = schemas["sanitized-page-state.schema.json"]
    resolver = RefResolver.from_schema(schema, store=schemas)
    return Draft202012Validator(schema, resolver=resolver, format_checker=FormatChecker())