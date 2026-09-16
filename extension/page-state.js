/**
 * page-state.js  — Day 2
 * Member 1 — Browser Perception Layer
 * Produces a PageState conforming exactly to page-state.schema.json v1.0
 *
 * Day 2 additions (over Day 1):
 *   - Improved accessible-name resolution (aria-describedby, alt, broken-ref
 *     handling, whitespace normalisation, duplicate-text suppression)
 *   - Expanded HTML5 implicit roles (ul, li, option, article, section, aside,
 *     figure, details, summary, dialog, table, th, td, fieldset, legend)
 *   - Open Shadow DOM traversal
 *   - Internal diff engine (never exposed in PageState)
 *   - Registry hardening: stale-node detection via WeakRef
 *
 * SECURITY RULES (enforced here):
 *   - Password input values are NEVER captured.
 *   - No external network requests are made.
 *   - No cookies, tokens, or credentials are captured.
 */

"use strict";

// ---------------------------------------------------------------------------
// Element Registry  (EL_xxx → WeakRef<Element>, in-memory only)
// Using WeakRef so stale/detached nodes can be detected without leaking memory.
// ---------------------------------------------------------------------------
const _registry = new Map(); // Map<string, WeakRef<Element>>
let _counter = 0;

function _nextId() {
  if (_counter >= 999999) throw new Error("Element ID space exhausted");
  _counter += 1;
  const padded = String(_counter).padStart(3, "0");
  return "EL_" + padded;
}

function _register(el) {
  const id = _nextId();
  _registry.set(id, new WeakRef(el));
  return id;
}

/** Reset registry between captures. */
function _resetRegistry() {
  _registry.clear();
}

/**
 * Resolve a live element from the registry.
 * Returns null if the node has been garbage-collected or detached.
 */
function _resolveRegistryEntry(id) {
  const ref = _registry.get(id);
  if (!ref) return null;
  const el = ref.deref();
  if (!el || !el.isConnected) return null;
  return el;
}

// ---------------------------------------------------------------------------
// Visibility
// ---------------------------------------------------------------------------
function _isVisible(el) {
  if (!el.isConnected) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return false;

  // Check the element and its ancestors, including an open shadow host.
  for (let current = el; current;) {
    const style = window.getComputedStyle(current);
    if (style.display === "none") return false;
    if (style.visibility === "hidden") return false;
    if (style.opacity === "0") return false;

    const root = current.getRootNode();
    current = current.parentElement;
    if (!current) {
      current = root && root.host ? root.host : null;
    }
  }

  return true;
}

// ---------------------------------------------------------------------------
// Enabled state
// ---------------------------------------------------------------------------
function _isEnabled(el) {
  if (el.getAttribute("aria-disabled") === "true") return false;
  if ("disabled" in el) return !el.disabled;
  return true;
}

// ---------------------------------------------------------------------------
// Bounds
// ---------------------------------------------------------------------------
function _bounds(el) {
  const r = el.getBoundingClientRect();
  return {
    x: Math.round(r.left),
    y: Math.round(r.top),
    width: Math.round(r.width),
    height: Math.round(r.height),
  };
}

// ---------------------------------------------------------------------------
// Accessible-name resolution  (Day 2 — improved)
//
// Priority order (ARIA spec §4.3 / AccName §2.1):
//   1. aria-label
//   2. aria-labelledby  (multiple IDs, broken refs silently skipped)
//   3. aria-describedby (fallback when no labelling mechanism found)
//   4. <label for="id">
//   5. wrapping <label>
//   6. placeholder
//   7. title
//   8. alt  (images / inputs with type=image)
//   9. ""
//
// All resolved strings are whitespace-normalised and capped at 500 chars.
// Duplicate text (label == element's own text content) is NOT suppressed here
// because the label field is independent of the text field.
// ---------------------------------------------------------------------------
function _normaliseText(s) {
  return (s || "").replace(/\s+/g, " ").trim();
}

