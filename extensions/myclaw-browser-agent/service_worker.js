/* eslint-disable no-console */
const WS_URL = "ws://127.0.0.1:8000/ws/browser-gateway";
const RETRY_MS = 3000;
let socket = null;
let connected = false;
let attachedTabId = null;
let attachedFrameId = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let lastSingleTriggerKey = "";
let lastSingleTriggerAt = 0;

function log(...args) {
  console.log("[myclaw-native-ext]", ...args);
}

function send(msg) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify(msg));
}

function scheduleReconnect(reason, delay = RETRY_MS) {
  if (reconnectTimer) return;
  log(`schedule reconnect in ${delay}ms`, reason || "");
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    ensureConnected(`retry:${reason || "unknown"}`);
  }, delay);
}

async function sendToActiveTab(action, payload) {
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
    if (tab && tab.id) {
      attachedTabId = tab.id;
    }
  }
  if (!tab || !tab.id) {
    return { ok: false, message: "no active/attached tab" };
  }

  if (action === "navigate") {
    if (!payload || !payload.url) return { ok: false, message: "missing url" };
    await chrome.tabs.update(tab.id, { url: payload.url });
    return { ok: true, message: "navigated" };
  }

  if (action === "go_back") {
    await chrome.tabs.goBack(tab.id);
    return { ok: true, message: "went back" };
  }

  if (action === "go_forward") {
    await chrome.tabs.goForward(tab.id);
    return { ok: true, message: "went forward" };
  }

  if (action === "wait") {
    const ms = Math.max(0, Number(payload && payload.ms ? payload.ms : 0));
    await new Promise((resolve) => setTimeout(resolve, ms));
    return { ok: true, message: `waited ${ms}ms` };
  }

  if (action === "screenshot") {
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    return { ok: true, data_url: dataUrl };
  }

  if (action === "download_status") {
    const keyword = payload && payload.keyword ? String(payload.keyword) : "";
    const items = await chrome.downloads.search({ limit: 5, orderBy: ["-startTime"] });
    const filtered = keyword
      ? items.filter((x) => (x.filename || "").includes(keyword))
      : items;
    return {
      ok: true,
      items: filtered.map((x) => ({
        id: x.id,
        state: x.state,
        filename: x.filename,
        exists: x.exists,
      })),
    };
  }

  if (action === "run_plan") {
    const steps = Array.isArray(payload && payload.steps) ? payload.steps : [];
    const stopOnError = payload && payload.stop_on_error !== false;
    const results = [];
    for (let i = 0; i < steps.length; i += 1) {
      const step = steps[i] || {};
      const stepAction = String(step.action || "");
      const stepPayload = (step.payload && typeof step.payload === "object") ? step.payload : {};
      if (!stepAction || stepAction === "run_plan") {
        const err = { ok: false, message: `invalid step action at index=${i}` };
        results.push({ index: i, action: stepAction, ok: false, result: err });
        if (stopOnError) {
          return { ok: false, message: err.message, steps: results };
        }
        continue;
      }
      try {
        const stepResult = await sendToActiveTab(stepAction, stepPayload);
        const ok = !(stepResult && stepResult.ok === false);
        results.push({ index: i, action: stepAction, ok, result: stepResult });
        if (!ok && stopOnError) {
          return {
            ok: false,
            message: `plan failed at step ${i}: ${stepAction}`,
            steps: results,
          };
        }
      } catch (err) {
        const errorResult = { ok: false, message: String(err) };
        results.push({ index: i, action: stepAction, ok: false, result: errorResult });
        if (stopOnError) {
          return {
            ok: false,
            message: `plan exception at step ${i}: ${stepAction}`,
            steps: results,
          };
        }
      }
    }
    return { ok: true, message: `plan executed (${results.length} steps)`, steps: results };
  }

  if (action === "alpha_bi_set_date_ranges") {
    const currentStart = String((payload && payload.current_start) || "");
    const currentEnd = String((payload && payload.current_end) || "");
    const compareStart = String((payload && payload.compare_start) || "");
    const compareEnd = String((payload && payload.compare_end) || "");
    if (!currentStart || !currentEnd || !compareStart || !compareEnd) {
      return { ok: false, message: "missing date params" };
    }

    const execResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      func: async (cs, ce, ds, de) => {
        const isVisible = (el) => {
          if (!el) return false;
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
        };
        const sleep = (ms) => new Promise((r) => setTimeout(r, Math.max(0, Number(ms || 0))));
        const parseYmd = (v) => {
          const m = String(v || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
          if (!m) return null;
          return { ym: Number(m[1]) * 12 + Number(m[2]) };
        };
        const monthDiff = (from, to) => {
          const a = parseYmd(from);
          const b = parseYmd(to);
          if (!a || !b) return 0;
          return Math.max(0, a.ym - b.ym);
        };
        const click = (el) => {
          if (!el) return false;
          el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
          el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
          el.click();
          return true;
        };
        const dateCell = (date) => {
          const day = String(Number(String(date).slice(-2)));
          const selectors = [`[title='${date}']`, `.ant-picker-cell[title='${date}']`, `[data-date='${date}']`];
          for (const s of selectors) {
            const el = document.querySelector(s);
            if (el && isVisible(el)) return el;
          }
          // Fallback: match visible day cells by text and pick in-view/non-disabled candidates.
          const dayNodes = Array.from(
            document.querySelectorAll(".ant-picker-cell-inner, .ant-calendar-date, td[role='gridcell'], .ant-picker-content td"),
          );
          const candidates = dayNodes
            .map((n) => (n && n.closest ? n.closest("td, .ant-picker-cell, .ant-calendar-cell, [role='gridcell']") || n : n))
            .filter((n) => {
              if (!n || !isVisible(n)) return false;
              const txt = String(n.innerText || n.textContent || "").replace(/\s+/g, "");
              if (txt !== day) return false;
              const cls = String(n.className || "");
              if (cls.includes("disabled") || cls.includes("ant-picker-cell-disabled")) return false;
              return true;
            });
          if (candidates.length) return candidates[0];
          return null;
        };
        const shiftMonthTo = async (baselineDate, targetDate) => {
          const n = monthDiff(baselineDate, targetDate);
          for (let i = 0; i < Math.min(n, 24); i += 1) {
            const prevBtn = document.querySelector(".ant-picker-header-prev-btn, .ant-calendar-prev-month-btn");
            if (!prevBtn || !isVisible(prevBtn)) break;
            click(prevBtn);
            await sleep(100);
          }
        };
        const pickRange = async (startInput, startDate, endDate, baseline) => {
          if (!startInput) return { ok: false, message: "start input missing" };
          click(startInput);
          await sleep(180);
          await shiftMonthTo(baseline, startDate);
          const start = dateCell(startDate);
          if (!start) return { ok: false, message: `start cell not found: ${startDate}` };
          click(start);
          await sleep(120);
          const end = dateCell(endDate);
          if (!end) return { ok: false, message: `end cell not found: ${endDate}` };
          click(end);
          await sleep(260);
          return { ok: true };
        };

        const inputs = Array.from(document.querySelectorAll("input")).filter(
          (el) => isVisible(el) && /^\d{4}-\d{2}-\d{2}$/.test(String(el.value || "")),
        );
        if (inputs.length < 4) {
          return { ok: false, message: "date inputs < 4", frame_url: location.href, found: inputs.length };
        }

        const pairs = [];
        for (let i = 0; i < inputs.length - 1; i += 1) {
          const a = inputs[i];
          const b = inputs[i + 1];
          const ra = a.getBoundingClientRect();
          const rb = b.getBoundingClientRect();
          const sameRow = Math.abs(ra.top - rb.top) < 28;
          const close = Math.abs(ra.left - rb.left) < 320;
          if (sameRow && close) {
            pairs.push([a, b]);
            i += 1;
          }
        }
        if (pairs.length < 2) {
          pairs.length = 0;
          pairs.push([inputs[0], inputs[1]]);
          pairs.push([inputs[2], inputs[3]]);
        }

        const currentPair = pairs[0];
        const comparePair = pairs[1];
        const targetInputs = [currentPair[0], currentPair[1], comparePair[0], comparePair[1]];
        const before = targetInputs.map((el) => String(el.value || ""));

        const r1 = await pickRange(targetInputs[0], cs, ce, before[0]);
        if (!r1.ok) return { ...r1, before, frame_url: location.href, found: inputs.length };
        const r2 = await pickRange(targetInputs[2], ds, de, before[2]);
        if (!r2.ok) return { ...r2, before, frame_url: location.href, found: inputs.length };

        const after = targetInputs.map((el) => String(el.value || ""));
        const expected = [cs, ce, ds, de];
        const ok = expected.every((v, i) => after[i] === v);
        if (!ok) {
          // Fallback: write exact values then re-validate current visible values.
          for (let i = 0; i < targetInputs.length; i += 1) {
            const el = targetInputs[i];
            const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
            if (setter) setter.call(el, expected[i]);
            else el.value = expected[i];
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "Enter" }));
            el.dispatchEvent(new Event("blur", { bubbles: true }));
          }
          await sleep(240);
          const after2 = targetInputs.map((el) => String(el.value || ""));
          const ok2 = expected.every((v, i) => after2[i] === v);
          return {
            ok: ok2,
            message: ok2 ? "alpha-bi date ranges set (input-fallback)" : "date value mismatch after pick",
            before,
            after: after2,
            expected,
            frame_url: location.href,
            found: inputs.length,
          };
        }
        return {
          ok,
          message: ok ? "alpha-bi date ranges set" : "date value mismatch after pick",
          before,
          after,
          expected,
          frame_url: location.href,
          found: inputs.length,
        };
      },
      args: [currentStart, currentEnd, compareStart, compareEnd],
    });

    let best = null;
    for (const item of execResults || []) {
      const r = item && item.result ? item.result : {};
      const score = (r.ok ? 100000 : 0) + Number(r.found || 0) * 10;
      if (!best || score > best.score) {
        best = { score, frameId: item.frameId, result: r };
      }
    }
    if (!best || !best.result) {
      return { ok: false, message: "no frame execution result" };
    }
    attachedFrameId = best.frameId;
    return { ...best.result, meta: { frame_id: best.frameId, frames: (execResults || []).length } };
  }

  if (action === "alpha_bi_goto_task_center") {
    const execResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      func: async () => {
        const normalize = (v) =>
          String(v || "")
            .replace(/[\s\-—–_·|【】\[\]\(\)（）&＋+✔✅:：,，。\.]/g, "")
            .toLowerCase();
        const textOf = (el) => String(el?.innerText || el?.textContent || "").replace(/\s+/g, " ").trim();
        const isVisible = (el) => {
          if (!el) return false;
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
        };
        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
        const beforeUrl = String(location.href || "");
        const beforeTitle = String(document.title || "");
        const isInTaskCenterView = () => {
          const currentUrl = String(location.href || "");
          const currentTitle = String(document.title || "");
          const hint = normalize(`${currentTitle} ${currentUrl}`);
          const keywordHit = (
            hint.includes(normalize("任务中心")) ||
            hint.includes(normalize("下载中心")) ||
            hint.includes(normalize("离线下载")) ||
            hint.includes(normalize("下载任务")) ||
            hint.includes("downloadcenter") ||
            hint.includes("downloadtask")
          );
          const changed =
            normalize(currentUrl) !== normalize(beforeUrl) ||
            normalize(currentTitle) !== normalize(beforeTitle);
          // 必须“特征命中 + 可见状态变化”，避免仅因页面文案里包含“任务中心”而误判。
          return keywordHit && changed;
        };
        const openHref = (rawHref) => {
          const href = String(rawHref || "").trim();
          if (!href) return false;
          try {
            const target = href.startsWith("http") ? href : new URL(href, location.href).toString();
            window.location.assign(target);
            return true;
          } catch (_err) {
            return false;
          }
        };
        const findGotoCandidates = () => {
          const labels = [
            "任务中心",
            "前往任务中心",
            "下载中心",
            "前往下载中心",
            "去下载中心",
            "查看下载",
            "跳转下载",
            "下载列表",
            "查看任务",
            "download center",
            "view download",
          ].map((x) => normalize(x));
          const nodes = Array.from(
            document.querySelectorAll("button, a, [role='button'], [role='menuitem'], [data-href], [data-url], .ant-btn, .ant-notification-notice"),
          );
          return nodes
            .filter((el) => isVisible(el))
            .map((el) => {
              const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
              const href = String(el.getAttribute?.("href") || el.getAttribute?.("data-href") || el.getAttribute?.("data-url") || "").trim();
              const sig = normalize(`${t} ${href} ${el.className || ""}`);
              const labelHit = labels.some((lb) => sig.includes(lb));
              const hrefHit =
                sig.includes("task") ||
                sig.includes("download") ||
                sig.includes("center") ||
                sig.includes("%E4%BB%BB%E5%8A%A1") ||
                sig.includes("%E4%B8%8B%E8%BD%BD");
              return { el, t, href, score: (labelHit ? 100 : 0) + (hrefHit ? 60 : 0) };
            })
            .filter((x) => x.score > 0)
            .sort((a, b) => b.score - a.score);
        };

        let gotoMethod = "";
        for (let i = 0; i < 8; i += 1) {
          const cands = findGotoCandidates();
          for (const c of cands.slice(0, 8)) {
            try {
              c.el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
              if (typeof c.el.click === "function") c.el.click();
              else c.el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
              gotoMethod = "click";
            } catch (_err) {
              // ignore and try href
            }
            for (let k = 0; k < 6; k += 1) {
              await sleep(220);
              if (isInTaskCenterView()) {
                return {
                  ok: true,
                  goto_center_clicked: true,
                  before_url: beforeUrl,
                  after_url: String(location.href || ""),
                  goto_method: gotoMethod || "click",
                  debug: { candidates: cands.length },
                };
              }
            }
            if (openHref(c.href)) {
              gotoMethod = "href_assign";
              for (let k = 0; k < 8; k += 1) {
                await sleep(240);
                if (isInTaskCenterView()) {
                  return {
                    ok: true,
                    goto_center_clicked: true,
                    before_url: beforeUrl,
                    after_url: String(location.href || ""),
                    goto_method: gotoMethod,
                    debug: { candidates: cands.length },
                  };
                }
              }
            }
          }
          await sleep(220);
        }
        return {
          ok: false,
          goto_center_clicked: false,
          before_url: beforeUrl,
          after_url: String(location.href || ""),
          goto_method: gotoMethod || "none",
          debug: { candidates: findGotoCandidates().length },
        };
      },
      args: [],
    });

    let best = null;
    for (const item of execResults || []) {
      const r = item && item.result ? item.result : {};
      const score = (r.goto_center_clicked ? 1000 : 0) + Number(((r.debug || {}).candidates) || 0);
      if (!best || score > best.score) {
        best = { score, frameId: item.frameId, result: r };
      }
    }
    if (!best || !best.result) {
      return { ok: false, message: "goto task center no frame result" };
    }
    attachedFrameId = best.frameId;
    return { ...best.result, meta: { frame_id: best.frameId, frames: (execResults || []).length } };
  }

  if (action === "alpha_bi_download_table") {
    const tableKeyword = String((payload && payload.table_keyword) || "").trim();
    const fileKeyword = String((payload && payload.file_keyword) || "").trim();
    const singleTriggerOnly = Boolean(payload && payload.single_trigger_only);
    const timeoutMs = Math.max(5000, Number((payload && payload.timeout_ms) || 120000));
    const pollMs = Math.max(300, Number((payload && payload.poll_interval_ms) || 1200));
    const gotoCenterAfterTrigger = Boolean(payload && payload.goto_center_after_trigger);
    const allowAnyDownloadType = Boolean(payload && payload.allow_any_download_type);
    if (!tableKeyword) {
      return { ok: false, message: "missing table_keyword" };
    }
    if (singleTriggerOnly) {
      const now = Date.now();
      const key = `${tab.id}:${tableKeyword}`;
      if (lastSingleTriggerKey === key && now - lastSingleTriggerAt < 30000) {
        return {
          ok: false,
          message: "single trigger suppressed (dedupe window)",
          failure_reason: "dedupe_suppressed",
          trigger_count: 0,
          menu_target: "raw_only",
          table_keyword: tableKeyword,
          file_keyword: fileKeyword,
        };
      }
      lastSingleTriggerKey = key;
      lastSingleTriggerAt = now;
    }

    const startedAt = Date.now();
    let exportTriggered = false;
    const uiTry = async () => {
      const execResults = await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        func: async (kw, fk, suppressExportStep, singleOnly, allowAnyTypeInMenu, gotoCenterAfterTriggerInPlan) => {
          try {
          const normalize = (v) =>
            String(v || "")
              .replace(/[\s\-—–_·|【】\[\]\(\)（）&＋+✔✅:：,，。\.]/g, "")
              .toLowerCase();
          const tokenize = (v) =>
            String(v || "")
              .split(/[\s\-—–_·|【】\[\]\(\)（）&＋+✔✅:：,，。\.]+/g)
              .map((x) => normalize(x))
              .filter((x) => x && x.length >= 2);
          const isVisible = (el) => {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
          };
          const isActionVisible = (el) => {
            if (!el) return false;
            if (isVisible(el)) return true;
            const style = window.getComputedStyle(el);
            if (style.display === "none" || style.visibility === "hidden") return false;
            const childSvg = el.querySelector?.("svg");
            return Boolean(childSvg && isVisible(childSvg));
          };
          const textOf = (el) => String(el?.innerText || el?.textContent || "").replace(/\s+/g, " ").trim();
          const visibleAll = Array.from(document.querySelectorAll("*")).filter((el) => isVisible(el));
          const want = normalize(kw);
          const wantTokens = tokenize(kw);
          const fileWant = normalize(fk || "");
          const fileTokens = tokenize(fk || "");
          const textScore = (textNorm, tokens) => {
            if (!textNorm) return 0;
            if (want && textNorm.includes(want)) return 1000;
            let hit = 0;
            for (const tk of tokens || []) {
              if (textNorm.includes(tk)) hit += 1;
            }
            return hit * 100;
          };
          const hitCount = (textNorm, tokens) => {
            if (!textNorm) return 0;
            let n = 0;
            for (const tk of tokens || []) {
              if (textNorm.includes(tk)) n += 1;
            }
            return n;
          };
          const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
          const click = (el) => {
            if (!el) return false;
            try {
              el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
              // 最小化交互副作用：只执行一次原生 click。
              if (typeof el.click === "function") el.click();
              else el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
              return true;
            } catch (_err) {
              return false;
            }
          };
          const clickDownloadTriggerOnce = (el, options = {}) => {
            const force = Boolean(options && options.force);
            if (!el) return false;
            try {
              const target =
                el.closest?.(".ant-dropdown-trigger, .table__action, [role='button'], button, a") ||
                el.querySelector?.(".ant-dropdown-trigger, .table__action, [role='button'], button, a") ||
                el;
              const signal = normalize(
                `${textOf(target)} ${target.getAttribute?.("aria-label") || ""} ${target.getAttribute?.("title") || ""} ${target.className || ""}`,
              );
              const clsNorm = normalize(String(target.className || ""));
              const isSetting =
                signal.includes(normalize("列设置")) ||
                signal.includes(normalize("设置")) ||
                signal.includes("columnsetting") ||
                signal.includes("columnsettings") ||
                signal.includes("setting");
              const isDownload =
                signal.includes(normalize("下载")) ||
                signal.includes(normalize("导出")) ||
                signal.includes("download") ||
                signal.includes("export") ||
                signal.includes("anticondownload");
              const hasStrictDownloadHint =
                clsNorm.includes("anticondownload") ||
                clsNorm.includes("icondownload") ||
                String(target.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                String(target.getAttribute?.("aria-label") || "").toLowerCase().includes("download");
              // 终点保护：宁可不点，也不要误点“列设置”。
              if (isSetting || (!force && !isDownload && !hasStrictDownloadHint)) return false;
              target.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
              // 严格单击：避免多事件连发导致一次请求触发多次下载。
              if (typeof target.click === "function") target.click();
              else target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
              return true;
            } catch (_err) {
              return false;
            }
          };
          const hover = (el) => {
            if (!el) return false;
            try {
              el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
              el.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
              el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
              el.dispatchEvent(new MouseEvent("mousemove", { bubbles: true }));
              return true;
            } catch (_err) {
              return false;
            }
          };
          const hoverTopRight = (el) => {
            if (!el) return false;
            try {
              const r = el.getBoundingClientRect();
              const x = Math.max(1, Math.floor(r.right - 10));
              const y = Math.max(1, Math.floor(r.top + 10));
              const tgt = document.elementFromPoint(x, y) || el;
              const ev = { bubbles: true, clientX: x, clientY: y };
              tgt.dispatchEvent(new MouseEvent("mouseenter", ev));
              tgt.dispatchEvent(new MouseEvent("mouseover", ev));
              tgt.dispatchEvent(new MouseEvent("mousemove", ev));
              return true;
            } catch (_err) {
              return false;
            }
          };
          const findButtonIn = (root, labels) => {
            if (!root) return null;
            const all = [root, ...Array.from(root.querySelectorAll("*"))];
            const wanted = (labels || []).map((x) => normalize(x));
            for (const el of all) {
              if (!isVisible(el)) continue;
              const disabled = el.disabled || el.getAttribute?.("aria-disabled") === "true";
              if (disabled) continue;
              const tag = String(el.tagName || "").toLowerCase();
              const role = String(el.getAttribute?.("role") || "");
              const cls = String(el.className || "");
              if (!(tag === "button" || tag === "a" || role === "button" || role === "menuitem")) continue;
              const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || "");
              if (!t) continue;
              if (wanted.some((w) => t.includes(w))) return el;
              // 兼容非标准按钮（例如仅样式类 + 文本）
              if (cls.includes("btn") && wanted.some((w) => t.includes(w))) return el;
            }
            return null;
          };
          const findLooseTextAction = (root, labels) => {
            if (!root) return null;
            const all = Array.from(root.querySelectorAll("*"));
            const wanted = (labels || []).map((x) => normalize(x));
            for (const el of all) {
              if (!isVisible(el)) continue;
              const disabled = el.getAttribute?.("aria-disabled") === "true";
              if (disabled) continue;
              const t = normalize(textOf(el) || "");
              if (!t) continue;
              if (!wanted.some((w) => t.includes(w))) continue;
              const clickable = el.closest("button, a, [role='button'], [role='menuitem']");
              if (clickable && isVisible(clickable)) return clickable;
              return el;
            }
            return null;
          };
          const tryClickGotoCenter = async () => {
            const labels = [
              "任务中心",
              "前往任务中心",
              "下载中心",
              "前往下载中心",
              "去下载中心",
              "查看下载",
              "跳转下载",
              "下载列表",
              "查看任务",
              "download center",
              "view download",
            ];
            const extractGotoHref = (el) => {
              if (!el) return "";
              const a = el.closest?.("a[href]") || (el.matches?.("a[href]") ? el : null);
              const href = String(
                a?.getAttribute?.("href") ||
                el.getAttribute?.("href") ||
                el.getAttribute?.("data-href") ||
                el.getAttribute?.("data-url") ||
                "",
              ).trim();
              if (!href) return "";
              const h = href.toLowerCase();
              if (
                h.includes("task") ||
                h.includes("download") ||
                h.includes("%E4%BB%BB%E5%8A%A1") ||
                h.includes("%E4%B8%8B%E8%BD%BD")
              ) return href;
              return "";
            };
            const tryOpenHref = (href) => {
              if (!href) return false;
              try {
                const target = href.startsWith("http")
                  ? href
                  : new URL(href, location.href).toString();
                window.location.assign(target);
                return true;
              } catch (_err) {
                return false;
              }
            };
            const findGlobalTaskCenterHref = () => {
              const nodes = Array.from(document.querySelectorAll("*"));
              for (const el of nodes) {
                if (!isVisible(el)) continue;
                const raw = String(
                  el.getAttribute?.("href") ||
                  el.getAttribute?.("data-href") ||
                  el.getAttribute?.("data-url") ||
                  "",
                ).trim();
                const txt = normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
                const h = raw.toLowerCase();
                if (
                  txt.includes(normalize("任务中心")) ||
                  txt.includes(normalize("下载中心")) ||
                  h.includes("task") ||
                  h.includes("download") ||
                  h.includes("center") ||
                  h.includes("%E4%BB%BB%E5%8A%A1") ||
                  h.includes("%E4%B8%8B%E8%BD%BD")
                ) {
                  if (raw) return raw;
                  const clickable =
                    el.closest?.("a[href], [data-href], [data-url], button, [role='button'], [onclick], span, div") || el;
                  const fallback = String(
                    clickable.getAttribute?.("href") ||
                    clickable.getAttribute?.("data-href") ||
                    clickable.getAttribute?.("data-url") ||
                    "",
                  ).trim();
                  if (fallback) return fallback;
                }
              }
              return "";
            };
            for (let i = 0; i < 8; i += 1) {
              const btn =
                findButtonIn(document.body, labels) ||
                findLooseTextAction(document.body, labels);
              if (btn && click(btn)) return true;
              if (btn) {
                const href = extractGotoHref(btn);
                if (tryOpenHref(href)) return true;
              }
              const globalHref = findGlobalTaskCenterHref();
              if (tryOpenHref(globalHref)) return true;
              await sleep(220);
            }
            return false;
          };
          const tryClickTaskCenterFromSuccessNotice = async () => {
            const containerSelectors = [
              ".ant-notification-notice",
              ".ant-message-notice",
              ".ant-alert",
              ".ant-modal-content",
              ".ant-drawer-content",
              ".ant-popover-inner-content",
              ".ant-tooltip-inner",
            ];
            const noticeTexts = ["离线下载任务创建成功", "任务创建成功", "下载任务创建成功"];
            const targetTexts = ["前往任务中心", "任务中心", "下载中心"];
            for (let i = 0; i < 12; i += 1) {
              const containers = [];
              for (const sel of containerSelectors) {
                for (const el of Array.from(document.querySelectorAll(sel))) {
                  if (isVisible(el)) containers.push(el);
                }
              }
              // 兜底：全局扫描可能承载通知文本的节点
              if (!containers.length) {
                for (const el of Array.from(document.querySelectorAll("div,section,article"))) {
                  if (isVisible(el)) containers.push(el);
                }
              }
              let clicked = false;
              for (const box of containers) {
                const boxText = normalize(textOf(box) || "");
                const isSuccessNotice = noticeTexts.some((t) => boxText.includes(normalize(t)));
                if (!isSuccessNotice) continue;
                const candidates = Array.from(
                  box.querySelectorAll("button, a, [role='button'], .ant-btn, .ant-btn-primary"),
                )
                  .filter((el) => isVisible(el))
                  .map((el) => ({
                    el,
                    t: normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || ""),
                    cls: String(el.className || "").toLowerCase(),
                  }))
                  .filter((x) => x.t);
                candidates.sort((a, b) => {
                  const score = (x) => {
                    let s = 0;
                    if (targetTexts.some((t) => x.t.includes(normalize(t)))) s += 1000;
                    if (x.cls.includes("ant-btn-primary")) s += 200;
                    if (x.cls.includes("primary")) s += 100;
                    return s;
                  };
                  return score(b) - score(a);
                });
                if (candidates.length && targetTexts.some((t) => candidates[0].t.includes(normalize(t)))) {
                  if (click(candidates[0].el)) {
                    clicked = true;
                    break;
                  }
                  const href =
                    String(candidates[0].el.getAttribute?.("href") || candidates[0].el.getAttribute?.("data-href") || "").trim();
                  if (href) {
                    try {
                      const target = href.startsWith("http") ? href : new URL(href, location.href).toString();
                      window.location.assign(target);
                      clicked = true;
                      break;
                    } catch (_err) {
                      // ignore and continue probing
                    }
                  }
                }
              }
              if (clicked) return true;
              await sleep(180);
            }
            return false;
          };
          const tryClickTaskCenterPopupPrimary = async () => {
            const normalizeBtnText = (el) =>
              normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
            const candidates = () =>
              Array.from(
                document.querySelectorAll("button, a, [role='button'], .ant-btn, .ant-btn-primary, .ant-modal button"),
              ).filter((el) => isVisible(el));
            const scoreBtn = (el) => {
              const t = normalizeBtnText(el);
              if (!t) return -1;
              let score = 0;
              if (t.includes(normalize("前往任务中心"))) score += 1000;
              if (t.includes(normalize("任务中心"))) score += 600;
              if (t.includes(normalize("下载中心"))) score += 300;
              const cls = String(el.className || "").toLowerCase();
              if (cls.includes("ant-btn-primary")) score += 200;
              if (cls.includes("primary")) score += 100;
              return score;
            };
            for (let i = 0; i < 12; i += 1) {
              const list = candidates()
                .map((el) => ({ el, s: scoreBtn(el) }))
                .filter((x) => x.s > 0)
                .sort((a, b) => b.s - a.s);
              if (list.length && click(list[0].el)) return true;
              if (list.length) {
                const href =
                  String(list[0].el.getAttribute?.("href") || list[0].el.getAttribute?.("data-href") || "").trim();
                if (href) {
                  try {
                    const target = href.startsWith("http") ? href : new URL(href, location.href).toString();
                    window.location.assign(target);
                    return true;
                  } catch (_err) {
                    // ignore and continue probing
                  }
                }
              }
              await sleep(180);
            }
            return false;
          };
          const isInTaskCenterView = () => {
            const hint = normalize(`${document.title || ""} ${location.href || ""} ${textOf(document.body || document.documentElement) || ""}`);
            return (
              hint.includes(normalize("任务中心")) ||
              hint.includes(normalize("下载中心")) ||
              hint.includes(normalize("离线下载")) ||
              hint.includes(normalize("下载任务")) ||
              hint.includes("downloadcenter") ||
              hint.includes("downloadtask")
            );
          };
          const clickGotoCenterWithVerify = async () => {
            const verifyAfterClick = async () => {
              // 给页面路由/弹窗切换留一点时间，再做可见态校验。
              for (let i = 0; i < 6; i += 1) {
                await sleep(220);
                if (isInTaskCenterView()) return true;
              }
              return false;
            };
            if (await tryClickTaskCenterFromSuccessNotice()) {
              if (await verifyAfterClick()) return true;
            }
            if (await tryClickGotoCenter()) {
              if (await verifyAfterClick()) return true;
            }
            if (await tryClickTaskCenterPopupPrimary()) {
              if (await verifyAfterClick()) return true;
            }
            return false;
          };
          const findMenuActionItem = (root) => {
            if (!root) return null;
            const all = Array.from(root.querySelectorAll("*"));
            const labels = ["原始数据", "raw"];
            const wanted = labels.map((x) => normalize(x));
            const strictItems = Array.from(root.querySelectorAll(".custom_download-type-item, .ant-dropdown-menu-item.custom_download-type-item"));
            for (const item of strictItems) {
              if (!isVisible(item)) continue;
              const t = normalize(textOf(item) || item.getAttribute?.("aria-label") || "");
              if (t && wanted.some((w) => t.includes(w))) return item;
            }
            for (const el of all) {
              if (!isVisible(el)) continue;
              const cls = String(el.className || "");
              const role = String(el.getAttribute?.("role") || "");
              const tag = String(el.tagName || "").toLowerCase();
              const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || "");
              const looksMenu =
                role === "menuitem" ||
                cls.includes("menu-item") ||
                cls.includes("dropdown") ||
                cls.includes("popover");
              if (!looksMenu && tag !== "li" && tag !== "button" && tag !== "a" && !t) continue;
              if (t && wanted.some((w) => t.includes(w))) return el;
            }
            return null;
          };
          const tryClickDownloadTypeMenu = async (allowAnyType = false) => {
            for (let i = 0; i < 14; i += 1) {
              const strictList = Array.from(
                document.querySelectorAll(".custom_download-type-item, .ant-dropdown-menu-item.custom_download-type-item"),
              ).filter((el) => isVisible(el));
              const strictRaw = strictList.find((el) => {
                const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || "");
                return t.includes(normalize("原始数据")) || t.includes("raw");
              });
              if (strictRaw && click(strictRaw)) return true;
              if (allowAnyType && strictList.length && click(strictList[0])) return true;
              const menuItem = findMenuActionItem(document.body);
              if (menuItem && click(menuItem)) return true;
              if (allowAnyType) {
                const anyMenu = Array.from(document.querySelectorAll("[role='menuitem'], .ant-dropdown-menu-item, .custom_download-type-item"))
                  .find((el) => isVisible(el));
                if (anyMenu && click(anyMenu)) return true;
              }
              await sleep(180);
            }
            return false;
          };
          const tryClickAnyDownloadType = async () => {
            for (let i = 0; i < 12; i += 1) {
              const anyMenu = Array.from(
                document.querySelectorAll(
                  ".custom_download-type-item, .ant-dropdown-menu-item, [role='menuitem'], .ant-dropdown-menu-title-content, li",
                ),
              ).filter((el) => isVisible(el));
              const candidate = anyMenu.find((el) => {
                const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || "");
                if (!t) return false;
                // 排除明显非下载类型项
                if (t.includes(normalize("列设置")) || t.includes("setting")) return false;
                return t.includes(normalize("数据")) || t.includes(normalize("下载")) || t.includes("raw") || t.includes("format");
              });
              if (candidate && click(candidate)) return true;
              await sleep(160);
            }
            return false;
          };
          const forceOpenDownloadMenuNearScope = async (scope) => {
            if (!scope) return false;
            for (let i = 0; i < 5; i += 1) {
              const trigger =
                scope.querySelector?.("[aria-label='download'].ant-dropdown-trigger") ||
                scope.querySelector?.(".anticon-download.ant-dropdown-trigger") ||
                scope.querySelector?.(".table__action.ant-dropdown-trigger") ||
                findNearestScopedDownloadTrigger(scope) ||
                findNearestGlobalDownloadTrigger(scope);
              if (!trigger) {
                await sleep(120);
                continue;
              }
              hover(scope);
              hoverTopRight(scope);
              await sleep(120);
              if (clickDownloadTriggerOnce(trigger)) {
                await sleep(180);
                const opened =
                  Array.from(document.querySelectorAll(".ant-dropdown, .ant-dropdown-menu, .custom_download-type-item, [role='menuitem']"))
                    .some((el) => isVisible(el));
                if (opened) return true;
              }
              await sleep(120);
            }
            return false;
          };
          const tryClickRawButtonInScope = async (scope) => {
            if (!scope) return false;
            const pickButtons = (root) =>
              Array.from(root.querySelectorAll("button, a, span, div, li, [role='button'], [role='menuitem']"))
                .filter((el) => isVisible(el))
                .map((el) => ({
                  el,
                  t: normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || ""),
                  cls: String(el.className || "").toLowerCase(),
                }));
            for (let i = 0; i < 12; i += 1) {
              const list = pickButtons(scope);
              const raw = list.find((x) => x.t.includes(normalize("原始数据")) || x.t.includes("raw"));
              if (raw && click(raw.el)) return true;
              // 兜底：有些页面按钮文案是“原始”“数据下载”等，放宽匹配。
              const looseRaw = list.find((x) =>
                (x.t.includes(normalize("原始")) && x.t.includes(normalize("数据"))) ||
                (x.t.includes("raw") && x.t.includes("data")) ||
                x.cls.includes("download-type-item"),
              );
              if (looseRaw && click(looseRaw.el)) return true;
              await sleep(140);
            }
            return false;
          };
          const tryClickRawNearAnchor = async (anchor) => {
            if (!anchor || !anchor.getBoundingClientRect) return false;
            const ar = anchor.getBoundingClientRect();
            const ax = ar.right - Math.max(16, Math.floor(ar.width * 0.2));
            const ay = ar.top + Math.max(12, Math.floor(ar.height * 0.15));
            for (let i = 0; i < 10; i += 1) {
              const all = Array.from(document.querySelectorAll("button, a, span, div, li, [role='button'], [role='menuitem']"))
                .filter((el) => isVisible(el))
                .map((el) => {
                  const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
                  if (!(t.includes(normalize("原始数据")) || t.includes("raw"))) return null;
                  const r = el.getBoundingClientRect();
                  const ex = r.left + r.width / 2;
                  const ey = r.top + r.height / 2;
                  const d = Math.hypot(ex - ax, ey - ay);
                  return { el, d, r };
                })
                .filter(Boolean)
                .sort((a, b) => a.d - b.d);
              if (all.length && click(all[0].el)) return true;
              await sleep(140);
            }
            return false;
          };
          const findIconDownloadButtonIn = (root) => {
            if (!root) return null;
            const iconSelectors = [
              "[aria-label*='下载']",
              "[aria-label*='download']",
              "[title*='下载']",
              "[title*='download']",
              "[data-icon='download']",
              ".anticon-download",
              ".icon-download",
              ".download-icon",
            ];
            for (const sel of iconSelectors) {
              const nodes = Array.from(root.querySelectorAll(sel));
              for (const node of nodes) {
                if (!isActionVisible(node)) continue;
                const btn = node.closest("button, a, [role='button'], [role='menuitem']");
                if (btn && isActionVisible(btn)) {
                  const sig = normalize(
                    `${textOf(btn)} ${btn.getAttribute?.("aria-label") || ""} ${btn.getAttribute?.("title") || ""} ${btn.className || ""}`,
                  );
                  const clsNorm = normalize(String(btn.className || ""));
                  if (sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting")) continue;
                  if (
                    sig.includes(normalize("下载")) ||
                    sig.includes(normalize("导出")) ||
                    sig.includes("download") ||
                    sig.includes("export") ||
                    sig.includes("anticondownload") ||
                    clsNorm.includes("anticondownload") ||
                    clsNorm.includes("icondownload") ||
                    String(btn.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                    String(btn.getAttribute?.("aria-label") || "").toLowerCase().includes("download")
                  ) return btn;
                }
                // AntD 下载入口常见为 span.ant-dropdown-trigger，直接可点。
                if (node instanceof Element && isActionVisible(node)) {
                  const sig = normalize(
                    `${textOf(node)} ${node.getAttribute?.("aria-label") || ""} ${node.getAttribute?.("title") || ""} ${node.className || ""}`,
                  );
                  const clsNorm = normalize(String(node.className || ""));
                  if (sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting")) continue;
                  if (
                    sig.includes(normalize("下载")) ||
                    sig.includes(normalize("导出")) ||
                    sig.includes("download") ||
                    sig.includes("export") ||
                    sig.includes("anticondownload") ||
                    clsNorm.includes("anticondownload") ||
                    clsNorm.includes("icondownload") ||
                    String(node.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                    String(node.getAttribute?.("aria-label") || "").toLowerCase().includes("download")
                  ) return node;
                }
              }
            }
            return null;
          };
          const findNearestGlobalDownloadTrigger = (anchor) => {
            const nodes = Array.from(document.querySelectorAll(".anticon-download.ant-dropdown-trigger, [aria-label='download'].ant-dropdown-trigger"));
            const av = anchor?.getBoundingClientRect?.();
            if (!av) return null;
            const ax = av.left + av.width / 2;
            const ay = av.top + av.height / 2;
            let best = null;
            for (const el of nodes) {
              if (!isActionVisible(el)) continue;
              const r = el.getBoundingClientRect();
              const ex = r.left + r.width / 2;
              const ey = r.top + r.height / 2;
              const d = Math.hypot(ex - ax, ey - ay);
              if (!best || d < best.d) best = { el, d };
            }
            return best ? best.el : null;
          };
          const findDirectDownloadTrigger = (anchor) => {
            const nodes = Array.from(
              document.querySelectorAll(
                "[aria-label='download'].ant-dropdown-trigger, .anticon-download.ant-dropdown-trigger, .table__action.ant-dropdown-trigger",
              ),
            ).filter((el) => isActionVisible(el));
            if (!nodes.length) return null;
            if (!anchor || !anchor.getBoundingClientRect) return nodes[0];
            const ar = anchor.getBoundingClientRect();
            const ax = ar.left + ar.width / 2;
            const ay = ar.top + ar.height / 2;
            let best = null;
            for (const el of nodes) {
              const sig = normalize(
                `${textOf(el)} ${el.getAttribute?.("aria-label") || ""} ${el.getAttribute?.("title") || ""} ${el.className || ""}`,
              );
              if (sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting")) continue;
              const r = el.getBoundingClientRect();
              const d = Math.hypot((r.left + r.width / 2) - ax, (r.top + r.height / 2) - ay);
              if (!best || d < best.d) best = { el, d };
            }
            return best ? best.el : null;
          };
          const pickScopedPreferredTrigger = (scope, anchor) => {
            if (!scope) return null;
            const nodes = Array.from(
              scope.querySelectorAll(
                ".table__action.cursor-pointer.ant-dropdown-trigger, .table__action.ant-dropdown-trigger, .ant-dropdown-trigger[aria-label='download'], .anticon-download.ant-dropdown-trigger",
              ),
            ).filter((el) => isActionVisible(el));
            if (!nodes.length) return null;
            const ar = anchor?.getBoundingClientRect?.() || scope.getBoundingClientRect?.();
            const top = Number(ar?.top || 0);
            let best = null;
            for (const el of nodes) {
              const sig = normalize(
                `${textOf(el)} ${el.getAttribute?.("aria-label") || ""} ${el.getAttribute?.("title") || ""} ${el.className || ""}`,
              );
              if (sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting")) continue;
              const r = el.getBoundingClientRect();
              const rightScore = r.left / Math.max(1, window.innerWidth);
              const topPenalty = Math.abs((r.top + r.height / 2) - (top + 16));
              let score = rightScore * 100 - topPenalty;
              if (sig.includes("download") || sig.includes(normalize("下载")) || sig.includes("anticondownload")) score += 80;
              if (!best || score > best.score) best = { el, score };
            }
            return best ? best.el : null;
          };
          const pickBestRightSideTriggerForBlock = (anchor) => {
            if (!anchor || !anchor.getBoundingClientRect) return null;
            const ar = anchor.getBoundingClientRect();
            const targetY = ar.top + Math.min(28, Math.max(8, ar.height / 8));
            const nodes = Array.from(document.querySelectorAll(".ant-dropdown-trigger, .app-iconify.anticon, .table__action"));
            let best = null;
            for (const n of nodes) {
              if (!isActionVisible(n)) continue;
              const cls = String(n.className || "").toLowerCase();
              if (!(cls.includes("dropdown-trigger") || cls.includes("table__action") || cls.includes("anticon"))) continue;
              const sig = normalize(
                `${textOf(n)} ${n.getAttribute?.("aria-label") || ""} ${n.getAttribute?.("title") || ""} ${n.className || ""}`,
              );
              const clsNorm = normalize(String(n.className || ""));
              const isSetting = sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting");
              const isDownload =
                sig.includes(normalize("下载")) ||
                sig.includes(normalize("导出")) ||
                sig.includes("download") ||
                sig.includes("export") ||
                sig.includes("anticondownload");
              const hasStrictDownloadHint =
                clsNorm.includes("anticondownload") ||
                clsNorm.includes("icondownload") ||
                String(n.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                String(n.getAttribute?.("aria-label") || "").toLowerCase().includes("download");
              if (isSetting || (!isDownload && !hasStrictDownloadHint)) continue;
              const r = n.getBoundingClientRect();
              if (r.left < window.innerWidth * 0.55) continue;
              const y = r.top + r.height / 2;
              const dy = Math.abs(y - targetY);
              const xScore = r.left / Math.max(1, window.innerWidth);
              const score = -dy + xScore * 100;
              if (!best || score > best.score) best = { el: n, score };
            }
            return best ? best.el : null;
          };
          const probeRightRailDownloadTrigger = (anchor) => {
            if (!anchor || !anchor.getBoundingClientRect) return null;
            const ar = anchor.getBoundingClientRect();
            const probePoints = [
              { x: window.innerWidth - 22, y: Math.max(8, Math.floor(ar.top + 18)) },
              { x: window.innerWidth - 22, y: Math.max(8, Math.floor(ar.top + ar.height / 2)) },
              { x: window.innerWidth - 36, y: Math.max(8, Math.floor(ar.top + ar.height / 2)) },
            ];
            for (const p of probePoints) {
              const el = document.elementFromPoint(p.x, p.y);
              if (!el) continue;
              const clickable = el.closest?.("button, a, [role='button'], [role='menuitem'], span, div") || el;
              if (!clickable || !isVisible(clickable)) continue;
              const sig = normalize(
                `${textOf(clickable)} ${clickable.getAttribute?.("aria-label") || ""} ${clickable.getAttribute?.("title") || ""} ${clickable.className || ""}`,
              );
              const clsNorm = normalize(String(clickable.className || ""));
              const isSetting = sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting");
              const isDownload =
                sig.includes(normalize("下载")) ||
                sig.includes(normalize("导出")) ||
                sig.includes("download") ||
                sig.includes("export") ||
                sig.includes("anticondownload");
              const hasStrictDownloadHint =
                clsNorm.includes("anticondownload") ||
                clsNorm.includes("icondownload") ||
                String(clickable.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                String(clickable.getAttribute?.("aria-label") || "").toLowerCase().includes("download");
              if (!isSetting && (isDownload || hasStrictDownloadHint)) {
                return clickable;
              }
            }
            return null;
          };
          const findRightRailDownloadTextButton = (anchor) => {
            const all = Array.from(document.querySelectorAll("button, a, span, div, li")).filter((el) => isVisible(el));
            const ar = anchor?.getBoundingClientRect?.();
            const ay = ar ? (ar.top + ar.height / 2) : (window.innerHeight / 2);
            let best = null;
            for (const el of all) {
              const txt = normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
              if (!(txt === normalize("下载") || txt.includes("download"))) continue;
              const r = el.getBoundingClientRect();
              if (r.left < window.innerWidth * 0.65) continue;
              if (r.width > 200 || r.height > 80) continue;
              const dy = Math.abs((r.top + r.height / 2) - ay);
              if (!best || dy < best.dy) best = { el, dy };
            }
            return best ? best.el : null;
          };
          const sweepRightEdgeDownloadTrigger = async (anchor) => {
            if (!anchor || !anchor.getBoundingClientRect) return null;
            const r = anchor.getBoundingClientRect();
            const y0 = Math.max(8, Math.floor(r.top + 10));
            const y1 = Math.max(y0, Math.floor(r.bottom - 10));
            const step = Math.max(14, Math.floor((y1 - y0) / 8));
            const x = Math.max(8, window.innerWidth - 24);
            const looksDownload = (el) => {
              if (!el) return false;
              const sig = normalize(
                `${textOf(el)} ${el.getAttribute?.("aria-label") || ""} ${el.getAttribute?.("title") || ""} ${el.className || ""}`,
              );
              return (
                sig.includes(normalize("下载")) ||
                sig.includes("download") ||
                sig.includes("anticondownload")
              );
            };
            for (let y = y0; y <= y1; y += step) {
              const el = document.elementFromPoint(x, y);
              if (!el) continue;
              const tgt = el.closest?.("button, a, [role='button'], [role='menuitem'], span, div") || el;
              if (!tgt || !isActionVisible(tgt)) continue;
              // 先做一次 hover 激活可能的悬浮工具栏，再判定
              tgt.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true, clientX: x, clientY: y }));
              tgt.dispatchEvent(new MouseEvent("mouseover", { bubbles: true, clientX: x, clientY: y }));
              tgt.dispatchEvent(new MouseEvent("mousemove", { bubbles: true, clientX: x, clientY: y }));
              await sleep(40);
              if (looksDownload(tgt)) return tgt;
            }
            return null;
          };
          const findNearestScopedDownloadTrigger = (anchor) => {
            const scopes = [];
            if (anchor) {
              scopes.push(anchor);
              const a1 = anchor.closest?.(".ant-card, .ant-table-wrapper, .chart-container, section, div");
              if (a1 && !scopes.includes(a1)) scopes.push(a1);
              const a2 = a1?.parentElement;
              if (a2 && !scopes.includes(a2)) scopes.push(a2);
            }
            const selectors = [
              ".anticon-download.ant-dropdown-trigger",
              "[aria-label='download'].ant-dropdown-trigger",
              "[data-icon='download']",
              ".anticon-download",
            ];
            for (const scope of scopes) {
              const strict = Array.from(
                scope.querySelectorAll(".table__action.cursor-pointer.ant-dropdown-trigger, .table__action.ant-dropdown-trigger"),
              ).filter((el) => {
                if (!isActionVisible(el)) return false;
                const sig = normalize(
                  `${textOf(el)} ${el.getAttribute?.("aria-label") || ""} ${el.getAttribute?.("title") || ""} ${el.className || ""}`,
                );
                const clsNorm = normalize(String(el.className || ""));
                const isSetting = sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting");
                const isDownload =
                  sig.includes(normalize("下载")) ||
                  sig.includes(normalize("导出")) ||
                  sig.includes("download") ||
                  sig.includes("export") ||
                  sig.includes("anticondownload");
                const hasStrictDownloadHint =
                  clsNorm.includes("anticondownload") ||
                  clsNorm.includes("icondownload") ||
                  String(el.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                  String(el.getAttribute?.("aria-label") || "").toLowerCase().includes("download");
                return !isSetting && (isDownload || hasStrictDownloadHint);
              });
              if (strict.length) {
                return strict[0];
              }
              const nodes = [];
              for (const sel of selectors) {
                for (const el of Array.from(scope.querySelectorAll(sel))) {
                  if (!isActionVisible(el)) continue;
                  const sig = normalize(
                    `${textOf(el)} ${el.getAttribute?.("aria-label") || ""} ${el.getAttribute?.("title") || ""} ${el.className || ""}`,
                  );
                  const clsNorm = normalize(String(el.className || ""));
                  const isSetting = sig.includes(normalize("列设置")) || sig.includes("columnsetting") || sig.includes("setting");
                  const isDownload =
                    sig.includes(normalize("下载")) ||
                    sig.includes(normalize("导出")) ||
                    sig.includes("download") ||
                    sig.includes("export") ||
                    sig.includes("anticondownload");
                  const hasStrictDownloadHint =
                    clsNorm.includes("anticondownload") ||
                    clsNorm.includes("icondownload") ||
                    String(el.getAttribute?.("data-icon") || "").toLowerCase() === "download" ||
                    String(el.getAttribute?.("aria-label") || "").toLowerCase().includes("download");
                  if (!isSetting && (isDownload || hasStrictDownloadHint)) nodes.push(el);
                }
              }
              if (!nodes.length) continue;
              const ar = anchor.getBoundingClientRect();
              const ax = ar.left + ar.width / 2;
              const ay = ar.top + ar.height / 2;
              let best = null;
              for (const el of nodes) {
                const r = el.getBoundingClientRect();
                const ex = r.left + r.width / 2;
                const ey = r.top + r.height / 2;
                const d = Math.hypot(ex - ax, ey - ay);
                if (!best || d < best.d) best = { el, d };
              }
              if (best?.el) return best.el;
            }
            return null;
          };
          const countDownloadTriggersIn = (scope) => {
            if (!scope) return 0;
            const selectors = [
              ".anticon-download.ant-dropdown-trigger",
              "[aria-label='download'].ant-dropdown-trigger",
              "[data-icon='download']",
              ".anticon-download",
            ];
            let n = 0;
            for (const sel of selectors) {
              n += Array.from(scope.querySelectorAll(sel)).filter((el) => isActionVisible(el)).length;
            }
            return n;
          };
          const collectDownloadCandidates = (root, limit = 12) => {
            const out = [];
            if (!root) return out;
            const all = Array.from(root.querySelectorAll("*"));
            for (const el of all) {
              if (!isVisible(el)) continue;
              const t = normalize(textOf(el) || el.getAttribute?.("aria-label") || el.getAttribute?.("title") || "");
              const cls = String(el.className || "");
              const role = String(el.getAttribute?.("role") || "");
              const tag = String(el.tagName || "").toLowerCase();
              const hasDownloadSignal =
                (t && (t.includes("下载") || t.includes("导出") || t.includes("download") || t.includes("export"))) ||
                cls.includes("download") ||
                cls.includes("anticon-download") ||
                (cls.includes("dropdown-trigger") && cls.includes("anticon")) ||
                el.getAttribute?.("data-icon") === "download";
              if (!hasDownloadSignal) continue;
              out.push({
                tag,
                role,
                cls: cls.slice(0, 120),
                text: String(textOf(el) || "").slice(0, 80),
                aria: String(el.getAttribute?.("aria-label") || "").slice(0, 80),
                title: String(el.getAttribute?.("title") || "").slice(0, 80),
              });
              if (out.length >= limit) break;
            }
            return out;
          };

          let exportClicked = false;
          let menuClicked = false;
          let gotoCenterClicked = false;
          let finalDownloadClicked = false;
          let exportTriggerCount = 0;
          const noticeSeen = normalize(textOf(document.body) || "").includes(normalize("离线下载任务创建成功"));
          const debug = {
            matched_blocks: 0,
            url: String(location.href || ""),
            download_candidates: [],
            menu_candidates: [],
            menu_clicked: false,
            goto_candidates: [],
            notice_seen: noticeSeen,
          };
          debug.download_candidates = collectDownloadCandidates(document.body, 20);

          // 单次模式：仅走页面定制硬编码链路（目标表 -> 右侧下载触发器 -> 原始数据）
          if (singleOnly) {
            // 页面定制硬编码：优先精确命中目标表标题，避免模糊匹配漂移。
            const exactTargetNorm = normalize("✔ [过程拆解2]-补充订单&用户");
            const exactNodes = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,span,div,p"))
              .filter((el) => isVisible(el))
              .map((el) => {
                const tRaw = textOf(el) || "";
                const tNorm = normalize(tRaw);
                const exact = tNorm.includes(exactTargetNorm);
                return { el, tRaw, tNorm, exact };
              })
              .filter((x) => x.exact)
              .sort((a, b) => a.tRaw.length - b.tRaw.length);
            const minHits = Math.max(2, Math.ceil((wantTokens.length || 1) * 0.7));
            const titleNodes = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,span,div,p"))
              .filter((el) => isVisible(el))
              .map((el) => {
                const tRaw = textOf(el) || "";
                const tNorm = normalize(tRaw);
                const hits = hitCount(tNorm, wantTokens);
                const full = want ? tNorm.includes(want) : false;
                return { el, tRaw, tNorm, hits, full };
              })
              .filter((x) => x.full || x.hits >= minHits)
              .sort((a, b) => {
                if (Number(b.full) !== Number(a.full)) return Number(b.full) - Number(a.full);
                if (b.hits !== a.hits) return b.hits - a.hits;
                return a.tRaw.length - b.tRaw.length;
              });
            debug.matched_blocks = exactNodes.length || titleNodes.length;
            const head = exactNodes.length ? exactNodes[0] : (titleNodes.length ? titleNodes[0] : null);
            const targetBlock = head
              ? (head.el.closest?.(".ant-card, .ant-table-wrapper, .chart-container, section, div") || head.el.parentElement || head.el)
              : null;
            debug.target_block_text = String(textOf(targetBlock) || "").slice(0, 120);

            let menuClickedSingle = false;
            let triggerClickedSingle = false;
            let triggerScope = null;
            if (targetBlock) {
              // 单次模式：按“目标块 -> 父容器 -> 右侧轨道”逐层扩域，提升下载触发命中率。
              const scopeChain = [];
              let p = targetBlock;
              for (let i = 0; p && i < 5; i += 1) {
                if (!scopeChain.includes(p)) scopeChain.push(p);
                p = p.parentElement;
              }
              for (const scope of scopeChain) {
                // 单次锁：同一次 job 内只允许点一次下载触发器，后续仅尝试菜单项，不再重复触发下载。
                if (triggerClickedSingle) {
                  const menuScope = triggerScope || scope;
                  menuClickedSingle =
                    await tryClickRawButtonInScope(menuScope) ||
                    await tryClickRawNearAnchor(menuScope) ||
                    await tryClickRawButtonInScope(document.body) ||
                    await tryClickDownloadTypeMenu(allowAnyTypeInMenu) ||
                    (gotoCenterAfterTriggerInPlan ? await tryClickAnyDownloadType() : false);
                  if (menuClickedSingle) break;
                  await sleep(120);
                  continue;
                }
                hover(scope);
                hoverTopRight(scope);
                await sleep(220);
                click(scope);
                await sleep(120);
                let trigger =
                  pickScopedPreferredTrigger(scope, head?.el || targetBlock) ||
                  scope.querySelector?.(".table__action.cursor-pointer.ant-dropdown-trigger, .table__action.ant-dropdown-trigger") ||
                  scope.querySelector?.(".table__action [data-icon='download'], .table__action .anticon-download, .table__action .ant-dropdown-trigger") ||
                  findDirectDownloadTrigger(scope) ||
                  findNearestScopedDownloadTrigger(scope) ||
                  pickBestRightSideTriggerForBlock(scope) ||
                  findRightRailDownloadTextButton(scope) ||
                  probeRightRailDownloadTrigger(scope) ||
                  findNearestGlobalDownloadTrigger(scope);
                if (!trigger) {
                  trigger = await sweepRightEdgeDownloadTrigger(scope);
                }
                if (trigger && clickDownloadTriggerOnce(trigger, { force: true })) {
                  triggerClickedSingle = true;
                  triggerScope = scope;
                  exportTriggerCount = 1;
                  await sleep(140);
                  // 优先在目标区域内直接找“原始数据”按钮，其次再走全局下拉菜单探测。
                  menuClickedSingle =
                    await tryClickRawButtonInScope(scope) ||
                    await tryClickRawNearAnchor(scope) ||
                    await tryClickRawButtonInScope(document.body) ||
                    await tryClickDownloadTypeMenu(allowAnyTypeInMenu);
                  if (!menuClickedSingle && gotoCenterAfterTriggerInPlan) {
                    // “去任务中心”场景：不再重复触发下载，只尝试点击已出现的下载类型。
                    menuClickedSingle = (await tryClickDownloadTypeMenu(true)) || (await tryClickAnyDownloadType());
                  }
                  if (menuClickedSingle) break;
                }
              }
            }
            debug.menu_clicked = menuClickedSingle;
            exportClicked = menuClickedSingle;
            let gotoClickedSingle = false;
            if (gotoCenterAfterTriggerInPlan) {
              // 在“单次触发”基础上追加任务中心点击；即使菜单未命中也尝试已有入口，避免前置波动卡死。
              await sleep(260);
              gotoClickedSingle = await clickGotoCenterWithVerify();
            }
            let failureReason = "";
            if (!targetBlock) {
              failureReason = "target_not_found";
            } else if (!triggerClickedSingle) {
              failureReason = "trigger_not_found";
            } else if (!menuClickedSingle) {
              failureReason = "menu_not_found_raw";
            }
            return {
              ok: gotoCenterAfterTriggerInPlan ? gotoClickedSingle : exportClicked,
              export_clicked: exportClicked,
              goto_center_clicked: gotoClickedSingle,
              final_download_clicked: false,
              notice_seen: noticeSeen,
              trigger_count: exportTriggerCount,
              menu_target: "raw_only",
              failure_reason: exportClicked ? "" : failureReason,
              debug,
            };
          }

          // 1) 在目标表区块附近尝试点击 下载/导出（仅在未触发过创建任务时执行）。
          let matched = visibleAll
            .map((el) => {
              const t = normalize(textOf(el));
              return { el, score: textScore(t, wantTokens), hits: hitCount(t, wantTokens), t };
            })
            .filter((x) => {
              if (!singleOnly) return x.score >= 200;
              const minHits = Math.max(2, Math.ceil((wantTokens.length || 1) * 0.6));
              return x.hits >= minHits;
            })
            .sort((a, b) => {
              if (b.hits !== a.hits) return b.hits - a.hits;
              return b.score - a.score;
            });
          if (singleOnly) {
            matched = matched
              .map((m) => {
                const block = m.el.closest?.(".ant-card, .ant-table-wrapper, .chart-container, .block, section, div") || m.el.parentElement || m.el;
                const triggerCount = countDownloadTriggersIn(block);
                const bt = String(textOf(block) || "");
                const area = Math.max(1, Number(block.getBoundingClientRect?.().width || 1) * Number(block.getBoundingClientRect?.().height || 1));
                const blockScore = m.hits * 1000 + triggerCount * 500 - Math.floor(Math.log10(area));
                return { ...m, block, triggerCount, blockScore, blockText: bt };
              })
              .sort((a, b) => b.blockScore - a.blockScore);
          }
          debug.matched_blocks = matched.length;
          if (!suppressExportStep) {
            const candidates = singleOnly ? matched.slice(0, 1) : matched.slice(0, 12);
            for (const item of candidates) {
              const node = item.el;
              const block = item.block || node.closest?.(".ant-card, .ant-table-wrapper, .chart-container, .block, section, div") || node.parentElement || node;
              debug.target_block_text = String(textOf(block) || "").slice(0, 120);
              // 先悬浮区块，激活右上角的小图标入口。
              hover(block);
              hoverTopRight(block);
              await sleep(260);
              const iconBtn = singleOnly
                ? (
                    findNearestScopedDownloadTrigger(block) ||
                    pickBestRightSideTriggerForBlock(block) ||
                    findRightRailDownloadTextButton(block) ||
                    probeRightRailDownloadTrigger(block) ||
                    findNearestGlobalDownloadTrigger(block)
                  )
                : (findIconDownloadButtonIn(block) || findNearestGlobalDownloadTrigger(block));
              // 先点一下目标块，确保右侧工具栏作用于该块。
              if (singleOnly && exportTriggerCount === 0) {
                click(block);
                await sleep(120);
              }
              let finalBtn = iconBtn;
              if (singleOnly && !finalBtn) {
                finalBtn = await sweepRightEdgeDownloadTrigger(block);
              }
              if (finalBtn && (!singleOnly || exportTriggerCount === 0) && clickDownloadTriggerOnce(finalBtn)) {
                exportTriggerCount += 1;
                await sleep(120);
                menuClicked = await tryClickDownloadTypeMenu();
                const menuProbe = collectDownloadCandidates(document.body, 10).filter((x) => {
                  const tt = normalize(`${x.text} ${x.aria} ${x.title}`);
                  return tt.includes(normalize("格式化数据")) || tt.includes(normalize("原始数据"));
                });
                debug.menu_candidates = menuProbe;
                debug.menu_clicked = menuClicked;
                exportClicked = menuClicked;
                break;
              }
              const txtBtn = findButtonIn(block, ["下载", "导出", "export", "download"]);
              if (txtBtn && (!singleOnly || exportTriggerCount === 0) && click(txtBtn)) {
                exportTriggerCount += 1;
                await sleep(120);
                menuClicked = await tryClickDownloadTypeMenu();
                debug.menu_clicked = menuClicked;
                exportClicked = menuClicked;
                break;
              }
              const looseTxtBtn = findLooseTextAction(block, ["下载", "导出", "export", "download"]);
              if (looseTxtBtn && (!singleOnly || exportTriggerCount === 0) && click(looseTxtBtn)) {
                exportTriggerCount += 1;
                await sleep(120);
                menuClicked = await tryClickDownloadTypeMenu();
                debug.menu_clicked = menuClicked;
                exportClicked = menuClicked;
                break;
              }
            }
            if (!exportClicked && !singleOnly) {
              const fallbackBtn =
                findButtonIn(document.body, ["下载", "导出", "export", "download"]) ||
                findIconDownloadButtonIn(document.body) ||
                findLooseTextAction(document.body, ["下载", "导出", "export", "download"]);
              if (fallbackBtn && (!singleOnly || exportTriggerCount === 0) && click(fallbackBtn)) {
                exportTriggerCount += 1;
                menuClicked = await tryClickDownloadTypeMenu();
                debug.menu_clicked = menuClicked;
                exportClicked = menuClicked;
              }
            }
          }

          // 2) 处理“前往下载中心”类跳转按钮。
          const gotoProbe = collectDownloadCandidates(document.body, 20).filter((x) => {
            const tt = normalize(`${x.text} ${x.aria} ${x.title}`);
            return tt.includes(normalize("下载中心")) || tt.includes(normalize("查看下载")) || tt.includes(normalize("download center"));
          });
          debug.goto_candidates = gotoProbe;
          gotoCenterClicked = await clickGotoCenterWithVerify();

          // 3) 若已在下载中心（或同页下载列表），定位目标任务并点击最终下载按钮。
          const centerHint = normalize(document.title + " " + location.href);
          const inCenter = centerHint.includes("下载中心") || centerHint.includes("download");
          // 仅在“已确认进入任务中心”时才执行最终下载，避免主页面误点造成假阳性。
          const canRunFinalDownload = gotoCenterClicked || inCenter;
          const completeWords = ["已完成", "完成", "成功", "done", "complete"];
          const rows = visibleAll
            .map((el) => {
              const t = normalize(textOf(el));
              const primary = fileWant ? textScore(t, fileTokens) : textScore(t, wantTokens);
              return { el, score: primary, t };
            })
            .filter((x) => x.score >= 100)
            .sort((a, b) => b.score - a.score);
          for (const rowItem of rows.slice(0, 20)) {
            if (!canRunFinalDownload) break;
            const rowNode = rowItem.el;
            const row = rowNode.closest?.("tr, .ant-table-row, .list-item, .download-row, .record-item, .ant-list-item, div") || rowNode;
            const rowText = normalize(textOf(row));
            if (!inCenter && !rowText.includes("下载")) continue;
            const complete = completeWords.some((w) => rowText.includes(normalize(w)));
            if (!complete && inCenter) continue;
            const dlBtn = findButtonIn(row, ["下载", "download"]) || findLooseTextAction(row, ["下载", "download"]);
            if (dlBtn && click(dlBtn)) {
              finalDownloadClicked = true;
              break;
            }
          }

          // 兜底：下载中心中找首个可点击下载按钮。
          if (!finalDownloadClicked && canRunFinalDownload && inCenter) {
            const firstDl = findButtonIn(document.body, ["下载", "download"]);
            if (firstDl && click(firstDl)) {
              finalDownloadClicked = true;
            }
          }

          return {
            ok: exportClicked || gotoCenterClicked || finalDownloadClicked,
            export_clicked: exportClicked,
            goto_center_clicked: gotoCenterClicked,
            final_download_clicked: finalDownloadClicked,
            notice_seen: noticeSeen,
            debug,
          };
          } catch (err) {
            return {
              ok: false,
              export_clicked: false,
              goto_center_clicked: false,
              final_download_clicked: false,
              failure_reason: "script_exception",
              message: String(err),
              debug: {
                exception: String(err),
                url: String(location.href || ""),
              },
            };
          }
        },
        args: [tableKeyword, fileKeyword, exportTriggered, singleTriggerOnly, allowAnyDownloadType, gotoCenterAfterTrigger],
      });

      let best = null;
      for (const item of execResults || []) {
        const r = item && item.result ? item.result : {};
        const dc = Number((((r || {}).debug || {}).download_candidates || []).length || 0);
        const mc = Number((((r || {}).debug || {}).menu_candidates || []).length || 0);
        const score =
          (r.final_download_clicked ? 100000 : 0) +
          (r.goto_center_clicked ? 5000 : 0) +
          (r.export_clicked ? 500 : 0) +
          (singleTriggerOnly ? (dc * 120 + mc * 60) : 0) +
          Number((r.debug && r.debug.matched_blocks) || 0);
        if (!best || score > best.score) {
          best = { score, frameId: item.frameId, result: r };
        }
      }
      if (best) attachedFrameId = best.frameId;
      const out = best ? { ...(best.result || {}), meta: { frame_id: best.frameId, frames: (execResults || []).length } } : null;
      if (out && (out.export_clicked || out.notice_seen)) {
        exportTriggered = true;
      }
      return out;
    };

    let lastUi = null;
    let noMatchRounds = 0;
    while (Date.now() - startedAt < timeoutMs) {
      lastUi = await uiTry();
      if (singleTriggerOnly) {
        const ok = Boolean((lastUi || {}).export_clicked);
        return {
          ok,
          message: ok
            ? "single download trigger clicked"
            : "single download trigger failed",
          failure_reason: String((lastUi || {}).failure_reason || "trigger_not_found"),
          trigger_count: Number((lastUi || {}).trigger_count || 0),
          menu_target: String((lastUi || {}).menu_target || "raw_only"),
          table_keyword: tableKeyword,
          file_keyword: fileKeyword,
          ui: lastUi,
        };
      }
      const matchedBlocks = Number((((lastUi || {}).debug || {}).matched_blocks) || 0);
      const uiActed = Boolean((lastUi || {}).export_clicked || (lastUi || {}).goto_center_clicked || (lastUi || {}).final_download_clicked);
      if (!uiActed && matchedBlocks <= 0) {
        noMatchRounds += 1;
      } else {
        noMatchRounds = 0;
      }
      if (noMatchRounds >= 6) {
        return {
          ok: false,
          message: "target table not found (fast-fail)",
          table_keyword: tableKeyword,
          file_keyword: fileKeyword,
          ui: lastUi,
        };
      }

      // 检查下载队列，确认本地落盘。
      const items = await chrome.downloads.search({ limit: 20, orderBy: ["-startTime"] });
      const filtered = items.filter((x) => {
        const startMs = x.startTime ? Date.parse(x.startTime) : 0;
        const afterStart = startMs >= (startedAt - 2000);
        const name = String(x.filename || "");
        const keyOk = !fileKeyword || name.includes(fileKeyword);
        return afterStart && keyOk;
      });
      const latest = filtered.length ? filtered[0] : null;
      if (latest && latest.state === "complete" && latest.exists !== false) {
        return {
          ok: true,
          message: "download completed",
          table_keyword: tableKeyword,
          file_keyword: fileKeyword,
          download: {
            id: latest.id,
            state: latest.state,
            filename: latest.filename,
            exists: latest.exists,
          },
          ui: lastUi,
        };
      }

      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }

    const tailItems = await chrome.downloads.search({ limit: 10, orderBy: ["-startTime"] });
    return {
      ok: false,
      message: "download not completed within timeout",
      table_keyword: tableKeyword,
      file_keyword: fileKeyword,
      ui: lastUi,
      downloads: tailItems.map((x) => ({
        id: x.id,
        state: x.state,
        filename: x.filename,
        exists: x.exists,
      })),
    };
  }

  async function sendToFrame(frameId) {
    try {
      const response = await chrome.tabs.sendMessage(
        tab.id,
        {
          channel: "myclaw-native",
          action,
          payload: payload || {},
        },
        typeof frameId === "number" ? { frameId } : undefined,
      );
      if (!response) return { ok: false, message: "no response from content script" };
      if (!response.ok) return { ok: false, message: response.error || "unknown error" };
      return { ok: true, payload: response.payload || { ok: true }, frameId: frameId ?? 0 };
    } catch (err) {
      return { ok: false, message: String(err), frameId: frameId ?? 0 };
    }
  }

  async function listFrameIds() {
    try {
      const frames = await chrome.webNavigation.getAllFrames({ tabId: tab.id });
      return (frames || []).map((f) => f.frameId).filter((v) => typeof v === "number");
    } catch (_err) {
      return [0];
    }
  }

  if (action === "snapshot") {
    const frameIds = await listFrameIds();
    let best = null;
    for (const frameId of frameIds) {
      const r = await sendToFrame(frameId);
      if (!r.ok) continue;
      const snap = r.payload && r.payload.snapshot ? r.payload.snapshot : {};
      const elementsCount = Number(snap.elements_count || 0);
      const textLen = String(snap.text || "").length;
      const score = elementsCount * 1000 + textLen;
      if (!best || score > best.score) {
        best = { score, result: r, elementsCount, textLen };
      }
    }
    if (best && best.result) {
      attachedFrameId = best.result.frameId;
      const out = best.result.payload || { ok: true };
      if (out && typeof out === "object") {
        out.meta = { ...(out.meta || {}), frame_id: attachedFrameId };
      }
      return out;
    }
    return { ok: false, message: "no frame responded for snapshot" };
  }

  // For interaction actions, prefer previously attached frame.
  const preferredFrameIds = [];
  if (typeof attachedFrameId === "number") preferredFrameIds.push(attachedFrameId);
  if (!preferredFrameIds.includes(0)) preferredFrameIds.push(0);
  const allFrameIds = await listFrameIds();
  for (const fid of allFrameIds) {
    if (!preferredFrameIds.includes(fid)) preferredFrameIds.push(fid);
  }

  let lastError = null;
  for (const frameId of preferredFrameIds) {
    const r = await sendToFrame(frameId);
    if (!r.ok) {
      lastError = r;
      continue;
    }
    const out = r.payload || { ok: true };
    if (out && out.ok === false) {
      lastError = out;
      continue;
    }
    attachedFrameId = frameId;
    if (out && typeof out === "object") {
      out.meta = { ...(out.meta || {}), frame_id: frameId };
    }
    return out;
  }
  return {
    ok: false,
    message: (lastError && lastError.message) || "no response from any frame",
  };
}

