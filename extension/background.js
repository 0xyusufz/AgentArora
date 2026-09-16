"use strict";

const BRIDGE_URL = "http://127.0.0.1:8765";
const POLL_ALARM = "local-browser-bridge-poll";
const POLL_PERIOD_MINUTES = 0.5;
let pollInFlight = false;

async function postResult(requestId, actionResults) {
  await fetch(`${BRIDGE_URL}/action-result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId, action_results: actionResults }),
  });
}

function reloadTabAndWait(tabId) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timeout = setTimeout(() => finish(new Error("Timed out waiting for the test tab to reload.")), 10000);

    function finish(error) {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      chrome.tabs.onUpdated.removeListener(onUpdated);
      if (error) reject(error);
      else resolve();
    }

    function onUpdated(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") finish();
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.reload(tabId).catch(finish);
  });
}

async function sendAction(tabId, message) {
  try {
    return await chrome.tabs.sendMessage(tabId, message);
  } catch (error) {
    console.info("[Bridge] content listener missing; reloading static content scripts", tabId);
    await reloadTabAndWait(tabId);
    return chrome.tabs.sendMessage(tabId, message);
  }
}

async function pollOnce() {
  if (pollInFlight) return;
  pollInFlight = true;
  try {
    const response = await fetch(`${BRIDGE_URL}/next-action`, { cache: "no-store" });
    if (response.status !== 200) return;

    const envelope = await response.json();
    console.info("[Bridge] /next-action consumed", envelope.request_id);

    const tabs = await chrome.tabs.query({});
    const testTabs = tabs.filter((candidate) =>
      typeof candidate.url === "string" &&
      candidate.url.startsWith("http://localhost:8080/test-page/")
    );
    console.info(
      "[Bridge] matching test tabs",
      testTabs.map((t) => ({ id: t.id, url: t.url, active: t.active }))
    );

    const tab = testTabs.find((t) => t.active) || testTabs[0];
    if (!tab || tab.id === undefined) {
      console.warn("[Bridge] no matching test-page tab found — action dropped");
      return;
    }
    console.info("[Bridge] target tab", tab.id, tab.url);

    let result;
    try {
      result = await sendAction(tab.id, {
        type: "EXECUTE_ACTION_PLAN",
        action_plan: envelope.action_plan,
      });
    } catch (sendErr) {
      console.error(
        "[Bridge] sendMessage FAILED — listener not present in tab",
        tab.id,
        sendErr && sendErr.message
      );
      return;
    }

    console.info("[Bridge] ActionResult received", envelope.request_id, result && result.action_results);
    await postResult(envelope.request_id, result.action_results || []);
    console.info("[Bridge] /action-result posted", envelope.request_id);

  } catch (error) {
    console.warn("[Bridge] poll failed", error && error.message ? error.message : error);
  } finally {
    pollInFlight = false;
  }
}

function ensurePollingAlarm() {
  chrome.alarms.create(POLL_ALARM, { periodInMinutes: POLL_PERIOD_MINUTES });
  pollOnce();
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === POLL_ALARM) pollOnce();
});
chrome.runtime.onInstalled.addListener(ensurePollingAlarm);
chrome.runtime.onStartup.addListener(ensurePollingAlarm);
ensurePollingAlarm();
