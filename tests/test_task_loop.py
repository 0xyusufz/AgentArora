import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, RefResolver

from agent import Agent


MAX_STEPS = 3


def page_state(state_id, title, visible_text, elements):
    return {
        "schema_version": "1.0",
        "sanitized_state_id": state_id,
        "source_page_state_id": "PS_" + state_id[4:],
        "captured_at": "2026-09-14T10:00:00Z",
        "url": "https://example.test/task",
        "title": title,
        "visible_text": visible_text,
        "elements": elements,
        "privacy_summary": {
            "sensitive_context_detected": False,
            "redaction_count": 0,
            "categories": [],
            "verification_passed": True,
        },
    }


def element(element_id, role, label, visible=True, enabled=True):
    return {
        "element_id": element_id,
        "role": role,
        "label": label,
        "visible": visible,
        "enabled": enabled,
        "sensitivity": "NONE",
    }


def task(task_id, goal):
    return {"task_id": task_id, "natural_language_goal": goal}


def action_plan(state, task_goal, action):
    return {
        "schema_version": "1.0",
        "action_plan_id": "AP_" + state["sanitized_state_id"][4:],
        "source_sanitized_state_id": state["sanitized_state_id"],
        "created_at": "2026-09-14T10:00:01Z",
        "intent": task_goal,
        "actions": [action],
    }


class TaskAdapter:
    """Deterministic task-specific reasoning stand-in for the loop tests."""

    def __init__(self, task_id, plans):
        self.task_id = task_id
        self.plans = list(plans)
        self.calls = 0

    def generate(self, context):
        self.calls += 1
        plan = self.plans[min(self.calls - 1, len(self.plans) - 1)]
        if plan == "MALFORMED":
            return "not-json"
        return json.dumps(plan(context))


def click_plan(element_id, reason):
    def plan(context):
        state = context["sanitized_page_state"]
        return action_plan(
            state,
            context["user_task"]["natural_language_goal"],
            {
                "action_id": "ACT_click_01",
                "action_type": "CLICK",
                "target_element_id": element_id,
                "reason": reason,
                "risk_level": "LOW",
            },
        )

    return plan


def scroll_plan(reason):
    def plan(context):
        state = context["sanitized_page_state"]
        return action_plan(
            state,
            context["user_task"]["natural_language_goal"],
            {
                "action_id": "ACT_scroll_01",
                "action_type": "SCROLL",
                "scroll": {"direction": "DOWN", "amount": "SMALL"},
                "reason": reason,
                "risk_level": "LOW",
            },
        )

    return plan


def type_plan(element_id, reason):
    def plan(context):
        state = context["sanitized_page_state"]
        return action_plan(
            state,
            context["user_task"]["natural_language_goal"],
            {
                "action_id": "ACT_type_01",
                "action_type": "TYPE",
                "target_element_id": element_id,
                "input": {"source": "SAFE_LITERAL", "value": "demo query"},
                "reason": reason,
                "risk_level": "LOW",
            },
        )

    return plan


SCENARIOS = [
    {
        "name": "open_page_section",
        "task": task("TASK_open_01", "Open the Reports section."),
        "initial_state": page_state(
            "SPS_open_01",
            "Home",
            "Reports",
            [element("EL_101", "button", "Reports")],
        ),
        "adapter_plans": [click_plan("EL_101", "Open the Reports section requested by the user.")],
        "update": lambda state: state.update(
            title="Reports",
            visible_text="Reports section",
            elements=[element("EL_102", "heading", "Reports")],
        ),
    },
    {
        "name": "click_transactions",
        "task": task("TASK_transactions_01", "Click Transactions."),
        "initial_state": page_state(
            "SPS_transactions_01",
            "Account",
            "Account Transactions",
            [element("EL_201", "link", "Transactions")],
        ),
        "adapter_plans": [click_plan("EL_201", "Open Transactions for the user.")],
        "update": lambda state: state.update(
            title="Transactions",
            visible_text="Transactions list",
            elements=[element("EL_202", "heading", "Transactions")],
        ),
    },
    {
        "name": "find_visible_item",
        "task": task("TASK_item_01", "Find the visible invoice item."),
        "initial_state": page_state(
            "SPS_item_01",
            "Transactions",
            "Invoice 2026",
            [element("EL_301", "listitem", "Invoice 2026")],
        ),
        "adapter_plans": [
            "MALFORMED",
            click_plan("EL_301", "Open the visible Invoice 2026 item requested by the user."),
        ],
        "update": lambda state: state.update(
            visible_text="Invoice 2026 details",
            elements=[element("EL_302", "heading", "Invoice 2026")],
        ),
    },
    {
        "name": "scroll_to_relevant_section",
        "task": task("TASK_scroll_01", "Scroll to the relevant activity section."),
        "initial_state": page_state(
            "SPS_scroll_01",
            "Dashboard",
            "Dashboard top",
            [element("EL_401", "heading", "Dashboard")],
        ),
        "adapter_plans": [scroll_plan("Reveal the relevant activity section below the fold.")],
        "update": lambda state: state.update(
            visible_text="Dashboard Activity",
            elements=[element("EL_402", "heading", "Activity")],
        ),
    },
    {
        "name": "type_safe_test_field",
        "task": task("TASK_type_01", "Type into the safe test field."),
        "initial_state": page_state(
            "SPS_type_01",
            "Search",
            "Search",
            [element("EL_501", "textbox", "Safe test field")],
        ),
        "adapter_plans": [type_plan("EL_501", "Enter the safe test query in the requested field.")],
        "update": lambda state: state.update(visible_text="Search demo query"),
    },
]


