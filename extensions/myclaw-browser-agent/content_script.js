/* eslint-disable no-console */
const REF_ATTR = "data-myclaw-ref";
let refCounter = 1;

function normalizeText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function normalizeMatchText(text) {
  // Remove all whitespace so "查 询" and "查询" are treated the same.
  return normalizeText(text).replace(/\s+/g, "");
}

function isVisible(el) {
  if (!el || !(el instanceof Element)) return false;
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return (
    rect.width > 0 &&
    rect.height > 0 &&
    style.visibility !== "hidden" &&
    style.display !== "none" &&
    style.opacity !== "0"
  );
}

function getLabel(el) {
  if (!el) return "";
  const aria = el.getAttribute("aria-label");
  if (aria) return aria.trim();
  const placeholder = el.getAttribute("placeholder");
  if (placeholder) return placeholder.trim();
  const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
  return text.slice(0, 80);
}

function getRole(el) {
  return el.getAttribute("role") || "";
}

function ensureRef(el) {
  const existing = el.getAttribute(REF_ATTR);
  if (existing) return existing;
  const ref = `e${refCounter++}`;
  el.setAttribute(REF_ATTR, ref);
  return ref;
}

function getElementByRef(ref) {
  if (!ref) return null;
  return document.querySelector(`[${REF_ATTR}="${String(ref)}"]`);
}

function buildSelectorHint(el) {
  const esc = (v) => {
    if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
      return CSS.escape(v);
    }
    return String(v).replace(/"/g, '\\"');
  };
  const id = el.getAttribute("id");
  if (id) return `#${esc(id)}`;
  const name = el.getAttribute("name");
  if (name) return `[name="${esc(name)}"]`;
  return "";
}

function isInteractive(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = el.tagName.toLowerCase();
  const role = getRole(el);
  const hasClick = typeof el.onclick === "function";
  const tabIndex = Number(el.getAttribute("tabindex"));
  if (["button", "a", "input", "select", "textarea"].includes(tag)) return true;
  if (["button", "link", "textbox", "combobox", "option", "checkbox", "radio", "menuitem", "switch", "tab"].includes(role)) return true;
  if (el.isContentEditable) return true;
  // 避免仅因 tabindex 命中过多容器元素，导致文本点击歧义。
  if (!Number.isNaN(tabIndex) && tabIndex >= 0 && (hasClick || role)) return true;
  return hasClick;
}

function isClickable(el) {
  if (!el || !(el instanceof Element)) return false;
  const tag = el.tagName.toLowerCase();
  const role = getRole(el);
  if (["button", "a", "summary"].includes(tag)) return true;
  if (["button", "link", "menuitem", "tab", "switch"].includes(role)) return true;
  if (el.classList && el.classList.contains("ant-btn")) return true;
  return typeof el.onclick === "function";
}

function isAlphaBiPage() {
  const href = String(window.location.href || "");
  return href.includes("alpha-bi.ddxq.mobi/report");
}

function isForbiddenAlphaBiTextClick(text) {
  const v = normalizeMatchText(text);
  if (!v) return false;
  // 这些文本在 Alpha BI 页面高频重复，text 点击极易误命中。
  const blocked = new Set(["当期", "对比期", "查询", "~"]);
  return blocked.has(v);
}

function collectInteractiveElements(limit) {
  const all = Array.from(document.querySelectorAll("*"));
  const out = [];
  for (const el of all) {
    if (!isInteractive(el) || !isVisible(el)) continue;
    const ref = ensureRef(el);
    out.push({
      ref,
      tag: el.tagName.toLowerCase(),
      role: getRole(el),
      type: el.getAttribute("type") || "",
      label: getLabel(el),
      selector_hint: buildSelectorHint(el),
    });
    if (out.length >= limit) break;
  }
  return out;
}

