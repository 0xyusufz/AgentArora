/**
 * benchmark.js  — Day 2
 * Ground-Truth Accuracy Benchmark — Browser Perception Layer
 *
 * Depends on (loaded before this script):
 *   window.__pageStateCapture    — from page-state.js
 *   window.__pageStateValidate   — from page-state.js
 *   window.__elementRegistry     — from page-state.js  (Map<id, WeakRef<Element>>)
 *   window.__groundTruth         — from ground-truth.js
 *
 * Element mapping strategy:
 *   1. After capture, __elementRegistry is Map<EL_xxx, WeakRef<Element>>.
 *   2. We invert it to Map<DOMElement, EL_xxx>.
 *   3. For each ground-truth entry we resolve the DOM node:
 *      - Normal entries: document.querySelector(selector)
 *      - Shadow entries (shadowSelector set): host.shadowRoot.querySelector(shadowSelector)
 *   4. Look up the DOM node in the inverted map → EL_xxx → PageState entry.
 *   Selectors are used ONLY inside this file — never appear in PageState.
 *
 * Bounds tolerance: ±4 px (presence + sanity check only).
 */

"use strict";

(function () {

  const BOUNDS_TOLERANCE = 4;

  function normaliseLabel(v) {
    return (v === undefined || v === null) ? "" : String(v).trim();
  }

  function boundsReasonable(b) {
    if (!b) return false;
    return (
      Number.isFinite(b.x) && Number.isFinite(b.y) &&
      Number.isFinite(b.width) && b.width >= 0 &&
      Number.isFinite(b.height) && b.height >= 0
    );
  }

  // Resolve the DOM element for a ground-truth entry.
  // For shadow entries, navigate into the open shadow root.
  function resolveDomElement(gt) {
    if (gt.shadowSelector) {
      const host = document.querySelector(gt.selector);
      if (!host || !host.shadowRoot) return null;
      return host.shadowRoot.querySelector(gt.shadowSelector);
    }
    return document.querySelector(gt.selector);
  }

  function runBenchmark(pageState) {
    const groundTruth = window.__groundTruth;
    if (!groundTruth || !Array.isArray(groundTruth)) {
      console.error("[Benchmark] window.__groundTruth not found.");
      return;
    }

    // Build inverted registry: DOMElement → EL_xxx
    const domToId = new Map();
    window.__elementRegistry.forEach((ref, id) => {
      const el = ref.deref ? ref.deref() : ref; // support both WeakRef and raw Element
      if (el) domToId.set(el, id);
    });

    // Build PageState lookup: EL_xxx → element entry
    const psById = new Map();
    pageState.elements.forEach((entry) => psById.set(entry.element_id, entry));

    const counts = {
      role:    { correct: 0, total: 0 },
      label:   { correct: 0, total: 0 },
      visible: { correct: 0, total: 0 },
      enabled: { correct: 0, total: 0 },
      bounds:  { correct: 0, total: 0 },
    };
    const failures = [];

    groundTruth.forEach((gt) => {
      if (!gt.extracted) return;

      const domEl = resolveDomElement(gt);
      if (!domEl) {
        failures.push(`⚠  ELEMENT NOT FOUND IN DOM: ${gt.id}`);
        const exp = gt.expected;
        counts.role.total++; counts.visible.total++;
        counts.enabled.total++; counts.label.total++;
        if (exp.boundsExpected) counts.bounds.total++;
        return;
      }

      const elId = domToId.get(domEl);
      if (!elId) {
        failures.push(`⚠  NOT IN REGISTRY: ${gt.id} — element was not extracted`);
        const exp = gt.expected;
        counts.role.total++; counts.visible.total++;
        counts.enabled.total++; counts.label.total++;
        if (exp.boundsExpected) counts.bounds.total++;
        failures.push(`❌ ROLE    expected:"${exp.role}" actual:(not extracted)  [${gt.id}]`);
        failures.push(`❌ LABEL   expected:"${exp.label}" actual:(not extracted)  [${gt.id}]`);
        failures.push(`❌ VISIBLE expected:${exp.visible} actual:(not extracted)  [${gt.id}]`);
        failures.push(`❌ ENABLED expected:${exp.enabled} actual:(not extracted)  [${gt.id}]`);
        if (exp.boundsExpected) failures.push(`❌ BOUNDS  expected:present actual:(not extracted)  [${gt.id}]`);
        return;
      }

      const ps = psById.get(elId);
      if (!ps) {
        failures.push(`⚠  ID IN REGISTRY BUT NOT IN PAGESTATE: ${gt.id} (${elId})`);
        return;
      }

      const exp = gt.expected;

      // Role
      counts.role.total++;
      if (ps.role === exp.role) {
        counts.role.correct++;
      } else {
        failures.push(`❌ ROLE    expected:"${exp.role}" actual:"${ps.role}"  [${gt.id}]`);
      }

      // Label
      counts.label.total++;
      const actualLabel = normaliseLabel(ps.label);
      if (actualLabel === exp.label) {
        counts.label.correct++;
      } else {
        failures.push(`❌ LABEL   expected:"${exp.label}" actual:"${actualLabel}"  [${gt.id}]`);
      }

      // Visibility
      counts.visible.total++;
      if (ps.visible === exp.visible) {
        counts.visible.correct++;
      } else {
        failures.push(`❌ VISIBLE expected:${exp.visible} actual:${ps.visible}  [${gt.id}]`);
      }

      // Enabled
      counts.enabled.total++;
      if (ps.enabled === exp.enabled) {
        counts.enabled.correct++;
      } else {
        failures.push(`❌ ENABLED expected:${exp.enabled} actual:${ps.enabled}  [${gt.id}]`);
      }

      // Bounds
      if (exp.boundsExpected) {
        counts.bounds.total++;
        if (boundsReasonable(ps.bounds)) {
          counts.bounds.correct++;
        } else {
          failures.push(`❌ BOUNDS  expected:present actual:${JSON.stringify(ps.bounds ?? null)}  [${gt.id}]`);
        }
      } else {
        counts.bounds.total++;
        if (ps.bounds === undefined) {
          counts.bounds.correct++;
        } else {
          failures.push(`❌ BOUNDS  expected:absent actual:${JSON.stringify(ps.bounds)}  [${gt.id}]`);
        }
      }
    });

    // Password protection check
    const psJson = JSON.stringify(pageState);
    const passwordLeaked = psJson.includes("SuperSecret123!");
    if (passwordLeaked) {
      failures.push("❌ SECURITY VIOLATION: password value 'SuperSecret123!' found in PageState JSON");
    }

    // Score
    const totalCorrect =
      counts.role.correct + counts.label.correct +
      counts.visible.correct + counts.enabled.correct + counts.bounds.correct;
    const totalChecks =
      counts.role.total + counts.label.total +
      counts.visible.total + counts.enabled.total + counts.bounds.total;
    const overallPct = totalChecks > 0
      ? ((totalCorrect / totalChecks) * 100).toFixed(1)
      : "N/A";

    function pct(c, t) { return t > 0 ? ((c / t) * 100).toFixed(1) + "%" : "N/A"; }

    const line = "=".repeat(52);
    console.log("\n" + line);
    console.log("BROWSER PERCEPTION GROUND-TRUTH BENCHMARK — Day 2");
    console.log(line);

    const extracted = groundTruth.filter((g) => g.extracted).length;
    console.log(`\nElements benchmarked: ${extracted}`);
    console.log(`Bounds tolerance:     ±${BOUNDS_TOLERANCE} px (presence + sanity)\n`);

    [["Role", "role"], ["Label", "label"], ["Visibility", "visible"],
     ["Enabled", "enabled"], ["Bounds", "bounds"]].forEach(([name, key]) => {
      const c = counts[key];
      console.log(`${name}:\n  ${c.correct}/${c.total}  ${pct(c.correct, c.total)}`);
    });

    console.log(`\nOverall: ${totalCorrect}/${totalChecks} = ${overallPct}%`);
    console.log(`  (role + label + visibility + enabled + bounds)`);

    console.log("\nPassword protection:");
    console.log(passwordLeaked
      ? "  ❌ FAILED — password value leaked into PageState"
      : "  ✅ PASSED — password value not present in PageState"
    );

    if (failures.length > 0) {
      console.log(`\nFailures (${failures.length}):`);
      failures.forEach((f) => console.log("  " + f));
    } else {
      console.log("\nFailures: none ✅");
    }

    console.log("\n" + line + "\n");

    return { counts, overallPct, failures, passwordLeaked };
  }

  window.__runBenchmark = runBenchmark;

})();
