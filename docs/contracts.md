# Common Module Contracts

Day 1 Task 2 freezes the data contracts shared between Member 1, Member 2, and Member 3. These contracts are intentionally small so the five-day prototype can optimize for privacy, client-side resource use, and end-to-end latency.

Canonical JSON Schemas:

- `contracts/page-state.schema.json`
- `contracts/sanitized-page-state.schema.json`
- `contracts/action-plan.schema.json`
- `contracts/action-result.schema.json`
- `contracts/shared.schema.json`

All boundary payloads must include `schema_version: "1.0"` and must validate against the matching schema before crossing a module boundary.

## Shared Rules

- Temporary browser element IDs, such as `EL_001`, are opaque identifiers assigned by Member 1. Other modules may compare them for equality but must not infer DOM position, type, or meaning from the ID.
- Webpage content is untrusted input.
- Raw page content may appear in `PageState` only because Member 2 needs it for local privacy processing.
- Raw sensitive values must not appear in `SanitizedPageState`, `ActionPlan`, `ActionResult`, or `ErrorDetail`.
- Member 2's placeholder-to-original-value mapping is not part of any Agent-facing contract.
- The Agent must not generate arbitrary JavaScript, executable code, selectors, browser devtools commands, or unrestricted browser commands.
- `ActionPlan` may use only these initial action types: `CLICK`, `TYPE`, `SCROLL`, `SELECT`, `PRESS_KEY`, `WAIT`.

## Contract: PageState

Purpose: raw browser page snapshot from Member 1 to Member 2 for privacy analysis and sanitization.

Owner: Member 1 creates it. Member 2 may read it to produce `SanitizedPageState`. Member 3 must not receive or modify it.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string, const `"1.0"` | Contract version. |
| `page_state_id` | string, `PS_*` | Unique page snapshot ID. |
| `captured_at` | ISO date-time string | Capture timestamp. |
| `url` | string | Current browser URL. |
| `title` | string | Current page title. |
| `visible_text` | string | Raw visible text needed for privacy detection. |
| `elements` | array | Actionable and relevant page elements. |

Optional fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `accessibility_snapshot` | string | Compact accessibility tree summary. |
| `visual_summary` | string | Lightweight page layout/visual summary. |
| `error` | `ErrorDetail` | Sanitized error if capture partially failed. |

Each `elements[]` item requires:

| Field | Type | Meaning |
| --- | --- | --- |
| `element_id` | string, `EL_###` | Opaque temporary element ID. |
| `role` | string | Accessibility role or best available role. |
| `visible` | boolean | Whether the element is visible. |
| `enabled` | boolean | Whether the element can be interacted with. |

Each `elements[]` item may include `type`, `label`, `text`, `value`, and `bounds`.

Must never appear in `PageState`:

- Password field values.
- Cookies, session storage, local storage, auth tokens, browser credentials, or API keys.
- Raw screenshots or full-page image bytes.
- Executable JavaScript or browser commands.

Valid example:

```json
{
  "schema_version": "1.0",
  "page_state_id": "PS_checkout_001",
  "captured_at": "2026-09-13T10:00:00Z",
  "url": "https://example.test/checkout",
  "title": "Checkout",
  "visible_text": "Checkout Contact Email savan@example.com Continue",
  "elements": [
    {
      "element_id": "EL_001",
      "role": "textbox",
      "type": "email",
      "label": "Email",
      "value": "savan@example.com",
      "visible": true,
      "enabled": true,
      "bounds": { "x": 24, "y": 120, "width": 320, "height": 40 }
    },
    {
      "element_id": "EL_002",
      "role": "button",
      "label": "Continue",
      "text": "Continue",
      "visible": true,
      "enabled": true
    }
  ]
}
```

Invalid examples:

```json
{
  "schema_version": "1.0",
  "page_state_id": "PS_checkout_001",
  "captured_at": "2026-09-13T10:00:00Z",
  "url": "https://example.test",
  "title": "Checkout",
  "visible_text": "Checkout",
  "elements": [
    {
      "element_id": "email-field",
      "role": "textbox",
      "visible": true,
      "enabled": true
    }
  ]
}
```

Invalid because `element_id` is not an opaque `EL_###` ID.

