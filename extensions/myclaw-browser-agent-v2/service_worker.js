/* eslint-disable no-console */
const WS_URL = "ws://127.0.0.1:8000/ws/browser-gateway";
const RETRY_MS = 3000;

let socket = null;
let connected = false;
let reconnectTimer = null;
let heartbeatTimer = null;
let attachedTabId = null;
let attachedFrameId = null;

const CONTENT_CHANNEL = "myclaw-native-v2";

function log(...args) {
  console.log("[myclaw-native-v2]", ...args);
}

function send(msg) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify(msg));
}

function scheduleReconnect(reason, delay = RETRY_MS) {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    ensureConnected(`retry:${reason || "unknown"}`);
  }, delay);
}

function unsupported(action) {
  return {
    ok: false,
    error_code: "unsupported_action",
    message: `unsupported action in content script: ${action}`,
  };
}

async function getAttachedOrActiveTab() {
  let tab = null;
  if (attachedTabId) {
    try {
      tab = await chrome.tabs.get(attachedTabId);
    } catch (_err) {
      tab = null;
    }
  }
  if (!tab || !tab.id) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    tab = tabs && tabs.length ? tabs[0] : null;
    if (tab && tab.id) attachedTabId = tab.id;
  }
  return tab;
}

async function listFrameIds(tabId) {
  try {
    const frames = await chrome.webNavigation.getAllFrames({ tabId });
    return (frames || []).map((f) => f.frameId).filter((x) => typeof x === "number");
  } catch (_err) {
    return [0];
  }
}

async function sendToFrame(tabId, frameId, action, payload) {
  try {
    const response = await chrome.tabs.sendMessage(
      tabId,
      { channel: CONTENT_CHANNEL, action, payload: payload || {} },
      typeof frameId === "number" ? { frameId } : undefined,
    );
    if (!response) {
      return { ok: false, error_code: "no_response", message: "no response from content script", frameId };
    }
    return { ...(response || {}), frameId };
  } catch (err) {
    return { ok: false, error_code: "frame_send_failed", message: String(err), frameId };
  }
}

function scoreFrameResult(action, r) {
  if (!r || !r.ok) return -1;
  if (action === "snapshot") {
    const snap = r.snapshot || {};
    return Number(snap.elements_count || 0) * 1000 + String(snap.text || "").length;
  }
  const changed = r.changed ? 100 : 0;
  return changed + 1;
}

async function sendAtomicToBestFrame(tabId, action, payload) {
  const frameIds = await listFrameIds(tabId);
  const order = [];
  if (typeof attachedFrameId === "number") order.push(attachedFrameId);
  if (!order.includes(0)) order.push(0);
  for (const fid of frameIds) if (!order.includes(fid)) order.push(fid);

  let best = null;
  let lastErr = null;
  for (const frameId of order) {
    const r = await sendToFrame(tabId, frameId, action, payload);
    if (!r.ok) {
      lastErr = r;
      continue;
    }
    const score = scoreFrameResult(action, r);
    if (!best || score > best.score) best = { score, result: r };
  }
  if (best && best.result) {
    attachedFrameId = best.result.frameId;
    const out = { ...best.result };
    out.meta = { ...(out.meta || {}), frame_id: attachedFrameId, candidate_frames: order.length };
    return out;
  }
  return lastErr || { ok: false, error_code: "no_frame_result", message: "no frame returned usable result" };
}

