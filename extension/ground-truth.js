/**
 * ground-truth.js  — Day 2
 *
 * Manually authored expected values for the browser perception benchmark.
 * Derived by reading the HTML source directly — NOT by calling any extractor.
 *
 * GT-01 … GT-29  — Day 1 cases (unchanged)
 * GT-30 … GT-38  — Day 2 additions
 *
 * Each entry:
 *   selector       — CSS selector that uniquely identifies the DOM element
 *   id             — human-readable test ID for failure messages
 *   extracted      — true if expected to appear in PageState
 *   shadowSelector — (optional) CSS selector inside a shadow root; when set,
 *                    the benchmark looks up the element via the host's shadowRoot
 *   expected:
 *     role           — expected role string
 *     label          — expected label string ("" means no label expected)
 *     visible        — expected visibility boolean
 *     enabled        — expected enabled boolean
 *     boundsExpected — true if bounds should be present
 *
 * Bounds tolerance: ±4 px (presence + sanity check only).
 */

"use strict";

window.__groundTruth = [

  // ── GT-01 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-h1",
    id: "GT-01 <h1> implicit heading role",
    extracted: true,
    expected: { role: "heading", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-02 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-nav",
    id: "GT-02 <nav> not in SELECTOR (skip)",
    extracted: false,
    expected: {},
  },

  // ── GT-03 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-link-transactions",
    id: "GT-03 <a> text-content label",
    extracted: true,
    expected: { role: "link", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-04 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-link-profile",
    id: "GT-04 <a> aria-label overrides text",
    extracted: true,
    expected: { role: "link", label: "Go to Profile", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-05 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-aria-label",
    id: "GT-05 aria-label",
    extracted: true,
    expected: { role: "textbox", label: "Full Name", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-06 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-aria-labelledby",
    id: "GT-06 aria-labelledby (two IDs joined)",
    extracted: true,
    expected: { role: "textbox", label: "Account Number", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-07 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-label-for",
    id: "GT-07 <label for>",
    extracted: true,
    expected: { role: "textbox", label: "Email Address", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-08 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-wrapping-label",
    id: "GT-08 wrapping <label>",
    extracted: true,
    expected: { role: "textbox", label: "Date of Birth", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-09 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-placeholder-label",
    id: "GT-09 placeholder fallback label",
    extracted: true,
    expected: { role: "textbox", label: "Search transactions", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-10 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-title-label",
    id: "GT-10 title fallback label",
    extracted: true,
    expected: { role: "textbox", label: "Reference Code", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-11 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-no-label",
    id: "GT-11 unlabeled input",
    extracted: true,
    expected: { role: "textbox", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-12 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-button",
    id: "GT-12 <button> implicit role",
    extracted: true,
    expected: { role: "button", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-13 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-link-support",
    id: "GT-13 <a href> implicit link role",
    extracted: true,
    expected: { role: "link", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-14 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-select",
    id: "GT-14 <select> → combobox role",
    extracted: true,
    expected: { role: "combobox", label: "Category", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-15 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-textarea",
    id: "GT-15 <textarea> → textbox role",
    extracted: true,
    expected: { role: "textbox", label: "Notes", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-16 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-checkbox",
    id: "GT-16 <input type=checkbox> → checkbox role",
    extracted: true,
    expected: { role: "checkbox", label: "Show debits only", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-17 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-radio",
    id: "GT-17 <input type=radio> → radio role",
    extracted: true,
    expected: { role: "radio", label: "This month", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-18 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-img",
    id: "GT-18 <img> not in SELECTOR (skip)",
    extracted: false,
    expected: {},
  },

  // ── GT-19 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-btn-enabled",
    id: "GT-19 enabled button",
    extracted: true,
    expected: { role: "button", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-20 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-btn-disabled",
    id: "GT-20 disabled button (HTML attribute)",
    extracted: true,
    expected: { role: "button", label: "", visible: true, enabled: false, boundsExpected: true },
  },

  // ── GT-21 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-input-disabled",
    id: "GT-21 disabled input (HTML attribute)",
    extracted: true,
    expected: { role: "textbox", label: "Account Number (read-only)", visible: true, enabled: false, boundsExpected: true },
  },

  // ── GT-22 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-aria-disabled",
    id: "GT-22 aria-disabled=true on role=button",
    extracted: true,
    expected: { role: "button", label: "Locked Action", visible: true, enabled: false, boundsExpected: true },
  },

  // ── GT-23 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-btn-visible",
    id: "GT-23 visible button",
    extracted: true,
    expected: { role: "button", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-24 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-display-none",
    id: "GT-24 display:none → visible=false",
    extracted: true,
    expected: { role: "button", label: "", visible: false, enabled: true, boundsExpected: false },
  },

  // ── GT-25 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-vis-hidden",
    id: "GT-25 visibility:hidden → visible=false",
    extracted: true,
    expected: { role: "button", label: "", visible: false, enabled: true, boundsExpected: false },
  },

  // ── GT-26 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-opacity-zero",
    id: "GT-26 opacity:0 → visible=false",
    extracted: true,
    expected: { role: "button", label: "", visible: false, enabled: true, boundsExpected: false },
  },

  // ── GT-27 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-zero-size",
    id: "GT-27 zero-size element → visible=false",
    extracted: true,
    expected: { role: "button", label: "", visible: false, enabled: true, boundsExpected: false },
  },

  // ── GT-28 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-password",
    id: "GT-28 password input (value must not be captured)",
    extracted: true,
    expected: { role: "textbox", label: "Current Password", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-29 ────────────────────────────────────────────────────────────────
  {
    selector: "#el-btn-change-pwd",
    id: "GT-29 Change Password button",
    extracted: true,
    expected: { role: "button", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ════════════════════════════════════════════════════════════════════════
  // Day 2 additions
  // ════════════════════════════════════════════════════════════════════════

  // ── GT-30: aria-describedby fallback (no higher-priority label source) ───
  {
    selector: "#el-aria-describedby",
    id: "GT-30 aria-describedby fallback label",
    extracted: true,
    expected: { role: "textbox", label: "Sort by date or amount", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-31: input[type=search] → searchbox role ───────────────────────────
  {
    selector: "#el-search-input",
    id: "GT-31 input[type=search] → searchbox role",
    extracted: true,
    expected: { role: "searchbox", label: "Search accounts", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-32: <ul> → list role ───────────────────────────────────────────────
  {
    selector: "#el-ul",
    id: "GT-32 <ul> → list role",
    extracted: true,
    expected: { role: "list", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-33: <li> → listitem role ───────────────────────────────────────────
  {
    selector: "#el-li-first",
    id: "GT-33 <li> → listitem role",
    extracted: true,
    expected: { role: "listitem", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-34: <article> → article role ──────────────────────────────────────
  {
    selector: "#el-article",
    id: "GT-34 <article> → article role",
    extracted: true,
    expected: { role: "article", label: "", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-35: <section aria-label> → region role ────────────────────────────
  {
    selector: "#el-section",
    id: "GT-35 <section> → region role",
    extracted: true,
    expected: { role: "region", label: "Quick Actions", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-36: Shadow DOM button (inside open shadow root) ───────────────────
  // The element lives inside #el-shadow-host's shadow tree.
  // The benchmark uses shadowSelector to locate it.
  {
    selector: "#el-shadow-host",
    id: "GT-36 shadow DOM button (open shadow root)",
    extracted: true,
    shadowSelector: "#el-shadow-btn",
    expected: { role: "button", label: "Shadow Action", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-37: <a> without href → generic role ───────────────────────────────
  {
    selector: "#el-anchor-no-href",
    id: "GT-37 <a> without href → generic role",
    extracted: false,   // a[href] selector — no href means not matched by SELECTOR
    expected: {},
  },

  // ── GT-38: broken aria-labelledby → falls through to placeholder ─────────
  {
    selector: "#el-broken-labelledby",
    id: "GT-38 broken aria-labelledby → placeholder fallback",
    extracted: true,
    expected: { role: "textbox", label: "Fallback placeholder", visible: true, enabled: true, boundsExpected: true },
  },

  // ── GT-39: unnamed <section> → generic role (ARIA 1.2) ───────────────────
  {
    selector: "#el-section-unnamed",
    id: "GT-39 unnamed <section> → generic role",
    extracted: true,
    expected: { role: "generic", label: "", visible: true, enabled: true, boundsExpected: true },
  },

];