```json
{
  "schema_version": "1.0",
  "page_state_id": "PS_login_001",
  "captured_at": "2026-09-13T10:00:00Z",
  "url": "https://example.test/login",
  "title": "Login",
  "visible_text": "Login",
  "elements": [
    {
      "element_id": "EL_001",
      "role": "textbox",
      "type": "password",
      "label": "Password",
      "value": "real-password",
      "visible": true,
      "enabled": true
    }
  ]
}
```

Invalid by policy because password values must never be captured, even in raw `PageState`.

## Contract: SanitizedPageState

Purpose: privacy-checked page state from Member 2 to Member 3 for Agent reasoning.

Owner: Member 2 creates it from `PageState`. Member 3 may read it but must not restore raw values. Member 1 may use preserved `element_id` values later only through validated actions.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string, const `"1.0"` | Contract version. |
| `sanitized_state_id` | string, `SPS_*` | Unique sanitized snapshot ID. |
| `source_page_state_id` | string, `PS_*` | Source `PageState` ID. |
| `captured_at` | ISO date-time string | Sanitization timestamp. |
| `url` | string | Current browser URL. |
| `title` | string | Sanitized page title. |
| `visible_text` | string | Sanitized visible page text. |
| `elements` | array | Sanitized actionable/relevant elements. |
| `privacy_summary` | object | Redaction and sensitive-context summary. |

Optional fields: `accessibility_snapshot`, `visual_summary`, and `error`.

Each `elements[]` item requires `element_id`, `role`, `visible`, `enabled`, and `sensitivity`.

`sensitivity` values:

- `NONE`: no sensitive value or sensitive context detected.
- `SENSITIVE_CONTEXT`: element is in a sensitive context but no raw value is exposed.
- `REDACTED`: sensitive value was redacted or replaced with a placeholder.

Must never appear in `SanitizedPageState`:

- Original sensitive values.
- Placeholder-to-original-value mappings.
- Fields named or shaped as `original`, `raw_value`, `secret`, `token`, or `mapping`.
- Cookies, credentials, auth tokens, local storage, or session storage.
- Executable JavaScript or browser commands.

Valid example:

```json
{
  "schema_version": "1.0",
  "sanitized_state_id": "SPS_checkout_001",
  "source_page_state_id": "PS_checkout_001",
  "captured_at": "2026-09-13T10:00:01Z",
  "url": "https://example.test/checkout",
  "title": "Checkout",
  "visible_text": "Checkout Contact Email [EMAIL_1] Continue",
  "elements": [
    {
      "element_id": "EL_001",
      "role": "textbox",
      "type": "email",
      "label": "Email",
      "value": "[EMAIL_1]",
      "visible": true,
      "enabled": true,
      "sensitivity": "REDACTED",
      "redaction_placeholder": "[EMAIL_1]"
    },
    {
      "element_id": "EL_002",
      "role": "button",
      "label": "Continue",
      "text": "Continue",
      "visible": true,
      "enabled": true,
      "sensitivity": "NONE"
    }
  ],
  "privacy_summary": {
    "sensitive_context_detected": true,
    "redaction_count": 1,
    "categories": ["EMAIL"],
    "verification_passed": true
  }
}
```

Invalid example:

```json
{
  "schema_version": "1.0",
  "sanitized_state_id": "SPS_checkout_001",
  "source_page_state_id": "PS_checkout_001",
  "captured_at": "2026-09-13T10:00:01Z",
  "url": "https://example.test/checkout",
  "title": "Checkout",
  "visible_text": "Email savan@example.com",
  "elements": [],
  "privacy_summary": {
    "sensitive_context_detected": true,
    "redaction_count": 0,
    "categories": ["EMAIL"],
    "verification_passed": true
  }
}
```

Invalid by policy because it exposes the original email and claims verification passed without redaction.

## Contract: ActionPlan

Purpose: structured action request from Member 3 to the validator and browser layer.

Owner: Member 3 creates it. Member 3 validation/policy may approve or reject it. Member 1 executes only validated actions.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string, const `"1.0"` | Contract version. |
| `action_plan_id` | string, `AP_*` | Unique plan ID. |
| `source_sanitized_state_id` | string, `SPS_*` | Sanitized state used for planning. |
| `created_at` | ISO date-time string | Plan creation time. |
| `intent` | string | Short goal for the plan. |
| `actions` | array, 1-5 items | Machine-validatable action steps. |