function handleIncoming(raw) {
  let msg = null;
  try {
    msg = JSON.parse(raw.data);
  } catch (_e) {
    return;
  }
  if (!msg || msg.type !== "command") return;
  const id = msg.id || "";
  const action = msg.action || "";
  send({ type: "ack", id, timestamp: new Date().toISOString() });
  sendToActiveTab(action, msg.payload || {})
    .then((payload) => {
      if (payload && payload.ok === false) {
        send({
          type: "error",
          id,
          code: "execution_failed",
          message: payload.message || "execution failed",
          payload,
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
      if (tab && tab.id) {
        attachedTabId = tab.id;
      }
    }
    send({
      type: "heartbeat",
      timestamp: new Date().toISOString(),
      meta: {
        attached_tab_id: attachedTabId ? String(attachedTabId) : "",
        active_tab_id: tab && tab.id ? String(tab.id) : "",
        active_url: tab && tab.url ? tab.url : "",
      },
    });
  }, 5000);
}

function connect(reason = "boot") {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  log("connecting websocket", { reason, ws: WS_URL });
  socket = new WebSocket(WS_URL);
  socket.onopen = () => {
    connected = true;
    log("websocket connected");
    send({
      type: "hello",
      client_id: `ext-${chrome.runtime.id}`,
      timestamp: new Date().toISOString(),
      meta: {
        extension_id: chrome.runtime.id,
        version: chrome.runtime.getManifest().version,
        attached_tab_id: attachedTabId ? String(attachedTabId) : "",
      },
    });
  };
  socket.onmessage = handleIncoming;
  socket.onerror = (event) => {
    connected = false;
    log("websocket error", event && event.message ? event.message : "");
  };
  socket.onclose = (event) => {
    connected = false;
    log("websocket closed", { code: event && event.code, reason: event && event.reason });
    scheduleReconnect("onclose");
  };
}

function ensureConnected(reason = "manual") {
  if (socket && socket.readyState === WebSocket.OPEN) return;
  connect(reason);
}

chrome.runtime.onInstalled.addListener(() => {
  log("runtime onInstalled");
  ensureConnected("onInstalled");
});

chrome.runtime.onStartup.addListener(() => {
  log("runtime onStartup");
  ensureConnected("onStartup");
});

chrome.runtime.onSuspend.addListener(() => {
  log("runtime onSuspend");
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  attachedTabId = tabId;
  ensureConnected("tabs.onActivated");
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete") {
    if (tab && tab.active) {
      attachedTabId = tabId;
    }
    ensureConnected("tabs.onUpdated");
  }
});

chrome.action.onClicked.addListener(async (tab) => {
  if (tab && tab.id) {
    attachedTabId = tab.id;
  }
  log("action clicked", { attachedTabId });
  ensureConnected("action.onClicked");
});

log("service worker loaded");
ensureConnected("initial");
startHeartbeat();

