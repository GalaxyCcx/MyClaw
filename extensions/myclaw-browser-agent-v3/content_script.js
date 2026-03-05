/* eslint-disable no-console */
const CHANNEL = "myclaw-vision-v3";
const OVERLAY_ID = "__myclaw_vision_overlay_v3__";

let MARKS_CACHE = [];

function normText(v) {
  return String(v || "").replace(/\s+/g, " ").trim();
}

function isVisible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  const st = window.getComputedStyle(el);
  return r.width > 0 && r.height > 0 && st.display !== "none" && st.visibility !== "hidden";
}

function isInteractive(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = String(el.tagName || "").toLowerCase();
  const role = String(el.getAttribute("role") || "").toLowerCase();
  if (["a", "button", "input", "textarea", "select", "summary"].includes(tag)) return true;
  if (["button", "link", "textbox", "combobox", "checkbox", "radio", "menuitem", "tab", "switch"].includes(role)) return true;
  if (el.hasAttribute("onclick")) return true;
  if (el.hasAttribute("contenteditable")) return true;
  if (el.hasAttribute("tabindex") && Number(el.getAttribute("tabindex")) >= 0) return true;
  if (el.hasAttribute("aria-label") && ["div", "span", "i", "svg"].includes(tag)) return true;
  if (String(el.className || "").toLowerCase().includes("btn")) return true;
  if (el.isContentEditable) return true;
  if (typeof el.onclick === "function") return true;
  return false;
}

function clipRectToViewport(r) {
  const x1 = Math.max(0, r.left);
  const y1 = Math.max(0, r.top);
  const x2 = Math.min(window.innerWidth, r.right);
  const y2 = Math.min(window.innerHeight, r.bottom);
  const w = Math.max(0, x2 - x1);
  const h = Math.max(0, y2 - y1);
  return { x: x1, y: y1, width: w, height: h };
}

function isLikelyLoadingElement(el) {
  if (!el || !(el instanceof Element)) return false;
  const cls = String(el.className || "").toLowerCase();
  const role = String(el.getAttribute("role") || "").toLowerCase();
  const ariaBusy = String(el.getAttribute("aria-busy") || "").toLowerCase() === "true";
  if (ariaBusy) return true;
  if (role === "progressbar" || role === "status") return true;
  return (
    cls.includes("loading") ||
    cls.includes("skeleton") ||
    cls.includes("spin") ||
    cls.includes("spinner") ||
    cls.includes("shimmer")
  );
}

function nearestActionable(el) {
  if (!el || !(el instanceof Element)) return null;
  return (
    el.closest?.(
      "input,textarea,select,button,a,[role='button'],[role='tab'],[role='combobox'],[role='checkbox'],[role='radio'],[role='option'],[contenteditable='true'],[tabindex]",
    ) || el
  );
}

