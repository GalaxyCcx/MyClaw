/* eslint-disable no-console */
const WS_URL = "ws://127.0.0.1:8000/ws/browser-gateway";
const RETRY_MS = 3000;
const CONTENT_CHANNEL = "myclaw-vision-v3";

let socket = null;
let connected = false;
let reconnectTimer = null;
let heartbeatTimer = null;
let attachedTabId = null;
const TAB_STATE = new Map(); // tabId -> { marks, frameId }

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
}

function log(...args) {
  console.log("[myclaw-vision-v3]", ...args);
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
    const ids = (frames || []).map((f) => f.frameId).filter((x) => typeof x === "number");
    if (!ids.includes(0)) ids.unshift(0);
    return ids;
  } catch (_err) {
    return [0];
  }
}

async function sendToFrame(tabId, frameId, action, payload) {
  try {
    const response = await chrome.tabs.sendMessage(
      tabId,
      { channel: CONTENT_CHANNEL, action, payload: payload || {} },
      { frameId },
    );
    if (!response) return { ok: false, error_code: "no_response", message: "no response from content script", frameId };
    return { ...(response || {}), frameId };
  } catch (err) {
    return { ok: false, error_code: "frame_send_failed", message: String(err), frameId };
  }
}

async function ensureContentScriptInjected(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: ["content_script.js"],
    });
  } catch (_err) {
    // ignore; content script may already be present or host may block some frames
  }
}

async function sendToPreferredFrame(tabId, action, payload, preferredFrameId = null) {
  let lastErr = null;
  for (let round = 0; round < 3; round += 1) {
    const frameIds = await listFrameIds(tabId);
    const order = [];
    if (typeof preferredFrameId === "number") order.push(preferredFrameId);
    if (!order.includes(0)) order.push(0);
    for (const fid of frameIds) if (!order.includes(fid)) order.push(fid);

    for (const frameId of order) {
      const r = await sendToFrame(tabId, frameId, action, payload || {});
      if (r && r.ok) return r;
      lastErr = r;
    }

    const msg = String((lastErr && lastErr.message) || "").toLowerCase();
    const recoverable =
      (lastErr && lastErr.error_code === "frame_send_failed") &&
      (msg.includes("receiving end does not exist") || msg.includes("could not establish connection"));
    if (!recoverable) break;
    await ensureContentScriptInjected(tabId);
    await sleep(300 + round * 250);
  }
  return lastErr || { ok: false, error_code: "no_frame_result", message: "no frame returned usable result" };
}

function findMark(marks, label) {
  const want = String(label || "").trim().toLowerCase();
  if (!want) return null;
  return (marks || []).find((m) => String(m.label || "").trim().toLowerCase() === want) || null;
}

function getTabState(tabId) {
  return TAB_STATE.get(tabId) || { marks: [], frameId: 0 };
}

function setTabState(tabId, state) {
  TAB_STATE.set(tabId, { ...getTabState(tabId), ...(state || {}) });
}

