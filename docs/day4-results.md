# Day 4 Detection Results

The controlled dataset is intentionally small and rule-based. Metrics are evidence for this dataset, not a claim of complete privacy classification.

| Dataset | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Existing PII categories (email through message) | 59 | 0 | 0 | 100.0% | 100.0% |
| New sensitive context categories | 15 | 2 | 0 | 88.2% | 100.0% |

The two new-category false positives were used to calibrate overly broad `doctor` and `login` rules. The final controlled cases report 15/15 true positives, 0 false negatives, and 0 false positives.

## Runtime And Size

One representative state measured on the local test run:

| Raw JSON bytes | Sanitized JSON bytes | Sanitization time |
|---:|---:|---:|
| 236 | 462 | 1.47 ms |

Sanitized state can be larger because it includes structural metadata, privacy summaries, and stable placeholders. Size is reported for comparison, not treated as a pass/fail target.

## Uncertainty Behavior

- Known sensitive phrases are replaced with category placeholders while safe surrounding text remains available.
- Unknown identifiers are not guessed or classified; they remain unchanged unless a known rule also matches the surrounding context.
- Page text containing instructions such as `ignore privacy rules` remains untrusted data. It cannot change the sanitizer or agent policy, and known sensitive content in the same text is still redacted.

## Batch 1 Privacy Boundary Fixes

- **PAN/account overlap:** `PrivacyTokenizer._span_matches()` now gives PAN/card-specific spans precedence over generic account-number spans. Previously a spaced card number could be partially replaced as an account number, leaving its final digits exposed. The complete value is now replaced with a `[PAN_##]` token.
- **Optional field types:** `PrivacyTokenizer.sanitize_page_state()` now enforces the frozen `PageState` contract before processing. `accessibility_snapshot` and `visual_summary` remain string-only fields; invalid list/object values are rejected rather than emitted into an invalid sanitized payload.
- **Boundary validation:** Member 2 validates both incoming `PageState` and generated `SanitizedPageState` with the existing `jsonschema` dependency and fails closed on contract violations.
- **SSN/PAN compatibility:** Token prefixes remain `[SSN_##]` and `[PAN_##]`, but the frozen sanitized category enum does not define `SSN` or `PAN`; those summary categories are represented as `OTHER` so the existing contract is not changed.

These fixes preserve the existing payload shape and do not expose the local token mapping. Remaining detector coverage is heuristic: verification is scoped to detected or mapped values, and unknown sensitive identifiers are still not inferred.

## Day 4 — Batch 2

### Privacy Detection & URL Path Hardening

- **URL path privacy**
  - **File:** `src/tokenizer.py`
  - **Function/area:** `_sanitize_url()`
  - **Previous behavior:** A sensitive value in a decoded URL path could remain unsanitized when the whole path did not match an existing detector shape, for example a name in `/profile/Rahul%20Sharma`.
  - **Why it was a problem:** URL paths are part of the Agent-facing state and could expose a sensitive value even when query and fragment data were removed.
  - **New behavior:** Decoded URL path segments are sanitized independently, then re-encoded and reconstructed. Query and fragment removal is unchanged.
  - **Privacy impact:** Names, emails, account-like values, and other already-supported sensitive spans in individual path segments are redacted without requiring an earlier token mapping.
  - **Integration impact:** URL structure, scheme, hostname, port, and path separators are preserved; query and fragment data remain omitted.
  - **Contract impact:** None. The sanitized URL remains a string within the frozen contract.
  - **Tests added:** URL-only name, encoded spaces, email, account-like path values, multiple path segments, and query/fragment removal in `tests/test_day4_detection.py`.
  - **Remaining limitations:** URL detection remains limited to existing detector patterns and does not claim exhaustive secret discovery.

- **Private/confidential element matching**
  - **File:** `src/tokenizer.py`
  - **Function/area:** `_span_matches()` category-hinted matching
  - **Previous behavior:** A `Message` hint restricted matching to message spans, so private-communication phrases such as `Please reply privately` or `do not share this` could remain and trigger the independent privacy check.
  - **Why it was a problem:** Valid private-communication content could fail sanitization instead of producing a sanitized state.
  - **New behavior:** Message-hinted fields also evaluate private-communication spans while preserving ordinary message-span behavior. Confidential labels continue using the existing confidential classification path.
  - **Privacy impact:** Private-communication phrases are now redacted before verification, avoiding raw phrase retention.
  - **Integration impact:** Sanitization succeeds for message elements containing private-communication wording; output remains available to the existing Agent boundary.
  - **Contract impact:** None. Existing token and summary enum values remain compatible.
  - **Tests added:** Message label plus text combinations for `Please reply privately`, `do not share this`, and `private conversation`, plus confidential element content in `tests/test_day4_detection.py`.
  - **Remaining limitations:** Category detection remains rule-based and heuristic; no exhaustive private/confidential classification is claimed.