function queryElementsByText(text, options = {}) {
  const { mode = "click" } = options;
  const wanted = normalizeMatchText(text);
  if (!wanted) return [];
  const all = Array.from(document.querySelectorAll("*"));
  const exact = [];
  const contains = [];
  for (const el of all) {
    if (!isVisible(el) || !isInteractive(el)) continue;
    if (mode === "click" && !isClickable(el)) continue;
    if (mode === "type") {
      const tag = el.tagName.toLowerCase();
      if (!(tag === "input" || tag === "textarea" || el.isContentEditable)) continue;
    }
    if (mode === "select") {
      if (!(el instanceof HTMLSelectElement)) continue;
    }
    const content = normalizeMatchText(getLabel(el));
    if (!content) continue;
    if (content === wanted) {
      exact.push(el);
      continue;
    }
    if (content.includes(wanted)) {
      contains.push(el);
    }
  }
  return exact.length ? exact : contains;
}

function resolveTarget(payload, options = {}) {
  const { requireUniqueText = false, mode = "click", locatorTextKey = "text" } = options;
  const locatorText = payload ? payload[locatorTextKey] : undefined;
  if (payload.ref) {
    const byRef = getElementByRef(payload.ref);
    if (!byRef) return { ok: false, message: `ref not found: ${payload.ref}` };
    return { ok: true, element: byRef };
  }
  if (payload.selector) {
    const bySelector = document.querySelector(payload.selector);
    if (!bySelector) return { ok: false, message: `selector not found: ${payload.selector}` };
    return { ok: true, element: bySelector };
  }
  if (locatorText) {
    const matched = queryElementsByText(locatorText, { mode });
    if (!matched.length) return { ok: false, message: "element not found" };
    if (requireUniqueText && matched.length > 1) {
      const candidates = matched.slice(0, 6).map((el) => ({
        ref: ensureRef(el),
        label: getLabel(el),
        tag: el.tagName.toLowerCase(),
      }));
      return {
        ok: false,
        message: "ambiguous text match",
        candidates,
      };
    }
    return { ok: true, element: matched[0] };
  }
  return { ok: false, message: "missing target(ref/selector/text)" };
}

function getInputValue(el) {
  if (!el) return "";
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
    return String(el.value || "");
  }
  if (el.isContentEditable) return String(el.textContent || "");
  return "";
}

function isEditableElement(el) {
  if (!el || !(el instanceof Element)) return false;
  return (
    el instanceof HTMLInputElement ||
    el instanceof HTMLTextAreaElement ||
    el instanceof HTMLSelectElement ||
    el.isContentEditable
  );
}

function findDefaultTypeTarget() {
  const active = document.activeElement;
  if (isEditableElement(active) && isVisible(active)) return active;
  const commonSelectors = [
    "input[name='wd']",
    "#kw",
    "input[type='search']",
    "input[type='text']",
    "textarea",
    "[contenteditable='true']",
  ];
  for (const selector of commonSelectors) {
    const el = document.querySelector(selector);
    if (isEditableElement(el) && isVisible(el)) return el;
  }
  return null;
}

function setInputValue(el, value) {
  const strVal = String(value || "");
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
    if (setter) {
      setter.call(el, strVal);
    } else {
      el.value = strVal;
    }
  } else if (el.isContentEditable) {
    el.textContent = strVal;
  } else {
    throw new Error("target is not an input element");
  }
}

function buildSnapshot(mode) {
  const title = document.title || "";
  const url = window.location.href;
  const full = mode === "full";
  const textLimit = full ? 3000 : 800;
  const elementLimit = full ? 160 : 60;
  const text = document.body && document.body.innerText ? document.body.innerText.slice(0, textLimit) : "";
  const elements = collectInteractiveElements(elementLimit);
  return {
    title,
    url,
    text,
    elements,
    elements_count: elements.length,
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms || 0))));
}

function parseYmd(value) {
  const m = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  return {
    y: Number(m[1]),
    m: Number(m[2]),
    d: Number(m[3]),
    ym: Number(m[1]) * 12 + Number(m[2]),
  };
}

function monthDiff(fromYmd, toYmd) {
  const from = parseYmd(fromYmd);
  const to = parseYmd(toYmd);
  if (!from || !to) return 0;
  return Math.max(0, from.ym - to.ym);
}