async function sendToActiveTab(action, payload) {
  const tab = await getAttachedOrActiveTab();
  if (!tab || !tab.id) return { ok: false, error_code: "no_tab", message: "no active/attached tab" };

  if (action === "navigate") {
    const url = String((payload && payload.url) || "").trim();
    if (!url) return { ok: false, error_code: "bad_input", message: "missing url" };
    await chrome.tabs.update(tab.id, { url });
    return { ok: true, changed: true, after: { url } };
  }
  if (action === "go_back") {
    await chrome.tabs.goBack(tab.id);
    return { ok: true, changed: true };
  }
  if (action === "go_forward") {
    await chrome.tabs.goForward(tab.id);
    return { ok: true, changed: true };
  }
  if (action === "wait") {
    const ms = Math.max(0, Number((payload && payload.ms) || 0));
    await new Promise((resolve) => setTimeout(resolve, ms));
    return { ok: true, changed: false, message: `waited ${ms}ms` };
  }
  if (action === "get_url") {
    return { ok: true, changed: false, url: String(tab.url || "") };
  }
  if (action === "screenshot") {
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    return { ok: true, changed: false, data_url: dataUrl };
  }

  if (action === "vision_capture_marked") {
    const waitStable = Boolean(payload && payload.wait_stable);
    if (waitStable) {
      const state = getTabState(tab.id);
      await sendToPreferredFrame(
        tab.id,
        "vision_wait_stable",
        {
          timeout_ms: Number((payload && payload.stable_timeout_ms) || 3000),
          interval_ms: Number((payload && payload.stable_interval_ms) || 250),
          settle_rounds: Number((payload && payload.stable_rounds) || 2),
          min_wait_ms: Number((payload && payload.stable_min_wait_ms) || 0),
        },
        state.frameId,
      );
    }
    const frameIds = await listFrameIds(tab.id);
    const prevFrame = getTabState(tab.id).frameId;
    const order = [];
    if (typeof prevFrame === "number") order.push(prevFrame);
    if (!order.includes(0)) order.push(0);
    for (const fid of frameIds) if (!order.includes(fid)) order.push(fid);

    let best = null;
    let lastErr = null;
    for (const frameId of order) {
      const r = await sendToFrame(tab.id, frameId, "vision_mark", payload || {});
      if (!r || !r.ok) {
        lastErr = r;
        continue;
      }
      const marks = Array.isArray(r.marks) ? r.marks : [];
      const qualityScore = Number(r.quality_score || (r.stats && r.stats.quality_score) || 0);
      const semanticCount = Number((r.stats && r.stats.semantic_count) || 0);
      const meaningfulCount = Number((r.stats && r.stats.meaningful_count) || 0);
      const score =
        qualityScore * 100000 +
        semanticCount * 2000 +
        meaningfulCount * 200 +
        marks.length * 10 +
        Number((r.page && r.page.viewport && r.page.viewport.height) || 0);
      if (!best || score > best.score) best = { score, result: r, frameId, marks };
    }
    if (!best || !best.result) {
      return lastErr || { ok: false, error_code: "mark_failed", message: "vision_mark failed in all frames" };
    }

    // Give overlay one paint cycle before screenshot, otherwise markers may be missing in capture.
    await sendToFrame(
      tab.id,
      best.frameId,
      "vision_wait_stable",
      {
        timeout_ms: Number((payload && payload.mark_render_timeout_ms) || 800),
        interval_ms: Number((payload && payload.mark_render_interval_ms) || 120),
        settle_rounds: 1,
        min_wait_ms: Number((payload && payload.mark_render_min_wait_ms) || 180),
      },
    );

    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    await sendToFrame(tab.id, best.frameId, "vision_clear_marks", {});
    setTabState(tab.id, { marks: best.marks, frameId: best.frameId });
    return {
      ok: true,
      changed: true,
      data_url: dataUrl,
      marks: best.marks,
      page: best.result.page || { url: String(tab.url || "") },
      meta: { frame_id: best.frameId, candidate_frames: order.length },
    };
  }

  if (action === "vision_clear_marks") {
    const frameIds = await listFrameIds(tab.id);
    for (const frameId of frameIds) {
      await sendToFrame(tab.id, frameId, "vision_clear_marks", {});
    }
    TAB_STATE.delete(tab.id);
    return { ok: true, changed: true };
  }

  if (action === "vision_scroll_by") {
    const dy = Math.floor(Number((payload && payload.dy) || 0));
    const prevFrame = getTabState(tab.id).frameId;
    const frameIds = await listFrameIds(tab.id);
    const order = [];
    if (typeof prevFrame === "number") order.push(prevFrame);
    if (!order.includes(0)) order.push(0);
    for (const fid of frameIds) if (!order.includes(fid)) order.push(fid);

    let best = null;
    let lastErr = null;
    for (const frameId of order) {
      const r = await sendToFrame(tab.id, frameId, "vision_scroll_by", { dy });
      if (!r || !r.ok) {
        lastErr = r;
        continue;
      }
      const delta = Math.abs(Number(r.after_scroll_y || 0) - Number(r.before_scroll_y || 0));
      const capacity = Math.max(0, Number(r.doc_height || 0) - Number(r.viewport_height || 0));
      const score = delta * 100000 + capacity;
      if (!best || score > best.score) best = { score, result: r, frameId };
    }
    if (!best || !best.result) return lastErr || { ok: false, error_code: "scroll_failed", message: "vision_scroll_by failed" };
    setTabState(tab.id, { frameId: best.frameId });
    const out = { ...best.result };
    out.meta = { ...(out.meta || {}), frame_id: best.frameId, candidate_frames: order.length };
    return out;
  }

  if (action === "vision_wait_stable") {
    const state = getTabState(tab.id);
    const waited = await sendToPreferredFrame(tab.id, "vision_wait_stable", payload || {}, state.frameId);
    if (!waited || !waited.ok) return waited || { ok: false, error_code: "wait_stable_failed", message: "vision_wait_stable failed" };
    setTabState(tab.id, { frameId: waited.frameId });
    return { ...waited, meta: { ...(waited.meta || {}), frame_id: waited.frameId } };
  }

  if (action === "vision_click_label") {
    const state = getTabState(tab.id);
    const marks = state.marks || [];
    const label = String((payload && payload.label) || "");
    const mark = findMark(marks, label);
    if (!mark) return { ok: false, error_code: "label_not_found", message: `label not found: ${label}` };
    const x = Math.floor(Number(mark.x || 0) + Number(mark.width || 0) / 2);
    const y = Math.floor(Number(mark.y || 0) + Number(mark.height || 0) / 2);
    const clicked = await sendToPreferredFrame(tab.id, "vision_click_point", { x, y }, state.frameId);
    if (!clicked || !clicked.ok) return clicked || { ok: false, error_code: "click_failed", message: "vision_click_point failed" };
    setTabState(tab.id, { frameId: clicked.frameId });
    return { ok: true, changed: true, label, point: { x, y }, meta: { frame_id: clicked.frameId } };
  }

  if (action === "vision_type_label") {
    const state = getTabState(tab.id);
    const marks = state.marks || [];
    const label = String((payload && payload.label) || "");
    const text = String((payload && payload.text) || "");
    const clear = payload ? payload.clear !== false : true;
    const mark = findMark(marks, label);
    if (!mark) return { ok: false, error_code: "label_not_found", message: `label not found: ${label}` };
    const x = Math.floor(Number(mark.x || 0) + Number(mark.width || 0) / 2);
    const y = Math.floor(Number(mark.y || 0) + Number(mark.height || 0) / 2);
    const typed = await sendToPreferredFrame(tab.id, "vision_type_point", { x, y, text, clear }, state.frameId);
    if (!typed || !typed.ok) return typed || { ok: false, error_code: "type_failed", message: "vision_type_point failed" };
    setTabState(tab.id, { frameId: typed.frameId });
    return { ok: true, changed: true, label, point: { x, y }, meta: { frame_id: typed.frameId } };
  }

  return { ok: false, error_code: "unsupported_action", message: `unsupported action: ${action}` };
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
          payload: payload || { ok: false },
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
        mode: "vision_v3",
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
      client_id: `ext-v3-${chrome.runtime.id}`,
      timestamp: new Date().toISOString(),
      meta: {
        extension_id: chrome.runtime.id,
        version: chrome.runtime.getManifest().version,
        mode: "vision_v3",
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

