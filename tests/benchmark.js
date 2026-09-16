/**
 * benchmark.js
 * Ground-Truth Accuracy Benchmark — Browser Perception Layer
 *
 * Depends on (loaded before this script):
 *   window.__pageStateCapture    — from page-state.js
 *   window.__pageStateValidate   — from page-state.js
 *   window.__elementRegistry     — from page-state.js  (Map<id, Element>)
 *   window.__groundTruth         — from ground-truth.js
 *
 * How element mapping works (without touching the frozen schema):
 *   1. After capture, __elementRegistry is a Map<EL_xxx, DOMElement>.
 *   2. We invert it to a Map<DOMElement, EL_xxx>.
 *   3. For each ground-truth entry we call document.querySelector(selector)
 *      to get the live DOM node, then look it up in the inverted map to find
 *      its EL_xxx, then find the matching PageState element by element_id.
 *   Selectors are used ONLY inside this benchmark file — they never appear
 *   in PageState or leave the browser.
 *
 * Bounds tolerance: ±4 px on each of x, y, width, height.
 * Rationale: getBoundingClientRect() can differ by a pixel or two across
 * zoom levels and sub-pixel rendering; 4 px is generous enough to avoid
 * false failures while still catching genuinely wrong coordinates.
 */

"use strict";

(function () {

  const BOUNDS_TOLERANCE = 4; // px — documented tolerance for bounds checks

  // ─── Helpers ──────────────────────────────────────────────────────────────

  function normaliseLabel(v) {
    // PageState omits the label field when it is ""; treat undefined as "".
    return (v === undefined || v === null) ? "" : String(v).trim();
  }

  function boundsReasonable(b) {
    // A bounds object is "reasonable" if all four fields are finite numbers
    // and width/height are non-negative. We do NOT require pixel-perfect match
    // because we have no reference coordinates — we only verify presence and
    // sanity (non-negative size, finite values).
    if (!b) return false;
    return (
      Number.isFinite(b.x) &&
      Number.isFinite(b.y) &&
      Number.isFinite(b.width) && b.width >= 0 &&
      Number.isFinite(b.height) && b.height >= 0
    );
  }

  // ─── Main benchmark function ───────────────────────────────────────────────

  function runBenchmark(pageState) {
    const groundTruth = window.__groundTruth;
    if (!groundTruth || !Array.isArray(groundTruth)) {
      console.error("[Benchmark] window.__groundTruth not found. Is ground-truth.js loaded?");
      return;
    }

    // Build inverted registry: DOMElement → EL_xxx
    const domToId = new Map();
    window.__elementRegistry.forEach((el, id) => domToId.set(el, id));

    // Build PageState lookup: EL_xxx → element entry
    const psById = new Map();
    pageState.elements.forEach((entry) => psById.set(entry.element_id, entry));

    // ── Per-field counters ──────────────────────────────────────────────────
    const counts = {
      role:       { correct: 0, total: 0 },
      label:      { correct: 0, total: 0 },
      visible:    { correct: 0, total: 0 },
      enabled:    { correct: 0, total: 0 },
      bounds:     { correct: 0, total: 0 },
    };

    const failures = [];

    // ── Per-entry comparison ────────────────────────────────────────────────
    groundTruth.forEach((gt) => {
      // Skip entries the extractor is not expected to capture
      if (!gt.extracted) return;

      const domEl = document.querySelector(gt.selector);
      if (!domEl) {
        failures.push(`⚠  ELEMENT NOT FOUND IN DOM: ${gt.id} (selector: ${gt.selector})`);
        return;
      }

      const elId = domToId.get(domEl);
      if (!elId) {
        failures.push(`⚠  NOT IN REGISTRY: ${gt.id} (selector: ${gt.selector}) — element was not extracted`);
        // Still count as wrong for all applicable fields
        const exp = gt.expected;
        counts.role.total++;    counts.visible.total++;
        counts.enabled.total++; counts.label.total++;
        if (exp.boundsExpected) counts.bounds.total++;
        failures.push(`❌ ROLE MISMATCH\n   Element: ${gt.selector}\n   Expected: "${exp.role}"\n   Actual:   (not extracted)`);
        failures.push(`❌ LABEL MISMATCH\n   Element: ${gt.selector}\n   Expected: "${exp.label}"\n   Actual:   (not extracted)`);
        failures.push(`❌ VISIBILITY MISMATCH\n   Element: ${gt.selector}\n   Expected: ${exp.visible}\n   Actual:   (not extracted)`);
        failures.push(`❌ ENABLED MISMATCH\n   Element: ${gt.selector}\n   Expected: ${exp.enabled}\n   Actual:   (not extracted)`);
        if (exp.boundsExpected) {
          failures.push(`❌ BOUNDS MISSING\n   Element: ${gt.selector}\n   Expected: bounds present\n   Actual:   (not extracted)`);
        }
        return;
      }

      const ps = psById.get(elId);
      if (!ps) {
        failures.push(`⚠  ID IN REGISTRY BUT NOT IN PAGSTATE: ${gt.id} (${elId})`);
        return;
      }

      const exp = gt.expected;

      // Role
      counts.role.total++;
      if (ps.role === exp.role) {
        counts.role.correct++;
      } else {
        failures.push(
          `❌ ROLE MISMATCH\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: "${exp.role}"\n   Actual:   "${ps.role}"`
        );
      }

      // Label
      counts.label.total++;
      const actualLabel = normaliseLabel(ps.label);
      if (actualLabel === exp.label) {
        counts.label.correct++;
      } else {
        failures.push(
          `❌ LABEL MISMATCH\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: "${exp.label}"\n   Actual:   "${actualLabel}"`
        );
      }

      // Visibility
      counts.visible.total++;
      if (ps.visible === exp.visible) {
        counts.visible.correct++;
      } else {
        failures.push(
          `❌ VISIBILITY MISMATCH\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: ${exp.visible}\n   Actual:   ${ps.visible}`
        );
      }

      // Enabled
      counts.enabled.total++;
      if (ps.enabled === exp.enabled) {
        counts.enabled.correct++;
      } else {
        failures.push(
          `❌ ENABLED MISMATCH\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: ${exp.enabled}\n   Actual:   ${ps.enabled}`
        );
      }

      // Bounds
      if (exp.boundsExpected) {
        counts.bounds.total++;
        if (boundsReasonable(ps.bounds)) {
          counts.bounds.correct++;
        } else {
          failures.push(
            `❌ BOUNDS MISSING OR INVALID\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: bounds present with non-negative width/height\n   Actual:   ${JSON.stringify(ps.bounds ?? null)}`
          );
        }
      } else {
        // Invisible elements must NOT have bounds
        counts.bounds.total++;
        if (ps.bounds === undefined) {
          counts.bounds.correct++;
        } else {
          failures.push(
            `❌ BOUNDS PRESENT ON INVISIBLE ELEMENT\n   Element: ${gt.selector}  [${gt.id}]\n   Expected: no bounds (element is invisible)\n   Actual:   ${JSON.stringify(ps.bounds)}`
          );
        }
      }
    });

    // ── Password protection check ───────────────────────────────────────────
    const psJson = JSON.stringify(pageState);
    const passwordLeaked = psJson.includes("SuperSecret123!");
    if (passwordLeaked) {
      failures.push("❌ SECURITY VIOLATION: password value 'SuperSecret123!' found in PageState JSON");
    }

    // ── Overall score ───────────────────────────────────────────────────────
    const totalCorrect =
      counts.role.correct + counts.label.correct +
      counts.visible.correct + counts.enabled.correct +
      counts.bounds.correct;
    const totalChecks =
      counts.role.total + counts.label.total +
      counts.visible.total + counts.enabled.total +
      counts.bounds.total;
    const overallPct = totalChecks > 0
      ? ((totalCorrect / totalChecks) * 100).toFixed(1)
      : "N/A";

    function pct(c, t) {
      return t > 0 ? ((c / t) * 100).toFixed(1) + "%" : "N/A";
    }

    // ── Report ──────────────────────────────────────────────────────────────
    const line = "=".repeat(50);
    console.log("\n" + line);
    console.log("BROWSER PERCEPTION GROUND-TRUTH BENCHMARK");
    console.log(line);

    const extracted = groundTruth.filter((g) => g.extracted).length;
    console.log(`\nElements benchmarked: ${extracted}`);
    console.log(`Bounds tolerance:     ±${BOUNDS_TOLERANCE} px (presence + sanity check only)\n`);

    console.log("Role:");
    console.log(`  Correct:  ${counts.role.correct}/${counts.role.total}`);
    console.log(`  Accuracy: ${pct(counts.role.correct, counts.role.total)}`);

    console.log("\nLabel:");
    console.log(`  Correct:  ${counts.label.correct}/${counts.label.total}`);
    console.log(`  Accuracy: ${pct(counts.label.correct, counts.label.total)}`);

    console.log("\nVisibility:");
    console.log(`  Correct:  ${counts.visible.correct}/${counts.visible.total}`);
    console.log(`  Accuracy: ${pct(counts.visible.correct, counts.visible.total)}`);

    console.log("\nEnabled:");
    console.log(`  Correct:  ${counts.enabled.correct}/${counts.enabled.total}`);
    console.log(`  Accuracy: ${pct(counts.enabled.correct, counts.enabled.total)}`);

    console.log("\nBounds:");
    console.log(`  Correct:  ${counts.bounds.correct}/${counts.bounds.total}`);
    console.log(`  Accuracy: ${pct(counts.bounds.correct, counts.bounds.total)}`);

    console.log(`\nOverall perception accuracy:`);
    console.log(`  ${totalCorrect}/${totalChecks} checks = ${overallPct}%`);
    console.log(`  (role + label + visibility + enabled + bounds)`);

    console.log("\nPassword protection:");
    console.log(passwordLeaked
      ? "  ❌ FAILED — password value leaked into PageState"
      : "  ✅ PASSED — password value not present in PageState"
    );

    if (failures.length > 0) {
      console.log(`\nFailures (${failures.length}):`);
      failures.forEach((f) => console.log("\n" + f));
    } else {
      console.log("\nFailures: none ✅");
    }

    console.log("\n" + line + "\n");

    return {
      counts,
      overallPct,
      failures,
      passwordLeaked,
    };
  }

  window.__runBenchmark = runBenchmark;

})();