function getVisibleDateInputs() {
  const all = Array.from(document.querySelectorAll("input"));
  return all.filter((el) => {
    if (!isVisible(el)) return false;
    const ph = String(el.getAttribute("placeholder") || "");
    const val = String(el.value || "");
    if (ph.includes("日期")) return true;
    if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return true;
    return false;
  });
}

function getVisibleDateRangeCandidates() {
  const allInputs = Array.from(document.querySelectorAll("input"));
  const dateInputs = allInputs.filter((el) => isVisible(el) && /^\d{4}-\d{2}-\d{2}$/.test(String(el.value || "")));
  if (dateInputs.length < 2) return [];
  // 按页面顺序两两分组，形成候选 range。
  const pairs = [];
  for (let i = 0; i < dateInputs.length - 1; i += 1) {
    const a = dateInputs[i];
    const b = dateInputs[i + 1];
    if (a === b) continue;
    const ra = a.getBoundingClientRect();
    const rb = b.getBoundingClientRect();
    // 近邻且同一视觉行优先视作一组
    const sameRow = Math.abs(ra.top - rb.top) < 28;
    const close = Math.abs(ra.left - rb.left) < 320;
    if (sameRow && close) {
      pairs.push([a, b]);
      i += 1;
    }
  }
  // 兜底：若没识别出近邻组，直接按顺序配对
  if (!pairs.length) {
    for (let i = 0; i < dateInputs.length - 1; i += 2) {
      pairs.push([dateInputs[i], dateInputs[i + 1]]);
    }
  }
  return pairs;
}

function findDateCell(date) {
  const selectors = [
    `[title='${date}']`,
    `[title='${date}'] .ant-picker-cell-inner`,
    `.ant-picker-cell[title='${date}']`,
  ];
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el && isVisible(el)) return el;
  }
  return null;
}

function clickElement(el) {
  if (!el) return false;
  el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
  el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  el.click();
  return true;
}

async function shiftPanelToTargetMonth(fromDate, targetDate) {
  const n = monthDiff(fromDate, targetDate);
  for (let i = 0; i < Math.min(n, 24); i += 1) {
    const prevBtn = document.querySelector(".ant-picker-header-prev-btn, .ant-calendar-prev-month-btn");
    if (!prevBtn || !isVisible(prevBtn)) break;
    clickElement(prevBtn);
    await sleep(100);
  }
}

async function pickDateRange(startInput, startDate, endDate, baselineStartValue) {
  if (!startInput) return { ok: false, message: "start input not found" };
  clickElement(startInput);
  await sleep(180);
  await shiftPanelToTargetMonth(baselineStartValue, startDate);

  const startCell = findDateCell(startDate);
  if (!startCell) return { ok: false, message: `start day cell not found: ${startDate}` };
  clickElement(startCell);
  await sleep(100);

  const endCell = findDateCell(endDate);
  if (!endCell) return { ok: false, message: `end day cell not found: ${endDate}` };
  clickElement(endCell);
  await sleep(240);

  return { ok: true };
}

async function alphaBiSetDateRanges(payload) {
  const currentStart = String(payload.current_start || "");
  const currentEnd = String(payload.current_end || "");
  const compareStart = String(payload.compare_start || "");
  const compareEnd = String(payload.compare_end || "");
  if (!currentStart || !currentEnd || !compareStart || !compareEnd) {
    return { ok: false, message: "missing date params" };
  }

  const pairs = getVisibleDateRangeCandidates();
  if (pairs.length < 2) {
    const dateInputs = getVisibleDateInputs();
    return { ok: false, message: "visible date range pairs < 2", found_inputs: dateInputs.length, found_pairs: pairs.length };
  }

  // 尝试候选组合：前两组为主，不通过则滑动窗口重试。
  const candidates = [];
  for (let i = 0; i < pairs.length - 1; i += 1) {
    candidates.push([pairs[i], pairs[i + 1]]);
    if (candidates.length >= 3) break;
  }
  if (!candidates.length) candidates.push([pairs[0], pairs[1]]);

  const expected = [currentStart, currentEnd, compareStart, compareEnd];
  let lastBefore = [];
  let lastAfter = [];
  for (const combo of candidates) {
    const currentPair = combo[0];
    const comparePair = combo[1];
    const targetInputs = [currentPair[0], currentPair[1], comparePair[0], comparePair[1]];
    const before = targetInputs.map((el) => String(el.value || ""));
    lastBefore = before;

    const first = await pickDateRange(targetInputs[0], currentStart, currentEnd, before[0]);
    if (!first.ok) continue;
    const second = await pickDateRange(targetInputs[2], compareStart, compareEnd, before[2]);
    if (!second.ok) continue;

    const after = targetInputs.map((el) => String(el.value || ""));
    lastAfter = after;
    const ok = expected.every((v, i) => after[i] === v);
    if (ok) {
      return {
        ok: true,
        message: "alpha-bi date ranges set",
        before,
        after,
        expected,
      };
    }
  }

  return {
    ok: false,
    message: "date value mismatch after pick",
    expected,
    before: lastBefore,
    after: lastAfter,
  };
}


