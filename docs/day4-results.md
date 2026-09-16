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