Each action requires:

| Field | Type | Meaning |
| --- | --- | --- |
| `action_id` | string, `ACT_*` | Unique action ID. |
| `action_type` | enum | One of `CLICK`, `TYPE`, `SCROLL`, `SELECT`, `PRESS_KEY`, `WAIT`. |
| `reason` | string | Why this step is needed. |
| `risk_level` | enum | `LOW`, `MEDIUM`, or `HIGH`. |

Action-specific required fields:

| Action | Additional required fields |
| --- | --- |
| `CLICK` | `target_element_id` |
| `TYPE` | `target_element_id`, `input` |
| `SELECT` | `target_element_id`, `select` |
| `PRESS_KEY` | `key` |
| `SCROLL` | `scroll` |
| `WAIT` | `wait_ms` |

Only the fields listed for an action type may be present. For example, a `CLICK` action cannot include `input`, `select`, `key`, `scroll`, or `wait_ms`.

Must never appear in `ActionPlan`:

- Arbitrary JavaScript.
- CSS/XPath selectors as execution targets.
- Browser devtools commands.
- Network interception commands.
- Unrestricted navigation or file-system commands.
- Raw sensitive values copied from `SanitizedPageState`.

Valid example:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_checkout_001",
  "source_sanitized_state_id": "SPS_checkout_001",
  "created_at": "2026-09-13T10:00:02Z",
  "intent": "Continue from the checkout contact step.",
  "actions": [
    {
      "action_id": "ACT_continue_001",
      "action_type": "CLICK",
      "target_element_id": "EL_002",
      "reason": "The sanitized page shows a visible enabled Continue button.",
      "risk_level": "LOW"
    }
  ]
}
```

Valid `TYPE` example:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_search_001",
  "source_sanitized_state_id": "SPS_search_001",
  "created_at": "2026-09-13T10:00:02Z",
  "intent": "Enter the user-provided search query.",
  "actions": [
    {
      "action_id": "ACT_type_001",
      "action_type": "TYPE",
      "target_element_id": "EL_003",
      "input": {
        "source": "USER_TASK",
        "value": "privacy browser agent"
      },
      "reason": "The user asked to search for this phrase.",
      "risk_level": "LOW"
    }
  ]
}
```

Invalid examples:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_bad_001",
  "source_sanitized_state_id": "SPS_checkout_001",
  "created_at": "2026-09-13T10:00:02Z",
  "intent": "Run a page script.",
  "actions": [
    {
      "action_id": "ACT_bad_001",
      "action_type": "EXECUTE_SCRIPT",
      "script": "document.querySelector('button').click()",
      "reason": "Shortcut",
      "risk_level": "HIGH"
    }
  ]
}
```

Invalid because `EXECUTE_SCRIPT`, `script`, and selector-driven execution are not allowed.

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_bad_002",
  "source_sanitized_state_id": "SPS_checkout_001",
  "created_at": "2026-09-13T10:00:02Z",
  "intent": "Click continue.",
  "actions": [
    {
      "action_id": "ACT_bad_002",
      "action_type": "CLICK",
      "reason": "Continue",
      "risk_level": "LOW"
    }
  ]
}
```

Invalid because `CLICK` requires `target_element_id`.

## Contract: ActionResult

Purpose: browser execution outcome from Member 1 to Member 3.

Owner: Member 1 creates it after attempting a validated action. Member 3 reads it to decide whether to continue, retry, request a fresh observation, or stop.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string, const `"1.0"` | Contract version. |
| `action_plan_id` | string, `AP_*` | Plan ID this result belongs to. |
| `action_id` | string, `ACT_*` | Action ID this result belongs to. |
| `completed_at` | ISO date-time string | Execution completion time. |
| `status` | enum | Execution status. |
| `observed_change` | string | Sanitized description of browser-visible result. |
| `needs_fresh_page_state` | boolean | Whether Member 3 should request a new `PageState`. |

Status values:

- `SUCCESS`: action executed successfully.
- `STALE_ELEMENT`: target element no longer matched or no longer exists.
- `INVALID_ACTION`: action failed contract or executor validation.
- `EXECUTION_FAILED`: browser could not complete the action.
- `BLOCKED_BY_POLICY`: action was blocked by validation/policy before execution.
- `NEEDS_OBSERVATION`: executor needs a fresh page observation before continuing.
- `TIMEOUT`: action did not complete within the allowed time.

