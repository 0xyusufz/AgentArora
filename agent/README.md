# Member 3 Agent

This is the initial Member 3 foundation. It does not call a model or browser.

## Flow

`Agent.create_plan(user_task, sanitized_page_state)` runs these stages:

1. Validate and copy the User Task and `SanitizedPageState` into a limited context.
2. Call the injected `ReasoningAdapter`.
3. Parse the adapter's JSON object output.
4. Validate the output with `contracts/action-plan.schema.json`.
5. Check the source state, unique action IDs, and visible/enabled target IDs.
6. Return one `ActionPlan`, or a schema-valid `ActionResult` with no execution.

The Day 1 policy allows only the six frozen action types, rejects mixed or
unsupported fields, requires visible/enabled targets when applicable, requires
targets to exist in the current sanitized state, and rejects executable content,
selectors, URLs, shell commands, and obvious raw sensitive literals. It is
deterministic and does not execute actions.

`StubReasoningAdapter` is the default deterministic adapter. A future provider should implement `generate(context)` and return one candidate ActionPlan as JSON or an object. The adapter receives only `user_task` and `sanitized_page_state`.

The module never receives raw `PageState`, stores placeholder mappings, executes browser actions, or includes model output in failure details.