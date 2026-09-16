import json
import unittest

from agent import Agent


def state(elements):
    return {
        "schema_version": "1.0",
        "sanitized_state_id": "SPS_risk_001",
        "source_page_state_id": "PS_risk_001",
        "captured_at": "2026-09-16T13:00:00Z",
        "url": "https://example.test",
        "title": "Risk test",
        "visible_text": "Continue Pay",
        "elements": elements,
        "privacy_summary": {
            "sensitive_context_detected": False,
            "redaction_count": 0,
            "categories": [],
            "verification_passed": True,
        },
    }


def button(element_id, label, sensitivity="NONE"):
    return {
        "element_id": element_id,
        "role": "button",
        "label": label,
        "visible": True,
        "enabled": True,
        "sensitivity": sensitivity,
    }


def textbox(element_id, sensitivity="NONE", role="textbox"):
    return {
        "element_id": element_id,
        "role": role,
        "label": "Input",
        "visible": True,
        "enabled": True,
        "sensitivity": sensitivity,
    }


def plan(action):
    return json.dumps({
        "schema_version": "1.0",
        "action_plan_id": "AP_risk_001",
        "source_sanitized_state_id": "SPS_risk_001",
        "created_at": "2026-09-16T13:00:01Z",
        "intent": "Run risk classification test.",
        "actions": [action],
    })


class StaticAdapter:
    def __init__(self, output):
        self.output = output

    def generate(self, context):
        return self.output


class RiskPolicyTests(unittest.TestCase):
    def test_low_risk_action_is_allowed(self):
        action = {
            "action_id": "ACT_risk01",
            "action_type": "CLICK",
            "target_element_id": "EL_001",
            "reason": "Open the section.",
            "risk_level": "LOW",
        }
        output = Agent(StaticAdapter(plan(action))).create_plan(
            {"task_id": "TASK_risk01", "natural_language_goal": "Open the section."},
            state([button("EL_001", "Continue")]),
        )
        self.assertIsNotNone(output.action_plan)
        normalized = output.action_plan["actions"][0]
        self.assertEqual(normalized["risk_level"], "LOW")
        self.assertFalse(normalized.get("requires_user_confirmation", False))

    def test_submit_like_click_is_elevated_and_requires_confirmation(self):
        action = {
            "action_id": "ACT_risk02",
            "action_type": "CLICK",
            "target_element_id": "EL_002",
            "reason": "Proceed with payment.",
            "risk_level": "LOW",
        }
        output = Agent(StaticAdapter(plan(action))).create_plan(
            {"task_id": "TASK_risk02", "natural_language_goal": "Pay now."},
            state([button("EL_002", "Pay now")]),
        )
        self.assertIsNotNone(output.action_plan)
        normalized = output.action_plan["actions"][0]
        self.assertEqual(normalized["risk_level"], "HIGH")
        self.assertTrue(normalized["requires_user_confirmation"])

    def test_sensitive_target_overrides_low_model_risk(self):
        action = {
            "action_id": "ACT_risk03",
            "action_type": "TYPE",
            "target_element_id": "EL_003",
            "input": {"source": "PLACEHOLDER", "value": "[ACCOUNT_01]"},
            "reason": "Enter account information.",
            "risk_level": "LOW",
        }
        output = Agent(StaticAdapter(plan(action))).create_plan(
            {"task_id": "TASK_risk03", "natural_language_goal": "Enter account information."},
            state([textbox("EL_003", sensitivity="REDACTED")]),
        )
        self.assertIsNotNone(output.action_plan)
        normalized = output.action_plan["actions"][0]
        self.assertEqual(normalized["risk_level"], "HIGH")
        self.assertTrue(normalized["requires_user_confirmation"])

    def test_confirmation_flag_forces_at_least_medium_risk(self):
        action = {
            "action_id": "ACT_risk04",
            "action_type": "CLICK",
            "target_element_id": "EL_004",
            "reason": "Review before proceeding.",
            "risk_level": "LOW",
            "requires_user_confirmation": True,
        }
        output = Agent(StaticAdapter(plan(action))).create_plan(
            {"task_id": "TASK_risk04", "natural_language_goal": "Review."},
            state([button("EL_004", "Continue")]),
        )
        self.assertIsNotNone(output.action_plan)
        normalized = output.action_plan["actions"][0]
        self.assertEqual(normalized["risk_level"], "MEDIUM")
        self.assertTrue(normalized["requires_user_confirmation"])


if __name__ == "__main__":
    unittest.main()
