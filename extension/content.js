/**
 * content.js
 * Browser perception bootstrap and schema gate.
 *
 * SECURITY:
 * - Raw PageState is never written to the console.
 * - Element registry contents are never written to the console.
 * - PII sanitization remains the responsibility of the privacy engine.
 */

"use strict";

(function () {
  function run() {
    const pageState = window.__pageStateCapture();
    const schemaErrors = window.__pageStateValidate(pageState);

    // Do not log pageState, element labels, values, visible text, or registry
    // contents. The browser perception layer may contain raw sensitive data.
    if (schemaErrors.length !== 0) {
      schemaErrors.forEach((error) => {
        console.error("[PageState] schema validation failed:", error);
      });
    }
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", run, { once: true });
  }
})();