function _label(el) {
  // 1. aria-label
  const ariaLabel = _normaliseText(el.getAttribute("aria-label"));
  if (ariaLabel) return ariaLabel.slice(0, 500);

  // 2. aria-labelledby — join multiple IDs, skip broken references silently
  const labelledBy = el.getAttribute("aria-labelledby");
  if (labelledBy) {
    const text = labelledBy
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => {
        const ref = document.getElementById(id);
        return ref ? _normaliseText(ref.textContent) : "";
      })
      .filter(Boolean)
      .join(" ")
      .trim();
    if (text) return text.slice(0, 500);
  }

  // 3. <label for="id">
  if (el.id) {
    const forLabel = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (forLabel) {
      const t = _normaliseText(forLabel.textContent);
      if (t) return t.slice(0, 500);
    }
  }

  // 4. wrapping <label> — strip nested form controls before reading text
  const parentLabel = el.closest("label");
  if (parentLabel) {
    const clone = parentLabel.cloneNode(true);
    clone.querySelectorAll("input,select,textarea,button").forEach((n) => n.remove());
    const t = _normaliseText(clone.textContent);
    if (t) return t.slice(0, 500);
  }

  // 5. placeholder
  const placeholder = _normaliseText(el.getAttribute("placeholder"));
  if (placeholder) return placeholder.slice(0, 500);

  // 6. title
  const title = _normaliseText(el.getAttribute("title"));
  if (title) return title.slice(0, 500);

  // 7. alt  (img, input[type=image])
  const alt = _normaliseText(el.getAttribute("alt"));
  if (alt) return alt.slice(0, 500);

  // 8. aria-describedby — last-resort fallback (lower priority than labelling)
  const describedBy = el.getAttribute("aria-describedby");
  if (describedBy) {
    const text = describedBy
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => {
        const ref = document.getElementById(id);
        return ref ? _normaliseText(ref.textContent) : "";
      })
      .filter(Boolean)
      .join(" ")
      .trim();
    if (text) return text.slice(0, 500);
  }

  return "";
}

// ---------------------------------------------------------------------------
// Role resolution  (Day 2 — expanded implicit roles)
// Priority: explicit ARIA role → native HTML semantic → safe generic fallback
// ---------------------------------------------------------------------------
function _role(el) {
  const explicit = _normaliseText(el.getAttribute("role"));
  if (explicit) return explicit.slice(0, 80);

  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute("type") || "").toLowerCase();

  // input variants
  if (tag === "input") {
    if (type === "checkbox") return "checkbox";
    if (type === "radio") return "radio";
    if (type === "submit" || type === "button" || type === "reset") return "button";
    if (type === "range") return "slider";
    if (type === "image") return "button";
    if (type === "search") return "searchbox";
    return "textbox";
  }

  // anchor: only link when href is present
  if (tag === "a") return el.hasAttribute("href") ? "link" : "generic";

  // ARIA 1.2: <section> is "region" only when it has an accessible name.
  if (tag === "section") {
    const hasName =
      el.getAttribute("aria-label")?.trim() ||
      el.getAttribute("aria-labelledby")?.trim() ||
      el.getAttribute("title")?.trim();
    return hasName ? "region" : "generic";
  }

  const map = {
    button:   "button",
    select:   "combobox",
    textarea: "textbox",
    h1: "heading", h2: "heading", h3: "heading",
    h4: "heading", h5: "heading", h6: "heading",
    label:    "label",
    img:      "img",
    nav:      "navigation",
    main:     "main",
    header:   "banner",
    footer:   "contentinfo",
    form:     "form",
    ul:       "list",
    ol:       "list",
    li:       "listitem",
    option:   "option",
    article:  "article",
    aside:    "complementary",
    figure:   "figure",
    details:  "group",
    summary:  "button",
    dialog:   "dialog",
    table:    "table",
    th:       "columnheader",
    td:       "cell",
    fieldset: "group",
    legend:   "legend",
  };

  return map[tag] || tag;
}