class TaskLoopTests(unittest.TestCase):
    def setUp(self):
        contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in contracts_dir.glob("*.schema.json")
        }
        schema = schemas["action-result.schema.json"]
        self.action_result_validator = Draft202012Validator(
            schema,
            resolver=RefResolver.from_schema(schema, store=schemas),
            format_checker=FormatChecker(),
        )

    def simulate_action_result(self, action_plan):
        action = action_plan["actions"][0]
        return {
            "schema_version": "1.0",
            "action_plan_id": action_plan["action_plan_id"],
            "action_id": action["action_id"],
            "completed_at": "2026-09-14T10:00:02Z",
            "status": "SUCCESS",
            "observed_change": "Simulated sanitized browser change.",
            "needs_fresh_page_state": True,
        }

    def run_scenario(self, scenario):
        state = copy.deepcopy(scenario["initial_state"])
        adapter = TaskAdapter(scenario["task"]["task_id"], scenario["adapter_plans"])
        actions = []
        grounded_targets = []
        failures = []

        for step in range(1, MAX_STEPS + 1):
            output = Agent(adapter).create_plan(scenario["task"], state)
            if output.action_plan is None:
                failure = output.action_result["error"]
                failures.append({"code": failure["code"], "message": failure["message"]})
                continue

            action = output.action_plan["actions"][0]
            actions.append(action["action_type"])
            if "target_element_id" in action:
                grounded_targets.append(action["target_element_id"])
            action_result = self.simulate_action_result(output.action_plan)
            self.action_result_validator.validate(action_result)
            scenario["update"](state)
            return {
                "task": scenario["name"],
                "status": "PASS",
                "actions": actions,
                "grounded_targets": grounded_targets,
                "steps": step,
                "retry_count": len(failures),
                "failure_count": len(failures),
                "final_result": action_result["status"],
                "failures": failures,
            }

        return {
            "task": scenario["name"],
            "status": "FAIL",
            "actions": actions,
            "grounded_targets": grounded_targets,
            "steps": MAX_STEPS,
            "retry_count": len(failures),
            "failure_count": len(failures),
            "final_result": "MAX_STEPS_REACHED",
            "failures": failures,
        }

    def test_five_task_execution_loop_report(self):
        report = [self.run_scenario(scenario) for scenario in SCENARIOS]
        merged = {
            "successful_task_count": sum(result["status"] == "PASS" for result in report),
            "tasks": report,
        }
        print(json.dumps(merged, sort_keys=True))

        self.assertEqual(len(report), 5)
        self.assertEqual(merged["successful_task_count"], 5)
        for result in report:
            with self.subTest(task=result["task"]):
                self.assertEqual(result["status"], "PASS", result)
                self.assertLessEqual(result["steps"], MAX_STEPS)
                self.assertEqual(result["final_result"], "SUCCESS")
                for target in result["grounded_targets"]:
                    self.assertRegex(target, r"^EL_[0-9]{3,6}$")
        self.assertEqual(report[2]["retry_count"], 1)
        self.assertEqual(report[2]["failures"][0]["code"], "SCHEMA_VALIDATION_FAILED")

    def test_invalid_target_fails_without_simulated_execution(self):
        scenario = {
            "name": "invalid_target",
            "task": task("TASK_invalid_01", "Click the missing item."),
            "initial_state": page_state(
                "SPS_invalid_01",
                "Items",
                "Items",
                [element("EL_601", "button", "Known item")],
            ),
            "adapter_plans": [click_plan("EL_699", "Try the missing item.")],
            "update": lambda state: None,
        }
        result = self.run_scenario(scenario)

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["final_result"], "MAX_STEPS_REACHED")
        self.assertEqual(result["failure_count"], MAX_STEPS)
        self.assertTrue(all(failure["code"] == "POLICY_BLOCKED" for failure in result["failures"]))


if __name__ == "__main__":
    unittest.main()