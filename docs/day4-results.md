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
