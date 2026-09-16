import json
import unittest

from agent import Agent
from agent.dynamic_dom import DynamicDOMOrchestrator


class StaticAdapter:
    def __init__(self, output):
        self.output = output

    def generate(self, context):
        return self.output


def user_task():
    return {
        "task_id": "TASK_dynamic_001",
        "natural_language_goal": "Continue the workflow.",
    }


def fresh_state(state_id="SPS_fresh_002", element_id="EL_010"):
    return {
        "schema_version": "1.0",
        "sanitized_state_id": state_id,
        "source_page_state_id": "PS_fresh_002",
        "captured_at": "2026-09-16T12:00:00Z",
        "url": "https://example.test/workflow",
        "title": "Workflow",
        "visible_text": "Continue",
        "elements": [
            {
                "element_id": element_id,
                "role": "button",
                "label": "Continue",
                "visible": True,
                "enabled": True,
                "sensitivity": "NONE",
            }
        ],
        "privacy_summary": {
            "sensitive_context_detected": False,
            "redaction_count": 0,
            "categories": [],
            "verification_passed": True,
        },
    }


def action_plan(state_id, element_id):
    return json.dumps({
        "schema_version": "1.0",
        "action_plan_id": "AP_dynamic_001",
        "source_sanitized_state_id": state_id,
        "created_at": "2026-09-16T12:00:01Z",
        "intent": "Continue the workflow.",
        "actions": [
            {
                "action_id": "ACT_dynamic_001",
                "action_type": "CLICK",
                "target_element_id": element_id,
                "reason": "Continue the workflow.",
                "risk_level": "LOW",
            }
        ],
    })


def stale_result():
    return {
        "schema_version": "1.0",
        "action_plan_id": "AP_dynamic_001",
        "action_id": "ACT_dynamic_001",
        "completed_at": "2026-09-16T12:00:02Z",
        "status": "STALE_ELEMENT",
        "observed_change": "No browser action was executed.",
        "needs_fresh_page_state": True,
        "error": {
            "code": "STALE_ELEMENT",
            "message": "Target element is no longer attached to the document.",
            "retryable": True,
        },
    }


class DynamicDOMTests(unittest.TestCase):
    def test_stale_low_risk_action_allows_recovery(self):
        orchestrator = DynamicDOMOrchestrator(max_stale_recoveries=2)
        decision = orchestrator.handle_action_result(
            stale_result(),
            {
                "action_id": "ACT_dynamic_001",
                "action_type": "CLICK",
                "target_element_id": "EL_001",
                "reason": "Continue.",
                "risk_level": "LOW",
            },
            stale_recoveries=0,
        )

        self.assertTrue(decision.allowed)
        self.assertTrue(decision.needs_fresh_page_state)
        self.assertIsNone(decision.result)

    def test_stale_high_risk_action_is_blocked(self):
        orchestrator = DynamicDOMOrchestrator()
        decision = orchestrator.handle_action_result(
            stale_result(),
            {
                "action_id": "ACT_dynamic_001",
                "action_type": "CLICK",
                "target_element_id": "EL_001",
                "reason": "Confirm transfer.",
                "risk_level": "HIGH",
            },
            stale_recoveries=0,
        )

        self.assertFalse(decision.allowed)
        self.assertFalse(decision.needs_fresh_page_state)
        self.assertEqual(decision.result["status"], "BLOCKED_BY_POLICY")
        self.assertEqual(decision.result["error"]["code"], "POLICY_BLOCKED")
        self.assertFalse(decision.result["error"]["retryable"])

    def test_recovery_bound_is_enforced(self):
        orchestrator = DynamicDOMOrchestrator(max_stale_recoveries=2)
        action = {
            "action_id": "ACT_dynamic_001",
            "action_type": "CLICK",
            "target_element_id": "EL_001",
            "reason": "Continue.",
            "risk_level": "LOW",
        }

        first = orchestrator.handle_action_result(stale_result(), action, stale_recoveries=1)
        exhausted = orchestrator.handle_action_result(stale_result(), action, stale_recoveries=2)

        self.assertTrue(first.allowed)
        self.assertFalse(exhausted.allowed)
        self.assertEqual(exhausted.result["status"], "BLOCKED_BY_POLICY")
        self.assertFalse(exhausted.result["error"]["retryable"])

    def test_new_plan_references_new_sanitized_state(self):
        state = fresh_state("SPS_fresh_002", "EL_010")
        agent = Agent(StaticAdapter(action_plan("SPS_fresh_002", "EL_010")))
        orchestrator = DynamicDOMOrchestrator()

        output = orchestrator.replan_after_refresh(
            agent=agent,
            user_task=user_task(),
            action_result=stale_result(),
            original_action={
                "action_id": "ACT_dynamic_001",
                "action_type": "CLICK",
                "target_element_id": "EL_001",
                "reason": "Continue.",
                "risk_level": "LOW",
            },
            fresh_sanitized_page_state=state,
            stale_recoveries=0,
        )

        self.assertIsNotNone(output.action_plan)
        self.assertEqual(output.action_plan["source_sanitized_state_id"], "SPS_fresh_002")

    def test_old_element_id_is_not_reused_after_refresh(self):
        state = fresh_state("SPS_fresh_002", "EL_010")
        agent = Agent(StaticAdapter(action_plan("SPS_fresh_002", "EL_001")))
        orchestrator = DynamicDOMOrchestrator()

        output = orchestrator.replan_after_refresh(
            agent=agent,
            user_task=user_task(),
            action_result=stale_result(),
            original_action={
                "action_id": "ACT_dynamic_001",
                "action_type": "CLICK",
                "target_element_id": "EL_001",
                "reason": "Continue.",
                "risk_level": "LOW",
            },
            fresh_sanitized_page_state=state,
            stale_recoveries=0,
        )

        self.assertIsNone(output.action_plan)
        self.assertEqual(output.action_result["status"], "BLOCKED_BY_POLICY")
        self.assertEqual(output.action_result["error"]["code"], "POLICY_BLOCKED")


if __name__ == "__main__":
    unittest.main()