async function sendToActiveTab(action, payload) {
  const tab = await getAttachedOrActiveTab();
  if (!tab || !tab.id) {
    return { ok: false, error_code: "no_tab", message: "no active/attached tab" };
  }

  if (action === "navigate") {
    const url = String((payload && payload.url) || "").trim();
    if (!url) return { ok: false, error_code: "bad_input", message: "missing url" };
    await chrome.tabs.update(tab.id, { url });
    return { ok: true, changed: true, message: "navigated", after: { url } };
  }
  if (action === "get_url") {
    return { ok: true, changed: false, url: String(tab.url || "") };
  }
  if (action === "go_back") {
    await chrome.tabs.goBack(tab.id);
    return { ok: true, changed: true, message: "went back" };
  }
  if (action === "reload_tab") {
    await chrome.tabs.reload(tab.id);
    return { ok: true, changed: true, message: "tab reloaded" };
  }
  if (action === "go_forward") {
    await chrome.tabs.goForward(tab.id);
    return { ok: true, changed: true, message: "went forward" };
  }
  if (action === "wait") {
    const ms = Math.max(0, Number((payload && payload.ms) || 0));
    await new Promise((resolve) => setTimeout(resolve, ms));
    return { ok: true, changed: false, message: `waited ${ms}ms` };
  }

  if (action === "click_trusted") {
    const rectRes = await sendAtomicToBestFrame(tab.id, "get_element_rect", payload || {});
    if (!rectRes || !rectRes.ok || typeof rectRes.x !== "number" || typeof rectRes.y !== "number") {
      return rectRes || { ok: false, error_code: "rect_failed", message: "get_element_rect failed" };
    }
    const { x, y } = rectRes;
    const target = { tabId: tab.id };
    try {
      await new Promise((resolve, reject) => {
        chrome.debugger.attach(target, "1.3", () => (chrome.runtime.lastError ? reject(chrome.runtime.lastError) : resolve()));
      });
      await new Promise((resolve, reject) => {
        chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", { type: "mouseMoved", x, y }, (err) => (err ? reject(err) : resolve()));
      });
      await new Promise((resolve, reject) => {
        chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", { type: "mousePressed", button: "left", x, y, clickCount: 1 }, (err) => (err ? reject(err) : resolve()));
      });
      await new Promise((resolve, reject) => {
        chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", { type: "mouseReleased", button: "left", x, y, clickCount: 1 }, (err) => (err ? reject(err) : resolve()));
      });
      return { ok: true, changed: true, message: "trusted click", x, y };
    } catch (err) {
      return { ok: false, error_code: "debugger_failed", message: String(err), x, y };
    } finally {
      try {
        await chrome.debugger.detach(target);
      } catch (_e) {}
    }
  }

  const atomicActions = new Set([
    "snapshot",
    "locate",
    "click",
    "type",
    "hover",
    "press_key",
    "select_option",
    "get_dropdown_options",
    "scroll_into_view",
    "wait_for",
    "assert",
    "download_from_link",
    "get_element_rect",
    "reload_page",
  ]);
  if (!atomicActions.has(action)) {
    return unsupported(action);
  }
  const frameResult = await sendAtomicToBestFrame(tab.id, action, payload || {});
  if (action === "download_from_link" && frameResult && frameResult.ok && frameResult.href) {
    try {
      const downloadId = await chrome.downloads.download({
        url: frameResult.href,
        saveAs: false,
      });
      return { ...frameResult, download_id: downloadId, message: "download started" };
    } catch (err) {
      return { ok: false, error_code: "download_api_failed", message: String(err), href: frameResult.href };
    }
  }
  return frameResult;
}

function handleIncoming(raw) {
  let msg = null;
  try {
    msg = JSON.parse(raw.data);
  } catch (_err) {
    return;
  }
  if (!msg || msg.type !== "command") return;
  const id = msg.id || "";
  const action = String(msg.action || "");

  send({ type: "ack", id, timestamp: new Date().toISOString() });
  sendToActiveTab(action, msg.payload || {})
    .then((payload) => {
      if (!payload || payload.ok === false) {
        send({
          type: "error",
          id,
          code: "execution_failed",
          message: (payload && payload.message) || "execution failed",
          payload: payload || { ok: false, message: "execution failed" },
          timestamp: new Date().toISOString(),
        });
      } else {
        send({
          type: "result",
          id,
          payload,
          timestamp: new Date().toISOString(),
        });
      }
    })
    .catch((err) => {
      send({
        type: "error",
        id,
        code: "execution_failed",
        message: String(err),
        timestamp: new Date().toISOString(),
      });
    });
}

function startHeartbeat() {
  if (heartbeatTimer) return;
  heartbeatTimer = setInterval(async () => {
    if (!connected) return;
    const tab = await getAttachedOrActiveTab();
    send({
      type: "heartbeat",
      timestamp: new Date().toISOString(),
      meta: {
        extension_version: chrome.runtime.getManifest().version,
        attached_tab_id: tab && tab.id ? String(tab.id) : "",
        active_url: tab && tab.url ? String(tab.url) : "",
        mode: "atomic_v2",
      },
    });
  }, 5000);
}

function connect(reason = "boot") {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
  log("connecting websocket", { reason, ws: WS_URL });
  socket = new WebSocket(WS_URL);
  socket.onopen = () => {
    connected = true;
    send({
      type: "hello",
      client_id: `ext-v2-${chrome.runtime.id}`,
      timestamp: new Date().toISOString(),
      meta: {
        extension_id: chrome.runtime.id,
        version: chrome.runtime.getManifest().version,
        mode: "atomic_v2",
      },
    });
  };
  socket.onmessage = handleIncoming;
  socket.onerror = () => {
    connected = false;
  };
  socket.onclose = () => {
    connected = false;
    scheduleReconnect("onclose");
  };
}

function ensureConnected(reason = "manual") {
  if (socket && socket.readyState === WebSocket.OPEN) return;
  connect(reason);
}

chrome.runtime.onInstalled.addListener(() => ensureConnected("onInstalled"));
chrome.runtime.onStartup.addListener(() => ensureConnected("onStartup"));
chrome.tabs.onActivated.addListener(({ tabId }) => {
  attachedTabId = tabId;
  ensureConnected("tabs.onActivated");
});
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab && tab.active) {
    attachedTabId = tabId;
    ensureConnected("tabs.onUpdated");
  }
});
chrome.action.onClicked.addListener((tab) => {
  if (tab && tab.id) attachedTabId = tab.id;
  ensureConnected("action.onClicked");
});

log("service worker loaded");
ensureConnected("initial");
startHeartbeat();