async function handleAction(action, payload) {
  switch (action) {
    case "hover": {
      const target = resolveTarget(payload, { requireUniqueText: true, mode: "click" });
      if (!target.ok) return target;
      const el = target.element;
      el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
      return { ok: true, message: "hovered", target: { ref: ensureRef(el), label: getLabel(el) } };
    }
    case "click": {
      if (payload && payload.text && isAlphaBiPage() && isForbiddenAlphaBiTextClick(payload.text)) {
        return {
          ok: false,
          message: "alpha-bi forbids text click for this target; use snapshot ref/selector",
        };
      }
      const target = resolveTarget(payload, { requireUniqueText: true, mode: "click" });
      if (!target.ok) return target;
      const el = target.element;
      el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
      el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
      el.click();
      return { ok: true, message: "clicked", target: { ref: ensureRef(el), label: getLabel(el) } };
    }
    case "type": {
      let el = null;
      const hasLocator = Boolean(payload.ref || payload.selector || payload.target_text);
      if (hasLocator) {
        const target = resolveTarget(payload, {
          requireUniqueText: true,
          mode: "type",
          locatorTextKey: "target_text",
        });
        if (!target.ok) return target;
        el = target.element;
      } else {
        el = findDefaultTypeTarget();
        if (!el) return { ok: false, message: "input not found" };
      }
      const before = getInputValue(el);
      if (!before && !isEditableElement(el)) {
        return { ok: false, message: "input not found" };
      }
      el.focus();
      if (payload.clear !== false) {
        setInputValue(el, "");
      }
      setInputValue(el, payload.text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      const after = getInputValue(el);
      const expected = String(payload.text || "");
      if (after !== expected) {
        return {
          ok: false,
          message: "typed value mismatch",
          expected,
          actual: after,
        };
      }
      return {
        ok: true,
        message: "typed",
        target: { ref: ensureRef(el), label: getLabel(el) },
        before,
        after,
      };
    }
    case "press_key": {
      const key = String(payload.key || "Enter");
      document.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
      document.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
      return { ok: true, message: `pressed ${key}` };
    }
    case "snapshot": {
      return { ok: true, snapshot: buildSnapshot(payload.mode || "summary") };
    }
    case "alpha_bi_set_date_ranges": {
      return alphaBiSetDateRanges(payload || {});
    }
    case "select_option": {
      const target = resolveTarget(payload, { requireUniqueText: true, mode: "select" });
      if (!target.ok) return target;
      const el = target.element;
      if (!(el instanceof HTMLSelectElement)) {
        return { ok: false, message: "select element not found" };
      }
      const value = String(payload.value || "");
      el.value = value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      if (String(el.value || "") !== value) {
        return {
          ok: false,
          message: "selected value mismatch",
          expected: value,
          actual: String(el.value || ""),
        };
      }
      return { ok: true, message: "selected", target: { ref: ensureRef(el), label: getLabel(el) } };
    }
    default:
      return { ok: false, message: `unsupported action in content script: ${action}` };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.channel !== "myclaw-native") return undefined;
  handleAction(message.action, message.payload || {})
    .then((result) => sendResponse({ ok: true, payload: result }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));
  return true;
});

