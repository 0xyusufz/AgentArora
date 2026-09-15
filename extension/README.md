# Privacy-Preserving Browser Agent — Extension

**Member 1 | Browser Perception Layer**
Smart India Hackathon 2026

---

## What this is

A Chrome Manifest V3 content-script extension that observes a webpage and produces a **PageState** object conforming exactly to `page-state.schema.json` (schema version `1.0`).

No PII sanitization, no LLM, no action execution — this is the browser perception layer only. The `PageState` it produces is the input contract for the downstream privacy engine.

---

## Project structure

```
privacy-browser-agent/
├── extension/
│   ├── manifest.json       Chrome MV3 manifest
│   ├── page-state.js       Extraction engine + inline schema validator
│   ├── content.js          Orchestrator — runs capture, logs output, runs benchmark
│   ├── ground-truth.js     39 manually authored GT entries (GT-01–GT-39)
│   ├── benchmark.js        Automated benchmark runner
│   ├── diff-test.js        Diff engine verification script (not in manifest by default)
│   └── README.md           This file
├── test-page/
│   ├── index.html          Controlled banking-style test page (39 GT elements)
│   └── ground-truth.js     Mirror of extension/ground-truth.js
└── schemas/                Frozen cross-team contracts — DO NOT MODIFY
    ├── shared.schema.json
    ├── page-state.schema.json
    ├── sanitized-page-state.schema.json
    ├── action-plan.schema.json
    └── action-result.schema.json
```

---

## Setup

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The extension loads with no errors

---

## Running the test page

**Option A — file:// (simplest)**

```
File → Open File → test-page/index.html
```

**Option B — local HTTP server (recommended)**

```bash
cd privacy-browser-agent
python -m http.server 8080
# open: http://localhost:8080/test-page/index.html
```

---

## Console output

Open DevTools → **Console** after loading the test page:

```
=== PRIVACY-PRESERVING BROWSER AGENT ===
PAGE STATE
{ "schema_version": "1.0", "page_state_id": "PS_…", … }

[PageState] ✅ Schema validation PASSED
[PageState] diff — existing:0 added:N changed:0 removed:0
[PageState] captured N elements in X.Xms

[PageState] Element Registry
  EL_001 → A "Transactions"
  EL_002 → A "Profile"
  …

=== BENCHMARK ===
GT-01 … ✅
…
GT-39 … ✅
BENCHMARK RESULT: 39/39 passed
```

---

## PageState structure

```json
{
  "schema_version": "1.0",
  "page_state_id": "PS_Xk9mLpQr2w",
  "captured_at": "2026-09-14T10:30:00.000Z",
  "url": "http://localhost:8080/test-page/index.html",
  "title": "SecureBank — Benchmark Page",
  "visible_text": "SecureBank Dashboard Transactions Profile ...",
  "elements": [
    {
      "element_id": "EL_001",
      "role": "link",
      "type": "link",
      "label": "",
      "text": "Transactions",
      "visible": true,
      "enabled": true,
      "bounds": { "x": 100, "y": 16, "width": 100, "height": 32 }
    }
  ]
}
```

All fields conform to `page-state.schema.json`. No extra fields are added.

---

## Element registry

`page-state.js` maintains an in-memory `Map<string, WeakRef<Element>>`:

- IDs are opaque (`EL_NNN`) — they encode no semantic meaning
- Registry entries reset on each capture; IDs remain unique for the content-script lifetime
- `WeakRef` wrapping allows stale/detached nodes to be detected without memory leaks
- The registry is browser-local — never serialised or sent anywhere
- Pattern enforced: `^EL_[0-9]{3,6}$`

```js
// Resolve a live element by ID (returns null if detached/GC'd)
window.__resolveRegistryEntry("EL_001")

// Inspect the full registry
window.__elementRegistry.forEach((ref, id) => {
  const el = ref.deref();
  if (el) console.log(id, el.tagName, el.id);
});
```

---

## Accessible-name resolution (8-step priority chain)

| Priority | Source |
|---|---|
| 1 | `aria-label` |
| 2 | `aria-labelledby` (multiple IDs joined; broken refs silently skipped) |
| 3 | `<label for="id">` |
| 4 | Wrapping `<label>` (nested form controls stripped before reading text) |
| 5 | `placeholder` |
| 6 | `title` |
| 7 | `alt` (images, `input[type=image]`) |
| 8 | `aria-describedby` (last-resort fallback) |

