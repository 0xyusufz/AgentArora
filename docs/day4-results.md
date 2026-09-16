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

## Day 4 — Batch 3 / URL & Category-Hint Hardening

- **Double-encoded URL path values**
  - **File/functions:** `src/tokenizer.py`, `_sanitize_url()` and `_decode_path_segment()`.
  - **Previous behavior:** A path such as `/profile/%2520Rahul%2520Sharma` was decoded only once, leaving an encoded sensitive value available to the Agent-facing URL.
  - **New behavior:** Each decoded path segment is decoded through a bounded two-layer pass before existing sensitive-value sanitization. URL structure and query/fragment removal remain unchanged.
  - **Why this was a real issue:** A supported sensitive value could bypass path detection through an additional encoding layer.
  - **Tests added:** Double-encoded person-name path coverage, including assertions that the raw value and encoded form are absent.
  - **Contract impact:** None; the URL remains a string under the frozen SanitizedPageState contract.
  - **Integration impact:** Member 3 receives the same URL structure without the exposed path value.
  - **Known limitations:** Decoding is intentionally bounded and does not claim to handle arbitrary encoding depth or unknown secret formats.

- **Category-hint mismatch**
  - **File/function:** `src/tokenizer.py`, `_span_matches()` (used by `_sanitize_element()`).
  - **Previous behavior:** A label hint such as `Name` could restrict matching to name spans even when the field value was an email, causing privacy verification to reject the whole state.
  - **New behavior:** Hinted matching retains priority, then supported generic categories scan the remaining content; overlapping matches continue to be resolved by the existing span-selection logic.
  - **Why this was a real issue:** A detectable sensitive value could cause a valid PageState to fail instead of producing a SanitizedPageState.
  - **Tests added:** Email sanitization under a `Name` label/hint.
  - **Contract impact:** None; token and summary values remain within the frozen schema.
  - **Integration impact:** Mismatched browser labels no longer cause avoidable Member 2-to-Member 3 processing failures when the value is otherwise supported.
  - **Known limitations:** Generic fallback is limited to existing tokenizer patterns and detector categories; it is not unlimited sensitive-data discovery.

## Day 5 — Blocker Fixes / Authentication & Malformed URL Hardening

- **Authentication credential values**
  - **Reproduction:** `API key: abc123secret` previously became `[AUTH_01]: abc123secret`.
  - **Previous behavior:** Authentication context was tokenized, but the value following supported labels such as `API key:` remained raw.
  - **New behavior:** Explicit credential-value patterns for supported authentication labels (`API key`, `auth token`, `passcode`, `recovery code`, `verification code`, and `security answer`) tokenize the associated value while preserving authentication detection.
  - **Functions changed:** `src/tokenizer.py`, authentication `CONTEXT_PATTERNS` and `_span_matches()`.
  - **Tests added:** `test_authentication_credential_value_is_redacted()` verifies the raw credential is absent from the serialized sanitized payload.
  - **Contract impact:** None. Existing token and summary categories remain within the frozen schema.
  - **Integration impact:** Agent-facing sanitized state no longer contains the supported authentication credential value.
  - **Remaining limitations:** Authentication matching remains limited to the explicitly supported labels and does not infer arbitrary secret formats.

- **Malformed percent-encoded URL paths**
  - **Reproduction:** `https://example.test/profile/%ZZRahul%20Sharma` previously became `https://example.test/profile/%25ZZRahul%20Sharma`, leaving `Rahul Sharma` raw.
  - **Previous behavior:** Invalid percent triplets prevented the existing name detector from seeing the underlying path value.
  - **New behavior:** Invalid percent triplets are converted to a path-safe delimiter before the existing bounded two-layer decode and sanitization pass. Valid encoding, path separators, URL structure, and query/fragment removal are preserved.
  - **Functions changed:** `src/tokenizer.py`, `_decode_path_segment()` and `_sanitize_url()`.
  - **Tests added:** `test_malformed_encoded_sensitive_url_path_is_redacted()` verifies both name components are absent and privacy verification passes.
  - **Contract impact:** None. Sanitized URLs remain strings under the frozen contract.
  - **Integration impact:** Supported sensitive values in malformed URL paths no longer reach Member 3 context.
  - **Remaining limitations:** Decoding remains bounded and malformed input outside supported detector patterns is not classified as sensitive.
