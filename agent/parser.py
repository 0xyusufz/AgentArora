import json
from typing import Any, Mapping

from .errors import AgentContractError


def parse_action_plan(model_output: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(model_output, str):
        try:
            parsed = json.loads(model_output)
        except (TypeError, ValueError):
            raise AgentContractError(
                "SCHEMA_VALIDATION_FAILED", "Reasoning output was not valid JSON."
            ) from None
    elif isinstance(model_output, Mapping):
        parsed = dict(model_output)
    else:
        raise AgentContractError(
            "SCHEMA_VALIDATION_FAILED", "Reasoning output must be JSON or an object."
        )

    if not isinstance(parsed, dict):
        raise AgentContractError(
            "SCHEMA_VALIDATION_FAILED", "Reasoning output must be a JSON object."
        )
    return parsed