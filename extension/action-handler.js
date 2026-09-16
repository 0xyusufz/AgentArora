/**
 * action-handler.js - Day 3 browser action execution layer.
 *
 * The handler accepts only the frozen ActionPlan shape and resolves opaque
 * element IDs through the browser-local registry from page-state.js.
 */

"use strict";

(function () {
  const ACTION_TYPES = new Set(["CLICK", "TYPE", "SCROLL", "SELECT", "PRESS_KEY", "WAIT"]);
  const RISK_LEVELS = new Set(["LOW", "MEDIUM", "HIGH"]);
  const INPUT_SOURCES = new Set(["USER_TASK", "SAFE_LITERAL", "PLACEHOLDER"]);
  const KEYS = new Set(["ENTER", "TAB", "ESCAPE", "ARROW_UP", "ARROW_DOWN", "ARROW_LEFT", "ARROW_RIGHT"]);
  const DIRECTIONS = new Set(["UP", "DOWN", "LEFT", "RIGHT"]);
  const AMOUNTS = new Set(["SMALL", "MEDIUM", "LARGE"]);
  const ACTION_RESULT_CODES = new Set([
    "SCHEMA_VALIDATION_FAILED", "PRIVACY_VIOLATION", "POLICY_BLOCKED",
    "STALE_ELEMENT", "INVALID_ACTION", "EXECUTION_FAILED", "TIMEOUT", "UNKNOWN"
  ]);
  const ACTION_ID = /^ACT_[A-Za-z0-9_-]{6,64}$/;
  const PLAN_ID = /^AP_[A-Za-z0-9_-]{6,64}$/;
  const STATE_ID = /^SPS_[A-Za-z0-9_-]{6,64}$/;
  const ELEMENT_ID = /^EL_[0-9]{3,6}$/;

  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function string(value, min, max) {
    return typeof value === "string" && value.length >= min && value.length <= max;
  }

  function errorResult(planId, actionId, status, code, message, retryable, fresh) {
    const safeCode = ACTION_RESULT_CODES.has(code) ? code : "UNKNOWN";
    return {
      schema_version: "1.0",
      action_plan_id: PLAN_ID.test(planId) ? planId : "AP_invalid_001",
      action_id: ACTION_ID.test(actionId) ? actionId : "ACT_invalid_001",
      completed_at: new Date().toISOString(),
      status,
      observed_change: "No browser action was executed.",
      needs_fresh_page_state: Boolean(fresh),
      error: { code: safeCode, message: message.slice(0, 500), retryable: Boolean(retryable) },
    };
  }

  function success(plan, action, message, fresh) {
    return {
      schema_version: "1.0",
      action_plan_id: plan.action_plan_id,
      action_id: action.action_id,
      completed_at: new Date().toISOString(),
      status: "SUCCESS",
      observed_change: message,
      needs_fresh_page_state: fresh,
    };
  }

  function invalidPlan(plan, action, message) {
    return errorResult(
      plan && plan.action_plan_id,
      action && action.action_id,
      "INVALID_ACTION",
      "SCHEMA_VALIDATION_FAILED",
      message,
      false,
      false
    );
  }

  function validateAction(action) {
    if (!object(action) || !string(action.action_id, 7, 71) || !ACTION_ID.test(action.action_id)) return "Action identity is invalid.";
    if (!ACTION_TYPES.has(action.action_type)) return "Action type is not supported.";
    if (!string(action.reason, 1, 500) || !RISK_LEVELS.has(action.risk_level)) return "Action metadata is invalid.";
    if (action.requires_user_confirmation !== undefined && typeof action.requires_user_confirmation !== "boolean") return "Action confirmation flag is invalid.";

    const common = new Set(["action_id", "action_type", "reason", "risk_level", "requires_user_confirmation"]);
    const allowed = {
      CLICK: new Set([...common, "target_element_id"]),
      TYPE: new Set([...common, "target_element_id", "input"]),
      SELECT: new Set([...common, "target_element_id", "select"]),
      PRESS_KEY: new Set([...common, "key"]),
      SCROLL: new Set([...common, "scroll"]),
      WAIT: new Set([...common, "wait_ms"]),
    }[action.action_type];
    if (Object.keys(action).some((key) => !allowed.has(key))) return "Action contains unsupported fields.";

    if (["CLICK", "TYPE", "SELECT"].includes(action.action_type) &&
        (!string(action.target_element_id, 6, 9) || !ELEMENT_ID.test(action.target_element_id))) return "Target element ID is invalid.";
    if (action.action_type === "TYPE" &&
        (!object(action.input) || Object.keys(action.input).some((key) => !["source", "value"].includes(key)) ||
         !INPUT_SOURCES.has(action.input.source) || !string(action.input.value, 1, 2000))) return "Type input is invalid.";
    if (action.action_type === "SELECT" &&
        (!object(action.select) || Object.keys(action.select).some((key) => key !== "option") || !string(action.select.option, 1, 500))) return "Select input is invalid.";
    if (action.action_type === "PRESS_KEY" && !KEYS.has(action.key)) return "Key is invalid.";
    if (action.action_type === "SCROLL" &&
        (!object(action.scroll) || Object.keys(action.scroll).some((key) => !["direction", "amount"].includes(key)) ||
         !DIRECTIONS.has(action.scroll.direction) || (action.scroll.amount !== undefined && !AMOUNTS.has(action.scroll.amount)))) return "Scroll input is invalid.";
    if (action.action_type === "WAIT" && (!Number.isInteger(action.wait_ms) || action.wait_ms < 100 || action.wait_ms > 5000)) return "Wait duration is invalid.";
    return null;
  }

  function validatePlan(plan) {
    const allowedPlanKeys = new Set(["schema_version", "action_plan_id", "source_sanitized_state_id", "created_at", "intent", "actions", "error"]);
    if (!object(plan) || Object.keys(plan).some((key) => !allowedPlanKeys.has(key)) || plan.schema_version !== "1.0" || !PLAN_ID.test(plan.action_plan_id) ||
        !STATE_ID.test(plan.source_sanitized_state_id) || typeof plan.created_at !== "string" || isNaN(Date.parse(plan.created_at)) ||
        !string(plan.intent, 1, 500) || !Array.isArray(plan.actions) || plan.actions.length < 1 || plan.actions.length > 5) {
      return { action: object(plan) && Array.isArray(plan.actions) ? plan.actions[0] : null, message: "ActionPlan failed contract validation." };
    }
    for (const action of plan.actions) {
      const message = validateAction(action);
      if (message) return { action, message };
    }
    return null;
  }

  function computedStyle(el) {
    return typeof window.getComputedStyle === "function" ? window.getComputedStyle(el) : {};
  }

  function visible(el) {
    if (!el || !el.isConnected) return false;
    const rect = typeof el.getBoundingClientRect === "function" ? el.getBoundingClientRect() : { width: 1, height: 1 };
    if (rect.width === 0 && rect.height === 0) return false;
    for (let current = el; current;) {
      const style = computedStyle(current);
      if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
      const root = current.getRootNode ? current.getRootNode() : null;
      current = current.parentElement;
      if (!current) {
        current = root && root.host ? root.host : null;
      }
    }
    return true;
  }

  function enabled(el) {
    return el.getAttribute("aria-disabled") !== "true" && !("disabled" in el && el.disabled);
  }

  function resolveTarget(action) {
    const registry = window.__elementRegistry;
    if (!registry || !registry.has(action.target_element_id)) return { error: "unknown" };
    const ref = registry.get(action.target_element_id);
    const el = ref && typeof ref.deref === "function" ? ref.deref() : ref;
    if (!el || !el.isConnected) return { error: "stale" };
    if (!visible(el)) return { error: "invisible" };
    if (!enabled(el)) return { error: "disabled" };
    return { el };
  }

  function clickTarget(el) {
    const tag = (el.tagName || "").toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase();
    const role = (el.getAttribute("role") || "").toLowerCase();
    return typeof el.click === "function" &&
      (tag === "button" || tag === "a" && el.hasAttribute("href") ||
       tag === "summary" || ["button", "link", "menuitem", "tab"].includes(role) ||
       tag === "input" && ["button", "submit", "reset", "image"].includes(type));
  }

  function typeTarget(el) {
    const tag = (el.tagName || "").toLowerCase();
    const type = (el.getAttribute("type") || "text").toLowerCase();
    return (tag === "textarea" || tag === "input" && ["text", "search", "email", "url", "tel", "number", "date", "datetime-local", "month", "week", "time"].includes(type) ||
      el.isContentEditable === true) && !el.readOnly && type !== "password";
  }

  function dispatch(el, type) {
    if (typeof el.dispatchEvent === "function") el.dispatchEvent(new Event(type, { bubbles: true }));
  }

  function executeAction(plan, action) {
    const fresh = ["CLICK", "TYPE", "SCROLL", "SELECT", "PRESS_KEY"].includes(action.action_type);
    if (["CLICK", "TYPE", "SELECT"].includes(action.action_type)) {
      const resolved = resolveTarget(action);
      if (resolved.error === "unknown") return errorResult(plan.action_plan_id, action.action_id, "INVALID_ACTION", "INVALID_ACTION", "Target element ID is not registered.", false, false);
      if (resolved.error === "stale") return errorResult(plan.action_plan_id, action.action_id, "STALE_ELEMENT", "STALE_ELEMENT", "Target element is no longer attached to the document.", true, true);
      if (resolved.error === "disabled") return errorResult(plan.action_plan_id, action.action_id, "BLOCKED_BY_POLICY", "POLICY_BLOCKED", "Target element is disabled.", false, false);
      if (resolved.error === "invisible") return errorResult(plan.action_plan_id, action.action_id, "BLOCKED_BY_POLICY", "POLICY_BLOCKED", "Target element is not visible.", true, true);
      const el = resolved.el;
      if (action.action_type === "CLICK") {
        if (!clickTarget(el)) return errorResult(plan.action_plan_id, action.action_id, "INVALID_ACTION", "INVALID_ACTION", "Target element is not an approved click target.", false, false);
        el.click();
        return success(plan, action, "Click executed successfully.", fresh);
      }
      if (action.action_type === "TYPE") {
        if (!typeTarget(el)) return errorResult(plan.action_plan_id, action.action_id, "BLOCKED_BY_POLICY", "POLICY_BLOCKED", "Target element is not an approved text input.", false, false);
        el.focus();
        el.value = action.input.value;
        dispatch(el, "input");
        dispatch(el, "change");
        return success(plan, action, "Text input updated successfully.", fresh);
      }
      if ((el.tagName || "").toLowerCase() !== "select") return errorResult(plan.action_plan_id, action.action_id, "INVALID_ACTION", "INVALID_ACTION", "Target element is not an approved select control.", false, false);
      const option = Array.from(el.options || []).find((candidate) => candidate.value === action.select.option || String(candidate.textContent || "").trim() === action.select.option);
      if (!option) return errorResult(plan.action_plan_id, action.action_id, "INVALID_ACTION", "INVALID_ACTION", "Requested option is not available.", false, false);
      el.value = option.value;
      dispatch(el, "input");
      dispatch(el, "change");
      return success(plan, action, "Selection updated successfully.", fresh);
    }

    if (action.action_type === "SCROLL") {
      const amount = { SMALL: 300, MEDIUM: 600, LARGE: 1000 }[action.scroll.amount || "MEDIUM"];
      const dx = action.scroll.direction === "LEFT" ? -amount : action.scroll.direction === "RIGHT" ? amount : 0;
      const dy = action.scroll.direction === "UP" ? -amount : action.scroll.direction === "DOWN" ? amount : 0;
      if (typeof window.scrollBy !== "function") throw new Error("Scroll is unavailable.");
      window.scrollBy(dx, dy);
      return success(plan, action, "Scroll executed successfully.", fresh);
    }

    if (action.action_type === "PRESS_KEY") {
      const target = document.activeElement || document;
      const key = { ENTER: "Enter", TAB: "Tab", ESCAPE: "Escape", ARROW_UP: "ArrowUp", ARROW_DOWN: "ArrowDown", ARROW_LEFT: "ArrowLeft", ARROW_RIGHT: "ArrowRight" }[action.key];
      target.dispatchEvent(new KeyboardEvent("keydown", { key, code: key, bubbles: true, cancelable: true }));
      target.dispatchEvent(new KeyboardEvent("keyup", { key, code: key, bubbles: true, cancelable: true }));
      return success(plan, action, "Key press dispatched successfully.", fresh);
    }

    return new Promise((resolve) => setTimeout(() => resolve(success(plan, action, "Wait completed successfully.", false)), action.wait_ms));
  }

  async function executeActionPlan(plan) {
    const validationError = validatePlan(plan);
    if (validationError) return [invalidPlan(plan, validationError.action, validationError.message)];
    const results = [];
    for (const action of plan.actions) {
      try {
        results.push(await executeAction(plan, action));
      } catch (error) {
        results.push(errorResult(plan.action_plan_id, action.action_id, "EXECUTION_FAILED", "EXECUTION_FAILED", "Browser action could not be completed.", true, false));
      }
    }
    return results;
  }

  window.__executeActionPlan = executeActionPlan;
  window.__handleActionPlan = executeActionPlan;

  if (window.chrome && window.chrome.runtime && window.chrome.runtime.onMessage) {
    window.chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (!message || message.type !== "EXECUTE_ACTION_PLAN") return false;
      executeActionPlan(message.action_plan).then((action_results) => {
        sendResponse({ type: "ACTION_RESULTS", action_results });
      });
      return true;
    });
  }
})();