`error` is required when status is `STALE_ELEMENT`, `INVALID_ACTION`, `EXECUTION_FAILED`, `BLOCKED_BY_POLICY`, or `TIMEOUT`.

Must never appear in `ActionResult`:

- Raw sensitive page values.
- Cookies, tokens, browser credentials, local storage, or session storage.
- Raw stack traces containing page content or secrets.
- Full raw DOM dumps or screenshots.

Valid example:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_checkout_001",
  "action_id": "ACT_continue_001",
  "completed_at": "2026-09-13T10:00:03Z",
  "status": "SUCCESS",
  "observed_change": "Clicked Continue. The page appears to be loading the next checkout step.",
  "needs_fresh_page_state": true
}
```

Valid failure example:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_checkout_001",
  "action_id": "ACT_continue_001",
  "completed_at": "2026-09-13T10:00:03Z",
  "status": "STALE_ELEMENT",
  "observed_change": "Target element was not found during revalidation.",
  "needs_fresh_page_state": true,
  "error": {
    "code": "STALE_ELEMENT",
    "message": "The target element no longer matches the current page.",
    "retryable": true
  }
}
```

Invalid example:

```json
{
  "schema_version": "1.0",
  "action_plan_id": "AP_checkout_001",
  "action_id": "ACT_continue_001",
  "completed_at": "2026-09-13T10:00:03Z",
  "status": "STALE_ELEMENT",
  "observed_change": "Failed",
  "needs_fresh_page_state": true
}
```

Invalid because failure statuses require `error`.

## Shared ErrorDetail

Purpose: shared sanitized failure representation used wherever a contract needs to describe a boundary failure.

Owner: the module that detects the failure creates the error. Downstream modules may read it but must not add raw sensitive data.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `code` | enum | Stable machine-readable failure code. |
| `message` | string | Short sanitized human-readable message. |
| `retryable` | boolean | Whether retrying after a fresh observation or corrected input might work. |

Optional field:

| Field | Type | Meaning |
| --- | --- | --- |
| `details` | string | Sanitized debug context. |

Allowed `code` values:

- `SCHEMA_VALIDATION_FAILED`
- `PRIVACY_VIOLATION`
- `POLICY_BLOCKED`
- `STALE_ELEMENT`
- `INVALID_ACTION`
- `EXECUTION_FAILED`
- `TIMEOUT`
- `UNKNOWN`

Must never appear in `ErrorDetail`:

- Raw sensitive values.
- Original-value mappings.
- Cookies, tokens, credentials, or storage dumps.
- Raw DOM dumps, raw screenshots, or raw stack traces containing page content.

## Validation Approach

Each module boundary must run schema validation before accepting or emitting a payload:

1. Producer validates before sending.
2. Consumer validates before processing.
3. Validation failure returns or logs a sanitized `ErrorDetail` with `code: "SCHEMA_VALIDATION_FAILED"`.
4. Privacy verification failure returns or logs a sanitized `ErrorDetail` with `code: "PRIVACY_VIOLATION"`.
5. Policy or executor failures use the closest stable error/status value instead of free-form status strings.

JSON Schema catches malformed shape, missing required fields, invalid enum values, unsupported action types, non-opaque element IDs, extra fields, action-specific missing fields, and action-specific fields supplied to the wrong action type.

Privacy policy checks remain separate from JSON Schema because schemas cannot reliably detect every raw PII value. Member 2 must perform privacy verification before emitting `SanitizedPageState`.

## Lightweight Constraints

- Boundary payloads cap large arrays and strings to avoid bloated client-side processing.
- Action plans are capped at five actions per plan.
- Visual and accessibility summaries are optional to avoid unnecessary latency.
- Contracts avoid duplicate raw and sanitized fields in the same Agent-facing payload.

## Unresolved Interface Decisions

- Exact implementation language and validator library.
- Exact sensitive/PII detection implementation inside Member 2.
- Whether Member 2 placeholder mappings remain only in memory or have a temporary local debug store.
- Exact first prototype executor behavior for ambiguous `SCROLL` targets.
- Exact visual summary format beyond the lightweight string contract.