function collectInteractiveCandidates(dense) {
  const out = [];
  const seen = new Set();
  const pushEl = (el) => {
    if (!el || !(el instanceof Element)) return;
    if (seen.has(el)) return;
    seen.add(el);
    out.push(el);
  };

  // Tier-1: semantic interactive elements.
  const semanticSelectors = [
    "input",
    "textarea",
    "select",
    "button",
    "a[href]",
    "[role='button']",
    "[role='tab']",
    "[role='combobox']",
    "[role='checkbox']",
    "[role='radio']",
    "[role='option']",
    "[contenteditable='true']",
    "[tabindex]:not([tabindex='-1'])",
  ];
  for (const sel of semanticSelectors) {
    for (const el of Array.from(document.querySelectorAll(sel))) {
      if (isInteractive(el)) pushEl(el);
    }
  }

  // Tier-2: common BI wrapper elements that frequently hold click handlers.
  const biSelectors = [
    ".ant-select-selector",
    ".ant-select",
    ".ant-picker",
    ".ant-picker-input",
    ".ant-tabs-tab",
    ".ant-tabs-tab-btn",
    ".ant-tabs-nav .ant-tabs-tab",
    ".ant-tabs-nav .ant-tabs-tab-btn",
    ".ant-btn",
    ".ant-checkbox-wrapper",
    ".ant-radio-wrapper",
    ".ant-cascader-picker",
    ".ant-tree-select",
    ".rc-select-selector",
    ".ant-select-item-option",
    ".ant-dropdown-trigger",
    ".ant-table-filter-trigger",
    ".ant-table-column-sorters",
    ".ant-pagination-item",
    ".ant-pagination-next",
    ".ant-pagination-prev",
    ".ant-slider-handle",
    ".ant-switch",
    "[class*='dropdown']",
    "[class*='select']",
    "[class*='picker']",
    "[class*='filter']",
  ];
  for (const sel of biSelectors) {
    for (const node of Array.from(document.querySelectorAll(sel))) {
      if (!(node instanceof Element)) continue;
      pushEl(nearestActionable(node));
    }
  }

  if (dense) {
    // Tier-3 (dense): meaningful icon-like controls only.
    for (const el of Array.from(document.querySelectorAll("svg, i, span, div"))) {
      const cls = String(el.className || "").toLowerCase();
      const title = String(el.getAttribute("title") || el.getAttribute("aria-label") || "").trim();
      const text = normText(el.innerText || el.textContent || "");
      const hasSignal =
        cls.includes("icon") ||
        cls.includes("arrow") ||
        cls.includes("trigger") ||
        cls.includes("suffix") ||
        title.length > 0;
      if (!hasSignal) continue;
      if (text.length > 20) continue;
      pushEl(nearestActionable(el));
    }
  }

  // Tier-2.5: text tabs in nav area (important for BI page section switching).
  for (const node of Array.from(document.querySelectorAll(".ant-tabs-nav *, [class*='tabs'] *"))) {
    if (!(node instanceof Element)) continue;
    if (!isVisible(node)) continue;
    const txt = normText(node.innerText || node.textContent || "");
    if (txt.length < 2 || txt.length > 20) continue;
    const cls = String(node.className || "").toLowerCase();
    const likelyTab =
      cls.includes("tab") ||
      node.closest(".ant-tabs-tab, .ant-tabs-nav, [role='tablist'], [role='tab']");
    if (!likelyTab) continue;
    // Keep text carrier itself first, fallback to actionable parent.
    pushEl(node);
    pushEl(nearestActionable(node));
  }

  // Tier-2.6: explicit tablist structure (text-independent).
  const tabStructureSelectors = [
    ".ant-tabs-tab",
    ".ant-tabs-tab-btn",
    "[role='tab']",
    "[role='tablist'] [class*='tab']",
    "[class*='tabs-nav'] [class*='tab']",
  ];
  for (const sel of tabStructureSelectors) {
    for (const node of Array.from(document.querySelectorAll(sel))) {
      if (!(node instanceof Element)) continue;
      if (!isVisible(node)) continue;
      const r = node.getBoundingClientRect();
      if (r.width < 20 || r.height < 12) continue;
      pushEl(node);
      const childTextCarrier = node.querySelector?.("span,div,a");
      if (childTextCarrier instanceof Element) pushEl(childTextCarrier);
      pushEl(nearestActionable(node));
    }
  }

  // Tier-2.7: breadcrumb/tab-like text rows (e.g. "xxx -> yyy -> zzz").
  const arrowRows = Array.from(document.querySelectorAll("div,span,p,nav,section"))
    .filter((el) => {
      if (!(el instanceof Element) || !isVisible(el)) return false;
      const txt = normText(el.innerText || el.textContent || "");
      if (!txt) return false;
      const hasArrow = txt.includes("->") || txt.includes("→") || txt.includes(">");
      if (!hasArrow) return false;
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.top <= window.innerHeight * 0.7 && r.height <= 80;
    });
  for (const row of arrowRows) {
    const rowRect = row.getBoundingClientRect();
    const chips = Array.from(row.querySelectorAll("a,span,div,button"))
      .filter((node) => {
        if (!(node instanceof Element) || !isVisible(node)) return false;
        const t = normText(node.innerText || node.textContent || "");
        if (t.length < 2 || t.length > 24) return false;
        const rr = node.getBoundingClientRect();
        if (Math.abs(rr.top - rowRect.top) > 28) return false;
        if (rr.width < 20 || rr.width > 260 || rr.height < 14 || rr.height > 64) return false;
        return true;
      });
    for (const c of chips) {
      pushEl(c);
      pushEl(nearestActionable(c));
    }
  }

  return out;
}