// ---------------------------------------------------------------------------
// Text content (normalised, no raw HTML)
// ---------------------------------------------------------------------------
function _text(el) {
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute("type") || "").toLowerCase();

  if (tag === "input") {
    if (type === "password") return ""; // NEVER capture password value as text
    return "";
  }
  if (tag === "select") {
    const opt = el.options[el.selectedIndex];
    return opt ? opt.text.trim().slice(0, 2000) : "";
  }
  if (tag === "textarea") return "";

  const raw = el.textContent || el.innerText || "";
  return raw.replace(/\s+/g, " ").trim().slice(0, 2000);
}

// ---------------------------------------------------------------------------
// Value (only for non-password inputs/textareas)
// ---------------------------------------------------------------------------
function _value(el) {
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute("type") || "").toLowerCase();

  if (type === "password") return undefined; // HARD RULE

  if (tag === "input" || tag === "textarea") {
    const v = el.value;
    if (v === undefined || v === null || v === "") return undefined;
    return String(v).slice(0, 2000);
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Element type field
// ---------------------------------------------------------------------------
function _type(el) {
  const tag = el.tagName.toLowerCase();
  if (tag === "input") return (el.getAttribute("type") || "text").toLowerCase().slice(0, 80);
  if (tag === "a") return "link";
  if (tag === "button") return "button";
  if (tag === "select") return "select";
  if (tag === "textarea") return "textarea";
  if (/^h[1-6]$/.test(tag)) return tag;
  return tag.slice(0, 80);
}

// ---------------------------------------------------------------------------
// Element selector — which elements to extract from a given root
// Day 2: added ul, ol, li, option, article, section, summary, dialog
// ---------------------------------------------------------------------------
const SELECTOR =
  "button, a[href], input:not([type='hidden']), textarea, select, " +
  "h1, h2, h3, h4, h5, h6, label, " +
  "ul, ol, li, option, article, section, summary, " +
  "[role='button'], [role='link'], [role='checkbox'], [role='radio'], " +
  "[role='textbox'], [role='combobox'], [role='menuitem'], [role='tab'], " +
  "[role='listitem'], [role='list']";

// ---------------------------------------------------------------------------
// PageState ID generator
// ---------------------------------------------------------------------------
function _pageStateId() {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let id = "PS_";
  for (let i = 0; i < 10; i++) id += chars[Math.floor(Math.random() * chars.length)];
  return id;
}

// ---------------------------------------------------------------------------
// Visible text (raw, for Member 2)
// ---------------------------------------------------------------------------
function _visibleText() {
  const walker = document.createTreeWalker(
    document.body,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        const p = node.parentElement;
        if (!p) return NodeFilter.FILTER_REJECT;
        const tag = p.tagName.toLowerCase();
        if (tag === "script" || tag === "style" || tag === "noscript") return NodeFilter.FILTER_REJECT;
        const style = window.getComputedStyle(p);
        if (style.display === "none" || style.visibility === "hidden") return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    }
  );
  const parts = [];
  let node;
  while ((node = walker.nextNode())) {
    const t = node.textContent.replace(/\s+/g, " ").trim();
    if (t) parts.push(t);
  }
  return parts.join(" ").slice(0, 20000);
}

// ---------------------------------------------------------------------------
// Deduplication set (cleared each capture)
// ---------------------------------------------------------------------------
const _seen = new Set();

// ---------------------------------------------------------------------------
// Shadow DOM traversal helper  (Day 2)
// Collects matching elements from a root, then recurses into open shadow roots.
// Closed shadow roots are intentionally skipped.
// ---------------------------------------------------------------------------
function _collectElements(root, results) {
  // querySelectorAll on the current root
  root.querySelectorAll(SELECTOR).forEach((el) => {
    if (!_seen.has(el)) {
      _seen.add(el);
      results.push(el);
    }
  });

  // Recurse into open shadow roots of ALL descendants
  root.querySelectorAll("*").forEach((el) => {
    if (el.shadowRoot) {
      // shadowRoot.mode === "open" is implied — closed roots return null
      _collectElements(el.shadowRoot, results);
    }
  });
}

