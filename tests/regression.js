"use strict";

(function () {
  function entryFor(state, element) {
    for (const [id, ref] of window.__elementRegistry) {
      const node = ref.deref ? ref.deref() : ref;
      if (node === element) {
        return state.elements.find((entry) => entry.element_id === id);
      }
    }
    return undefined;
  }

  function assert(condition, message, failures) {
    if (!condition) failures.push(message);
  }

  const failures = [];
  const fixture = document.createElement("div");
  fixture.id = "member1-regression-fixture";
  fixture.innerHTML = [
    '<button id="reg-native-disabled" disabled>Disabled</button>',
    '<button id="reg-native-aria-disabled" aria-disabled="true">ARIA disabled</button>',
    '<div id="reg-div-aria-disabled" role="button" aria-disabled="true">ARIA div</div>',
    '<button id="reg-enabled">Enabled</button>',
    '<div id="reg-opacity-parent" style="opacity: 0">',
    '  <button id="reg-opacity-child">Transparent child</button>',
    '</div>',
  ].join("");
  document.body.appendChild(fixture);

  const state = window.__pageStateCapture();
  const nativeDisabled = entryFor(state, document.getElementById("reg-native-disabled"));
  const nativeAriaDisabled = entryFor(state, document.getElementById("reg-native-aria-disabled"));
  const divAriaDisabled = entryFor(state, document.getElementById("reg-div-aria-disabled"));
  const enabled = entryFor(state, document.getElementById("reg-enabled"));
  const opacityChild = entryFor(state, document.getElementById("reg-opacity-child"));

  const oldId = nativeDisabled && nativeDisabled.element_id;
  const oldElement = document.getElementById("reg-native-disabled");
  const secondState = window.__pageStateCapture();
  const secondNativeDisabled = entryFor(secondState, oldElement);
  const currentId = secondNativeDisabled && secondNativeDisabled.element_id;

  assert(nativeDisabled && nativeDisabled.enabled === false, "native disabled control must be disabled", failures);
  assert(nativeAriaDisabled && nativeAriaDisabled.enabled === false, "native aria-disabled control must be disabled", failures);
  assert(divAriaDisabled && divAriaDisabled.enabled === false, "ARIA-disabled role control must be disabled", failures);
  assert(enabled && enabled.enabled === true, "normal native control must remain enabled", failures);
  assert(opacityChild && opacityChild.visible === false, "opacity-hidden descendant must be invisible", failures);
  assert(oldId && currentId && oldId !== currentId, "recapture must not reuse an old element ID", failures);
  assert(window.__resolveRegistryEntry(oldId) === null, "old capture element ID must be stale", failures);
  assert(currentId && window.__resolveRegistryEntry(currentId) === oldElement, "current capture element ID must resolve", failures);
  const thirdState = window.__pageStateCapture();
  assert(window.__resolveRegistryEntry(currentId) === null, "previous capture ID must be stale after another recapture", failures);
  assert(thirdState.elements.every((entry) => /^EL_[0-9]{3,6}$/.test(entry.element_id)), "repeated capture IDs must remain valid", failures);
  assert(window.__pageStateValidate(state).length === 0, "generated PageState must pass validation", failures);
  assert(!JSON.stringify(state).includes("SuperSecret123!"), "password value must not appear in PageState", failures);

  fixture.remove();
  const result = { passed: failures.length === 0, failures };
  window.__member1RegressionResults = result;
  console.log(`[Member1 regression] ${result.passed ? "PASS" : "FAIL"}`, result);
})();