function collectMarks(payload = {}) {
  const dense = Boolean(payload.dense);
  const maxMarks = Math.max(1, Math.min(600, Number(payload.max_marks || (dense ? 320 : 160))));
  const prefix = String(payload.label_prefix || "a").trim() || "a";
  const labelStart = Math.max(0, Number(payload.label_start || 0));
  const viewportOnly = payload.viewport_only !== false;
  const all = collectInteractiveCandidates(dense);
  const temp = [];
  let semanticCount = 0;
  let meaningfulCount = 0;
  for (const el of all) {
    if (!isVisible(el)) continue;
    const rect = clipRectToViewport(el.getBoundingClientRect());
    if (viewportOnly && (rect.width <= 0 || rect.height <= 0)) continue;
    const tag = String(el.tagName || "").toLowerCase();
    const role = String(el.getAttribute("role") || "");
    let text = "";
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
      text = normText(el.value || el.getAttribute("placeholder") || el.getAttribute("aria-label") || "").slice(0, 80);
    } else {
      text = normText(el.innerText || el.textContent || el.getAttribute("aria-label") || "").slice(0, 80);
    }
    let score = 0;
    const area = rect.width * rect.height;
    const isSemantic = ["input", "textarea", "select", "button", "a"].includes(tag) || String(role).length > 0;
    const meaningful = text.length > 0 || String(el.getAttribute("aria-label") || "").trim().length > 0;

    if (isSemantic) {
      score += 50;
      semanticCount += 1;
    }
    if (meaningful) {
      score += 18;
      meaningfulCount += 1;
    } else if (!["input", "textarea", "select"].includes(tag)) {
      score -= 12;
    }
    if (area <= 6) score -= 30;
    if (area > 120000) score -= 20;
    if (["div", "span"].includes(tag) && !isSemantic) score -= 10;
    if (!dense) score += Math.max(0, Math.min(20, Math.floor((window.innerHeight - rect.y) / 80)));
    temp.push({ rect, tag, role, text, score });
  }
  temp.sort((a, b) => b.score - a.score);

  const marks = [];
  for (const item of temp) {
    const cx = item.rect.x + item.rect.width / 2;
    const cy = item.rect.y + item.rect.height / 2;
    let duplicated = false;
    for (const m of marks) {
      const mcx = m.x + m.width / 2;
      const mcy = m.y + m.height / 2;
      const threshold = dense ? 2 : 6;
      if (Math.abs(mcx - cx) < threshold && Math.abs(mcy - cy) < threshold) {
        duplicated = true;
        break;
      }
    }
    if (duplicated) continue;
    const label = `${prefix}${labelStart + marks.length + 1}`;
    marks.push({
      label,
      x: Math.floor(item.rect.x),
      y: Math.floor(item.rect.y),
      width: Math.floor(item.rect.width),
      height: Math.floor(item.rect.height),
      tag: item.tag,
      role: item.role,
      text: item.text,
    });
    if (marks.length >= maxMarks) break;
  }
  const stats = {
    candidate_count: temp.length,
    semantic_count: semanticCount,
    meaningful_count: meaningfulCount,
    selected_count: marks.length,
    quality_score: marks.length > 0 ? Math.round(((semanticCount * 2 + meaningfulCount) / Math.max(1, temp.length)) * 1000) : 0,
  };
  return { marks, stats };
}

function pickScrollContainer() {
  const doc = document.scrollingElement || document.documentElement || document.body;
  let best = { el: doc, score: Math.max(0, (doc.scrollHeight || 0) - (doc.clientHeight || 0)) };
  const nodes = Array.from(document.querySelectorAll("div, main, section, article, aside"));
  for (const el of nodes) {
    if (!isVisible(el)) continue;
    const st = window.getComputedStyle(el);
    const overflowY = String(st.overflowY || st.overflow || "").toLowerCase();
    const canScroll = overflowY.includes("auto") || overflowY.includes("scroll") || overflowY.includes("overlay");
    if (!canScroll) continue;
    const capacity = Math.max(0, Number(el.scrollHeight || 0) - Number(el.clientHeight || 0));
    if (capacity < 20) continue;
    const rect = el.getBoundingClientRect();
    const area = Math.max(1, rect.width * rect.height);
    const score = capacity * 1000 + area;
    if (!best || score > best.score) best = { el, score };
  }
  return best.el || doc;
}