// ---------------------------------------------------------------------------
// Internal Diff Engine  (Day 2 — never exposed in PageState)
//
// Maintains a lightweight fingerprint of the previous capture so that on
// re-capture we can classify each element as: existing | new | changed.
// Removed elements are those in the previous snapshot not seen in the new one.
//
// Fingerprint key: role + "|" + label + "|" + type + "|" + approxBounds
// approxBounds is quantised to 8px grid to tolerate minor layout shifts.
//
// The diff result is stored in _lastDiff and logged to console only.
// It is NOT added to PageState (frozen schema).
// ---------------------------------------------------------------------------
const _diffEngine = (() => {
  // _nodeFingerprint: stable DOM identity across captures.
  // WeakMap so entries are GC'd automatically when nodes are removed.
  // Never reset between captures — that is what gives it cross-capture identity.
  const _nodeFingerprint = new WeakMap(); // DOMElement → previous fingerprint string

  function _fingerprint(entry) {
    const bx = entry.bounds ? Math.round(entry.bounds.x / 8) : -1;
    const by = entry.bounds ? Math.round(entry.bounds.y / 8) : -1;
    return `${entry.role}|${entry.label || ""}|${entry.type || ""}|${bx},${by}`;
  }

  // pairs: Array<{ el: DOMElement, entry: PageStateElement }>
  function diff(pairs) {
    const result = { existing: 0, added: 0, changed: 0, removed: 0 };

    // Track which nodes are present this capture (for removed detection).
    const currentNodes = new Set();

    pairs.forEach(({ el, entry }) => {
      currentNodes.add(el);
      const fp = _fingerprint(entry);

      if (_nodeFingerprint.has(el)) {
        const prevFp = _nodeFingerprint.get(el);
        if (prevFp === fp) {
          result.existing++;
        } else {
          result.changed++;
        }
      } else {
        result.added++;
      }

      _nodeFingerprint.set(el, fp);
    });

    // Removed: nodes seen last capture that are no longer in the current set.
    // We track this via a separate Set of previously seen nodes.
    _diffEngine._prevNodes.forEach((el) => {
      if (!currentNodes.has(el)) result.removed++;
    });
    _diffEngine._prevNodes = currentNodes;

    return result;
  }

  return { diff, _prevNodes: new Set() };
})();

// ---------------------------------------------------------------------------
// Main capture function
// ---------------------------------------------------------------------------
function capturePageState() {
  const t0 = performance.now();
  _resetRegistry();
  _seen.clear();

  // Collect elements from main document + open shadow roots
  const allElements = [];
  _collectElements(document, allElements);

  const elements = [];
  const diffPairs = []; // parallel array for diff engine: {el, entry}

  allElements.forEach((el) => {
    const visible = _isVisible(el);
    const enabled = _isEnabled(el);
    const id = _register(el);

    const entry = {
      element_id: id,
      role: _role(el),
      visible,
      enabled,
    };

    const type = _type(el);
    if (type) entry.type = type;

    const label = _label(el);
    if (label !== "") entry.label = label;

    const text = _text(el);
    if (text !== "") entry.text = text;

    const value = _value(el);
    if (value !== undefined) entry.value = value;

    if (visible) entry.bounds = _bounds(el);

    elements.push(entry);
    diffPairs.push({ el, entry });
  });

  _seen.clear();

  // Run internal diff (result logged, never added to PageState)
  const diffResult = _diffEngine.diff(diffPairs);
  console.log(
    `[PageState] diff — existing:${diffResult.existing} added:${diffResult.added} ` +
    `changed:${diffResult.changed} removed:${diffResult.removed}`
  );

  const pageState = {
    schema_version: "1.0",
    page_state_id: _pageStateId(),
    captured_at: new Date().toISOString(),
    url: location.href.slice(0, 2048),
    title: (document.title || "").slice(0, 300),
    visible_text: _visibleText(),
    elements: elements.slice(0, 500),
  };

  const elapsed = (performance.now() - t0).toFixed(1);
  console.log(`[PageState] captured ${elements.length} elements in ${elapsed}ms`);

  return pageState;
}