All resolved strings are whitespace-normalised and capped at 500 characters.

---

## Role resolution (ARIA 1.2)

Priority: explicit `role` attribute → native HTML semantic → safe generic fallback.

Key rules:

- `<section>` with an accessible name (`aria-label` / `aria-labelledby` / `title`) → `"region"`
- `<section>` with no accessible name → `"generic"`
- `<a href>` → `"link"` ; `<a>` without `href` → `"generic"`
- `input[type=search]` → `"searchbox"`
- `<ul>` / `<ol>` → `"list"` ; `<li>` → `"listitem"`
- `<article>` → `"article"` ; `<aside>` → `"complementary"`
- `<dialog>` → `"dialog"` ; `<details>` → `"group"` ; `<summary>` → `"button"`
- `<table>` → `"table"` ; `<th>` → `"columnheader"` ; `<td>` → `"cell"`
- `<fieldset>` → `"group"` ; `<legend>` → `"legend"`

---

## Shadow DOM traversal

`_collectElements(root, results)` runs `querySelectorAll(SELECTOR)` on the given root, then recurses into open shadow roots of all descendants. Closed shadow roots (`shadowRoot === null`) are intentionally skipped. Elements are deduplicated across the full traversal.

---

## Internal diff engine

Tracks element identity across multiple captures using a `WeakMap<DOMElement, fingerprint>` that is **never reset** between captures.

- Fingerprint: `role|label|type|quantisedBounds` (bounds quantised to 8 px grid)
- Elements are classified as `existing`, `added`, `changed`, or `removed`
- `changed` increments when the same DOM node has a different fingerprint vs. the previous capture
- Result is logged to the console only — never added to `PageState`

---

## Visibility detection

An element is **visible** when ALL of the following hold:

- `el.isConnected === true`
- `getBoundingClientRect()` returns non-zero width AND height
- `computedStyle.display !== 'none'`
- `computedStyle.visibility !== 'hidden'`
- `computedStyle.opacity !== '0'`

---

## Enabled-state detection

- Native `disabled` property (covers `<input>`, `<button>`, `<select>`, `<textarea>`)
- `aria-disabled="true"` attribute on any element

---

## Password protection

`<input type="password">` values are **never captured**:

- `_text()` returns `""` for password inputs
- `_value()` returns `undefined` for password inputs
- The `value` field is therefore absent from the element entry entirely
- The test page has `#el-password` with `value="SuperSecret123!"` — this value will NOT appear anywhere in the PageState

Verify:

```js
JSON.stringify(window.__pageStateCapture()).includes("SuperSecret123!")
// must return: false
```

---

## Schema validation

`validatePageState()` checks every constraint from the frozen schema:

- `schema_version === "1.0"`
- `page_state_id` matches `^PS_[A-Za-z0-9_-]{6,64}$`
- `captured_at` is a valid ISO 8601 date-time string
- `url` length 1–2048
- `title` length ≤ 300
- `visible_text` length ≤ 20 000
- `elements` array ≤ 500 items
- Each element: `element_id` matches `^EL_[0-9]{3,6}$`
- Each element: `role` string 1–80 chars
- Each element: `visible` and `enabled` are booleans
- `bounds` fields are numbers, width/height ≥ 0
- No `additionalProperties` on top-level or element objects

---

## Ground-truth benchmark — 39 cases