function clearOverlay() {
  const old = document.getElementById(OVERLAY_ID);
  if (old && old.parentNode) old.parentNode.removeChild(old);
}

function drawOverlay(marks) {
  clearOverlay();
  const root = document.createElement("div");
  root.id = OVERLAY_ID;
  root.style.position = "fixed";
  root.style.left = "0";
  root.style.top = "0";
  root.style.width = "100vw";
  root.style.height = "100vh";
  root.style.pointerEvents = "none";
  root.style.zIndex = "2147483646";
  root.style.fontFamily = "Arial, sans-serif";

  for (const m of marks) {
    const box = document.createElement("div");
    box.style.position = "fixed";
    box.style.left = `${m.x}px`;
    box.style.top = `${m.y}px`;
    box.style.width = `${Math.max(0, m.width)}px`;
    box.style.height = `${Math.max(0, m.height)}px`;
    box.style.outline = "2px dashed #ff2d55";
    box.style.background = "rgba(255,45,85,0.06)";
    box.style.boxSizing = "border-box";

    const lab = document.createElement("div");
    lab.textContent = m.label;
    lab.style.position = "absolute";
    lab.style.left = "0";
    lab.style.top = "0";
    lab.style.transform = "translate(0, -100%)";
    lab.style.background = "#ff2d55";
    lab.style.color = "#fff";
    lab.style.fontSize = "12px";
    lab.style.fontWeight = "700";
    lab.style.padding = "2px 6px";
    lab.style.borderRadius = "4px";
    lab.style.lineHeight = "1.2";
    lab.style.whiteSpace = "nowrap";

    box.appendChild(lab);
    root.appendChild(box);
  }
  document.documentElement.appendChild(root);
}

function markAction(payload = {}) {
  const out = collectMarks(payload);
  const marks = out.marks || [];
  const stats = out.stats || {};
  MARKS_CACHE = marks;
  drawOverlay(marks);
  return {
    ok: true,
    changed: true,
    marks,
    stats,
    quality_score: Number(stats.quality_score || 0),
    page: {
      title: document.title || "",
      url: location.href || "",
      viewport: { width: window.innerWidth, height: window.innerHeight },
    },
  };
}

function clearAction() {
  clearOverlay();
  MARKS_CACHE = [];
  return { ok: true, changed: true };
}

function getMarksAction() {
  return { ok: true, changed: false, marks: MARKS_CACHE };
}

function clickPointAction(payload = {}) {
  const x = Math.floor(Number(payload.x));
  const y = Math.floor(Number(payload.y));
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return { ok: false, error_code: "bad_input", message: "x/y required" };
  }
  const candidate = document.elementFromPoint(x, y);
  if (!candidate) return { ok: false, error_code: "target_not_found", message: "no element at point" };
  const target =
    candidate.closest?.("button, a, input, textarea, select, [role='button'], [role='link'], [tabindex]") ||
    candidate;
  const ev = { bubbles: true, cancelable: true, clientX: x, clientY: y };
  target.dispatchEvent(new MouseEvent("mouseenter", ev));
  target.dispatchEvent(new MouseEvent("mouseover", ev));
  target.dispatchEvent(new MouseEvent("mousemove", ev));
  target.dispatchEvent(new MouseEvent("mousedown", ev));
  target.dispatchEvent(new MouseEvent("mouseup", ev));
  if (typeof target.click === "function") target.click();
  else target.dispatchEvent(new MouseEvent("click", ev));
  return { ok: true, changed: true };
}