// ---------------------------------------------------------------------------
// Inline schema validator (structural only — no external fetch)
// ---------------------------------------------------------------------------
function validatePageState(ps) {
  const errors = [];
  function check(cond, msg) { if (!cond) errors.push(msg); }

  check(ps.schema_version === "1.0", "schema_version must be '1.0'");
  check(/^PS_[A-Za-z0-9_-]{6,64}$/.test(ps.page_state_id), "page_state_id pattern mismatch");
  check(typeof ps.captured_at === "string" && !isNaN(Date.parse(ps.captured_at)), "captured_at invalid");
  check(typeof ps.url === "string" && ps.url.length >= 1 && ps.url.length <= 2048, "url invalid");
  check(typeof ps.title === "string" && ps.title.length <= 300, "title invalid");
  check(typeof ps.visible_text === "string" && ps.visible_text.length <= 20000, "visible_text invalid");
  check(Array.isArray(ps.elements) && ps.elements.length <= 500, "elements invalid");

  const allowedTopKeys = new Set([
    "schema_version", "page_state_id", "captured_at", "url", "title",
    "visible_text", "elements", "accessibility_snapshot", "visual_summary", "error"
  ]);
  Object.keys(ps).forEach((k) => check(allowedTopKeys.has(k), `unexpected top-level key: ${k}`));

  const allowedElKeys = new Set([
    "element_id", "role", "type", "label", "text", "value", "visible", "enabled", "bounds"
  ]);

  ps.elements.forEach((el, i) => {
    const pfx = `elements[${i}]`;
    check(/^EL_[0-9]{3,6}$/.test(el.element_id), `${pfx}.element_id pattern mismatch: ${el.element_id}`);
    check(typeof el.role === "string" && el.role.length >= 1 && el.role.length <= 80, `${pfx}.role invalid`);
    check(typeof el.visible === "boolean", `${pfx}.visible must be boolean`);
    check(typeof el.enabled === "boolean", `${pfx}.enabled must be boolean`);
    if (el.type !== undefined) check(typeof el.type === "string" && el.type.length <= 80, `${pfx}.type invalid`);
    if (el.label !== undefined) check(typeof el.label === "string" && el.label.length <= 500, `${pfx}.label invalid`);
    if (el.text !== undefined) check(typeof el.text === "string" && el.text.length <= 2000, `${pfx}.text invalid`);
    if (el.value !== undefined) check(
      (typeof el.value === "string" || el.value === null) &&
      (el.value === null || el.value.length <= 2000),
      `${pfx}.value invalid`
    );
    if (el.bounds !== undefined) {
      const b = el.bounds;
      check(
        typeof b.x === "number" && typeof b.y === "number" &&
        typeof b.width === "number" && typeof b.height === "number",
        `${pfx}.bounds fields must be numbers`
      );
      check(b.width >= 0 && b.height >= 0, `${pfx}.bounds width/height must be >= 0`);
      Object.keys(b).forEach((k) => check(
        ["x", "y", "width", "height"].includes(k),
        `${pfx}.bounds unexpected key: ${k}`
      ));
    }
    Object.keys(el).forEach((k) => check(allowedElKeys.has(k), `${pfx} unexpected key: ${k}`));
  });

  return errors;
}

// Expose for content.js
window.__pageStateCapture  = capturePageState;
window.__pageStateValidate = validatePageState;
window.__elementRegistry   = _registry;
window.__resolveRegistryEntry = _resolveRegistryEntry;