| ID | Test | Expected |
|---|---|---|
| GT-01 | `<h1>` implicit role | `heading` |
| GT-02 | `<nav>` not in SELECTOR | not extracted |
| GT-03 | `<a>` text-content label | `link`, label `""` |
| GT-04 | `<a>` with `aria-label` | `link`, label `"Go to Profile"` |
| GT-05 | `aria-label` | `textbox`, label `"Full Name"` |
| GT-06 | `aria-labelledby` (two IDs) | `textbox`, label `"Account Number"` |
| GT-07 | `<label for>` | `textbox`, label `"Email Address"` |
| GT-08 | Wrapping `<label>` | `textbox`, label `"Date of Birth"` |
| GT-09 | `placeholder` fallback | `textbox`, label `"Search transactions"` |
| GT-10 | `title` fallback | `textbox`, label `"Reference Code"` |
| GT-11 | Unlabeled input | `textbox`, label `""` |
| GT-12 | `<button>` implicit role | `button` |
| GT-13 | `<a href>` implicit link | `link` |
| GT-14 | `<select>` | `combobox` |
| GT-15 | `<textarea>` | `textbox` |
| GT-16 | `input[type=checkbox]` | `checkbox` |
| GT-17 | `input[type=radio]` | `radio` |
| GT-18 | `<img>` not in SELECTOR | not extracted |
| GT-19 | Enabled button | `enabled: true` |
| GT-20 | `disabled` attribute | `enabled: false` |
| GT-21 | Disabled input | `enabled: false` |
| GT-22 | `aria-disabled="true"` | `enabled: false` |
| GT-23 | Visible button | `visible: true`, bounds present |
| GT-24 | `display:none` | `visible: false`, no bounds |
| GT-25 | `visibility:hidden` | `visible: false`, no bounds |
| GT-26 | `opacity:0` | `visible: false`, no bounds |
| GT-27 | Zero-size element | `visible: false`, no bounds |
| GT-28 | Password input | `role: textbox`, value absent |
| GT-29 | Change Password button | `button`, `enabled: true` |
| GT-30 | `aria-describedby` fallback | label `"Sort by date or amount"` |
| GT-31 | `input[type=search]` | `searchbox` |
| GT-32 | `<ul>` | `list` |
| GT-33 | `<li>` | `listitem` |
| GT-34 | `<article>` | `article` |
| GT-35 | Named `<section>` | `region`, label `"Quick Actions"` |
| GT-36 | Shadow DOM button | `button`, label `"Shadow Action"` |
| GT-37 | `<a>` without `href` | not extracted |
| GT-38 | Broken `aria-labelledby` | label `"Fallback placeholder"` |
| GT-39 | Unnamed `<section>` | `generic`, label `""` |

**Current result: 39/39 — 100%**

---

## Diff engine verification (diff-test.js)

To test cross-capture change detection:

1. Add `"diff-test.js"` to the `js` array in `manifest.json` (after `"content.js"`)
2. Reload the extension and open the test page
3. The script runs 5 captures with mutations on `#el-aria-label`
4. Expected output:

```
[DiffTest] C1 — existing:0   added:N   changed:0 removed:0
[DiffTest] C2 — existing:N   added:0   changed:0 removed:0
[DiffTest] C3 — existing:N-1 added:0   changed:1 removed:0
[DiffTest] C4 — existing:N-1 added:0   changed:1 removed:0
[DiffTest] C5 — existing:N   added:0   changed:0 removed:0
```

5. Remove `diff-test.js` from the manifest after testing

---

## Acceptance criteria

- [x] Chrome MV3 extension loads without errors
- [x] PageState is generated automatically at `document_idle`
- [x] PageState conforms to `page-state.schema.json`
- [x] `schema_version` is exactly `"1.0"`
- [x] `page_state_id` follows `^PS_[A-Za-z0-9_-]{6,64}$`
- [x] `captured_at` is valid ISO 8601
- [x] `url` and `title` are captured
- [x] `visible_text` is captured (≤ 20 000 chars)
- [x] 39 elements extracted and benchmarked
- [x] Every element has a valid opaque `EL_xxx` ID
- [x] `EL_xxx` IDs map locally to live DOM elements via WeakRef registry
- [x] Role, visibility, enabled state, label, and bounds captured correctly
- [x] Password values are never captured
- [x] Open shadow DOM elements are extracted
- [x] Named `<section>` → `region`; unnamed `<section>` → `generic`
- [x] Diff engine correctly classifies existing / added / changed / removed
- [x] No external API or network request is made
- [x] Frozen schemas remain completely unchanged
- [x] Benchmark passes 39/39

---

## Limitations

- Bounds are viewport-relative (not page-absolute); Y values shift if the page is scrolled before capture.
- Capture runs once at `document_idle`; SPA navigation does not trigger a re-capture.
- The inline validator is structural only — no full JSON Schema 2020-12 `$ref` resolution.
- `visible_text` is truncated at 20 000 characters per the schema limit.
- Closed shadow roots are not traversed by design.

---

## Security notes

- No network requests are made.
- `PageState` never leaves the browser.
- Password values are hard-blocked at the extraction layer.
- No cookies, tokens, or credentials are captured.
- Frozen schemas in `schemas/` are never modified.