function typePointAction(payload = {}) {
  const clickRes = clickPointAction(payload);
  if (!clickRes.ok) return clickRes;
  const text = String(payload.text || "");
  const clear = payload.clear !== false;
  const el = document.activeElement;
  if (!el) return { ok: false, error_code: "no_active_element", message: "no active element after click" };
  const editable =
    el.isContentEditable === true ||
    el.tagName === "INPUT" ||
    el.tagName === "TEXTAREA" ||
    el.tagName === "SELECT";
  if (!editable) return { ok: false, error_code: "not_editable", message: "active element is not editable" };
  if (el.isContentEditable) {
    if (clear) el.textContent = "";
    el.textContent = text;
  } else {
    if (clear) el.value = "";
    el.value = text;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return { ok: true, changed: true };
}

async function waitStableAction(payload = {}) {
  const timeoutMs = Math.max(300, Number(payload.timeout_ms || 3000));
  const intervalMs = Math.max(100, Number(payload.interval_ms || 250));
  const settleRounds = Math.max(2, Number(payload.settle_rounds || 2));
  const minWaitMs = Math.max(0, Number(payload.min_wait_ms || 0));
  const deadline = Date.now() + timeoutMs;
  const minWaitUntil = Date.now() + minWaitMs;
  let stable = 0;
  let lastKey = "";
  while (Date.now() < deadline) {
    const all = document.querySelectorAll("*").length;
    const visible = Array.from(document.querySelectorAll("*")).filter((el) => isVisible(el)).length;
    const loadingCount = Array.from(document.querySelectorAll("*")).filter((el) => isLikelyLoadingElement(el) && isVisible(el)).length;
    const doc = document.documentElement;
    const body = document.body;
    const docHeight = Math.max(
      Number(doc?.scrollHeight || 0),
      Number(body?.scrollHeight || 0),
      Number(doc?.offsetHeight || 0),
      Number(body?.offsetHeight || 0),
    );
    const key = `${all}|${visible}|${Math.floor(docHeight)}|${loadingCount}`;
    if (key === lastKey) stable += 1;
    else stable = 0;
    lastKey = key;
    const passedMinWait = Date.now() >= minWaitUntil;
    if (stable >= settleRounds && loadingCount === 0 && passedMinWait) {
      return { ok: true, changed: false, stable: true, key, loading_count: loadingCount };
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return { ok: true, changed: false, stable: false, key: lastKey, loading_count: -1 };
}

function handleAction(action, payload) {
  switch (action) {
    case "vision_mark":
      return markAction(payload || {});
    case "vision_clear_marks":
      return clearAction();
    case "vision_get_marks":
      return getMarksAction();
    case "vision_click_point":
      return clickPointAction(payload || {});
    case "vision_type_point":
      return typePointAction(payload || {});
    case "vision_scroll_by": {
      const dy = Math.floor(Number((payload || {}).dy || 0));
      const target = pickScrollContainer();
      const before = Math.floor(Number(target.scrollTop || window.scrollY || 0));
      if (target === document.body || target === document.documentElement || target === document.scrollingElement) {
        window.scrollBy(0, dy);
      } else {
        target.scrollTop = before + dy;
      }
      const after = Math.floor(Number(target.scrollTop || window.scrollY || 0));
      const doc = document.documentElement || target;
      const body = document.body || target;
      const docHeight = Math.max(
        Number(target.scrollHeight || 0),
        Number(doc?.scrollHeight || 0),
        Number(body?.scrollHeight || 0),
        Number(doc?.offsetHeight || 0),
        Number(body?.offsetHeight || 0),
      );
      return {
        ok: true,
        changed: before !== after,
        before_scroll_y: before,
        after_scroll_y: after,
        viewport_height: Math.floor(window.innerHeight || 0),
        doc_height: Math.floor(docHeight || 0),
        scroll_target_tag: String(target.tagName || "").toLowerCase(),
      };
    }
    case "vision_wait_stable":
      return waitStableAction(payload || {});
    default:
      return { ok: false, error_code: "unsupported_action", message: `unsupported action: ${action}` };
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.channel !== CHANNEL) return false;
  const action = String(msg.action || "");
  const payload = msg.payload || {};
  Promise.resolve(handleAction(action, payload))
    .then((result) => sendResponse(result))
    .catch((err) => sendResponse({ ok: false, error_code: "script_exception", message: String(err) }));
  return true;
});

