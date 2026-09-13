import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker, RefResolver

from .errors import AgentContractError


class ActionPlanValidator:
    def __init__(self, schema_path: Path | None = None):
        path = schema_path or Path(__file__).resolve().parent.parent / "contracts" / "action-plan.schema.json"
        contracts_dir = path.parent
        schemas = {
            schema.name: json.loads(schema.read_text(encoding="utf-8"))
            for schema in contracts_dir.glob("*.schema.json")
        }
        schema = schemas[path.name]
        resolver = RefResolver.from_schema(schema, store=schemas)
        self._validator = Draft202012Validator(
            schema, resolver=resolver, format_checker=FormatChecker()
        )

    def validate(
        self,
        action_plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(action_plan, Mapping):
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED", "Action plan must be an object."
            )
        if list(self._validator.iter_errors(action_plan)):
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED", "Action plan failed contract validation."
            )

        return dict(action_plan)