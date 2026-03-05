/* eslint-disable no-console */
const CHANNEL = "myclaw-native-v2";

let HANDLE_SEQ = 0;
const HANDLES = new Map();

function newHandle(el) {
  HANDLE_SEQ += 1;
  const id = `e${HANDLE_SEQ}`;
  HANDLES.set(id, el);
  return id;
}

function getByHandle(handle) {
  if (!handle) return null;
  const el = HANDLES.get(String(handle));
  if (!el || !document.contains(el)) return null;
  return el;
}

function norm(v) {
  return String(v || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isVisible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  const st = window.getComputedStyle(el);
  return r.width > 0 && r.height > 0 && st.display !== "none" && st.visibility !== "hidden";
}

function textOf(el) {
  return String(el?.innerText || el?.textContent || "").replace(/\s+/g, " ").trim();
}

function isEditable(el) {
  if (!el) return false;
  const tag = String(el.tagName || "").toLowerCase();
  return tag === "textarea" || tag === "input" || el.isContentEditable === true;
}

function elementMeta(el, handle) {
  const tag = String(el?.tagName || "").toLowerCase();
  return {
    handle,
    tag,
    text: textOf(el).slice(0, 120),
    role: String(el?.getAttribute?.("role") || ""),
    id: String(el?.id || ""),
    cls: String(el?.className || "").slice(0, 120),
    ref: String(el?.getAttribute?.("data-myclaw-ref") || ""),
  };
}

function querySelectorAllDeep(selector, root) {
  const results = [];
  const r = root || document;
  try {
    results.push(...Array.from(r.querySelectorAll(selector)));
    r.querySelectorAll("*").forEach((el) => {
      if (el.shadowRoot) {
        results.push(...querySelectorAllDeep(selector, el.shadowRoot));
      }
    });
  } catch (_e) {}
  return results;
}

function isInsideExcluded(el, exclude) {
  if (!el || !exclude) return false;
  const arr = Array.isArray(exclude) ? exclude : [exclude];
  for (const sel of arr) {
    const s = String(sel || "").trim();
    if (s && el.closest && el.closest(s)) return true;
  }
  return false;
}

function resolveFromLocator(locator = {}) {
  if (locator.handle) {
    const h = getByHandle(locator.handle);
    if (h) return h;
  }
  const exclude = locator.exclude;
  const before = locator.before;
  if (before && typeof before === "object" && before.selector) {
    const anchorSel = String(before.selector).trim();
    const anchor = document.querySelector(anchorSel);
    if (!anchor) return null;
    if (exclude && isInsideExcluded(anchor, exclude)) return null;
    let prev = anchor.previousElementSibling;
    const limit = 5;
    let i = 0;
    while (prev && i < limit) {
      const btn = prev.querySelector ? prev.querySelector("button, [role='button']") : null;
      const target = btn || (prev.matches && prev.matches("button, [role='button']") ? prev : null);
      if (target && isVisible(target) && !(exclude && isInsideExcluded(target, exclude))) return target;
      prev = prev.previousElementSibling;
      i++;
    }
    return null;
  }
  const selector = String(locator.selector || "").trim();
  const text = String(locator.text || "").trim();
  const role = String(locator.role || "").trim();
  const exact = Boolean(locator.exact);
  const index = Math.max(0, Number(locator.index || 0));
  const deep = Boolean(locator.deep);
  const within = locator.within;

  let searchRoot = document;
  if (within && typeof within === "object") {
    const blockText = String(within.text || "").trim();
    if (blockText) {
      const blockSel = "div, section, article, main, [class*='card'], [class*='block'], [class*='panel'], [class*='section'], [class*='container'], [class*='content']";
      const all = Array.from(document.querySelectorAll(blockSel));
      const matches = all.filter((el) => norm(textOf(el)).includes(norm(blockText)));
      // 排除含「贡献拆解」「二、问题定位」的块，避免误命中
      const excludeBlock = (el) => {
        const t = norm(textOf(el));
        return t.includes("贡献拆解") || t.includes("二、问题定位");
      };
      const filtered = matches.filter((el) => !excludeBlock(el));
      if (filtered.length) {
        searchRoot = filtered[0];
      } else if (matches.length) {
        searchRoot = matches[0];
      }
    }
  }

  const baseSelector = selector || "button, a, input, textarea, select, [role], [data-myclaw-ref], div, span";
  let nodes = Array.from(searchRoot.querySelectorAll(baseSelector));
  if (!nodes.length && deep) {
    nodes = querySelectorAllDeep(baseSelector, searchRoot);
  }
  nodes = nodes.filter((n) => isVisible(n));

  if (role) {
    const rr = norm(role);
    nodes = nodes.filter((n) => norm(n.getAttribute("role")) === rr);
  }
  if (text) {
    const tt = norm(text);
    nodes = nodes.filter((n) => {
      const nt = norm(textOf(n) || n.getAttribute("aria-label") || n.getAttribute("title"));
      return exact ? nt === tt : nt.includes(tt);
    });
  }
  if (exclude) {
    nodes = nodes.filter((n) => !isInsideExcluded(n, exclude));
  }

  if (!nodes.length) return null;
  return nodes[Math.min(index, nodes.length - 1)];
}

function actionResult(ok, payload = {}) {
  return { ok: Boolean(ok), ...payload };
}

function snapshot() {
  const all = Array.from(document.querySelectorAll("*"));
  const visible = all.filter((x) => isVisible(x));
  const interactive = visible.filter((el) => {
    const tag = String(el.tagName || "").toLowerCase();
    const role = String(el.getAttribute("role") || "").toLowerCase();
    return tag === "button" || tag === "a" || tag === "input" || tag === "textarea" || tag === "select" || role === "button";
  });
  return actionResult(true, {
    changed: false,
    snapshot: {
      title: document.title || "",
      url: location.href || "",
      text: textOf(document.body).slice(0, 8000),
      elements_count: visible.length,
      interactive_count: interactive.length,
    },
  });
}

function locate(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  if (NO_CLICK_SELECTORS.some((sel) => el.closest && el.closest(sel))) {
    return actionResult(false, { error_code: "forbidden", message: "element is in header/logo area" });
  }
  const handle = newHandle(el);
  return actionResult(true, { changed: false, element: elementMeta(el, handle) });
}

const NO_CLICK_SELECTORS = [
  ".ant-layout-header",
  "[class*='layout-header']",
  "[class*='header-logo']",
  "[class*='vben-layout-header']",
  "[class*='vben-app-logo']",  // Alpha BI 顶栏 logo，禁止点击
];

function click(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  let el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  if (NO_CLICK_SELECTORS.some((sel) => el.closest && el.closest(sel))) {
    return actionResult(false, { error_code: "forbidden", message: "element is in header/logo area" });
  }
  const tag = String(el.tagName || "").toLowerCase();
  const role = String(el.getAttribute?.("role") || "").toLowerCase();
  if ((tag === "svg" || tag === "path" || role === "img") && el.closest) {
    const btn = el.closest("button, [role='button']");
    if (btn) el = btn;
  }
  if (NO_CLICK_SELECTORS.some((sel) => el.closest && el.closest(sel))) {
    return actionResult(false, { error_code: "forbidden", message: "element is in header/logo area" });
  }
  el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
  const before = textOf(el);
  if (typeof el.click === "function") el.click();
  else el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  return actionResult(true, { changed: true, before: { text: before }, after: { text: textOf(el) }, element: elementMeta(el, newHandle(el)) });
}

function type(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const text = String(payload.text || "");
  const clear = payload.clear !== false;
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  if (!isEditable(el)) return actionResult(false, { error_code: "not_editable", message: "element is not editable" });
  el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
  el.focus();
  const before = String(el.value ?? textOf(el));
  if (clear && "value" in el) el.value = "";
  if ("value" in el) el.value = text;
  else el.textContent = text;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return actionResult(true, { changed: before !== text, before: { value: before }, after: { value: String(el.value ?? textOf(el)) }, element: elementMeta(el, newHandle(el)) });
}

function hover(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  const r = el.getBoundingClientRect();
  const evt = { bubbles: true, cancelable: true, clientX: Math.floor(r.left + r.width / 2), clientY: Math.floor(r.top + r.height / 2) };
  el.dispatchEvent(new MouseEvent("mouseenter", evt));
  el.dispatchEvent(new MouseEvent("mouseover", evt));
  el.dispatchEvent(new MouseEvent("mousemove", evt));
  return actionResult(true, { changed: true, element: elementMeta(el, newHandle(el)) });
}

function pressKey(payload = {}) {
  const key = String(payload.key || "Enter");
  const target = document.activeElement || document.body;
  target.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key }));
  target.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key }));
  return actionResult(true, { changed: true, key });
}

function selectOption(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const value = String(payload.value ?? "");
  const label = String(payload.label ?? "");
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  const tag = String(el.tagName || "").toLowerCase();
  if (tag !== "select") return actionResult(false, { error_code: "not_select", message: "element is not select" });
  const before = String(el.value || "");
  let selected = null;
  for (const opt of Array.from(el.options || [])) {
    if ((value && String(opt.value) === value) || (label && textOf(opt) === label)) {
      selected = opt;
      break;
    }
  }
  if (!selected) return actionResult(false, { error_code: "option_not_found", message: "option not found" });
  el.value = String(selected.value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return actionResult(true, { changed: before !== el.value, before: { value: before }, after: { value: String(el.value) }, element: elementMeta(el, newHandle(el)) });
}

function getDropdownOptions(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  let root = document;
  if (locator && (locator.selector || locator.handle)) {
    const container = resolveFromLocator(locator);
    if (container) root = container;
  }
  const dropdownSels = [
    ".ant-select-dropdown",
    "[class*='ant-select-dropdown']",
    "[class*='rc-select-dropdown']",
    ".rc-select-dropdown",
    "[role='listbox']",
    ".rc-virtual-list",
    "[class*='rc-virtual-list']",
    "[class*='dropdown']",
    ".ant-dropdown",
    "[role='menu']",
    "div[role='listbox']",
  ];
  let dropdowns = [];
  const rootsToSearch = [];
  const seenDocs = new Set();
  try {
    const addDoc = (d) => {
      if (d && !seenDocs.has(d)) {
        seenDocs.add(d);
        rootsToSearch.push(d);
      }
    };
    addDoc(root);
    addDoc(window.parent?.document);
    addDoc(window.top?.document);
    // 搜索同源 iframe 内的 dropdown（Alpha BI 等 BI 报表常渲染在 iframe）
    for (const doc of [document, window.top?.document].filter(Boolean)) {
      if (!doc?.querySelectorAll) continue;
      try {
        for (const ifr of Array.from(doc.querySelectorAll("iframe"))) {
          try {
            const cd = ifr.contentDocument;
            if (cd) addDoc(cd);
          } catch (_) {}
        }
      } catch (_) {}
    }
  } catch (_e) {}
  for (const r of rootsToSearch) {
    for (const sel of dropdownSels) {
      let candidates = Array.from(r.querySelectorAll(sel));
      dropdowns = candidates.filter((el) => isVisible(el));
      if (!dropdowns.length && candidates.length) dropdowns = candidates;
      if (!dropdowns.length && r.querySelectorAll) {
        candidates = querySelectorAllDeep(sel, r);
        dropdowns = candidates.filter((el) => isVisible(el));
        if (!dropdowns.length && candidates.length) dropdowns = candidates;
      }
      if (!dropdowns.length && candidates.length) {
        const r0 = candidates[0];
        const rect = r0?.getBoundingClientRect?.();
        if (rect && (rect.width > 0 || rect.height > 0)) dropdowns = [r0];
      }
      if (dropdowns.length) break;
    }
    if (dropdowns.length) break;
  }
  if (!dropdowns.length) {
    const targetText = String((payload && payload.target_text) || "").trim();
    if (targetText) {
      for (const r of rootsToSearch) {
        const allDivs = Array.from(r.querySelectorAll("div, span, li"));
        const withText = allDivs.filter((el) => {
          const t = textOf(el).trim();
          return t === targetText || t.includes(targetText) || targetText.includes(t);
        });
        for (const el of withText) {
          const parent = el.closest ? el.closest("[role='listbox'], [role='menu'], .ant-select-dropdown, [class*='dropdown'], [class*='select-dropdown']") : null;
          if (parent) {
            const items = Array.from(parent.querySelectorAll("[role='option'], div, span, li")).filter((e) => textOf(e).trim().length > 0 && textOf(e).trim().length < 80);
            if (items.length) {
              dropdowns = [parent];
              break;
            }
          }
        }
        if (dropdowns.length) break;
      }
    }
  }
  if (!dropdowns.length) {
    const debugCounts = {};
    for (const r of rootsToSearch) {
      for (const sel of dropdownSels) {
        try {
          const c = r.querySelectorAll(sel).length;
          debugCounts[sel] = (debugCounts[sel] || 0) + c;
        } catch (_e) {}
      }
    }
    return actionResult(false, { error_code: "dropdown_not_visible", message: "no visible ant-select-dropdown found", _debug_counts: debugCounts });
  }
  const dropdown = dropdowns[0];
  const itemSels = [
    ".ant-select-item",
    ".ant-select-item-option",
    ".ant-select-dropdown-menu-item",
    ".rc-select-item",
    ".rc-select-item-option",
    "[class*='select-item']",
    "[role='option']",
    "div[role='option']",
    ".rc-virtual-list-holder > div",
    ".rc-virtual-list-holder [class*='item']",
    "[class*='option-content']",
  ];
  let items = [];
  for (const sel of itemSels) {
    const candidates = Array.from(dropdown.querySelectorAll(sel));
    items = candidates.filter(isVisible);
    if (!items.length && candidates.length) items = candidates;
    if (items.length) break;
  }
  if (!items.length) {
    const withValue = Array.from(dropdown.querySelectorAll("[data-value], [data-option-value], [value]"));
    items = withValue.filter((el) => textOf(el).trim().length > 0);
  }
  if (!items.length) {
    const inListbox = dropdown.querySelector("[role='listbox']");
    if (inListbox) {
      items = Array.from(inListbox.querySelectorAll("[role='option'], div, span")).filter((el) => textOf(el).trim().length > 0 && textOf(el).trim().length < 80);
    }
  }
  const options = items.map((el) => {
    const handle = newHandle(el);
    const txt = textOf(el).trim();
    const val = String(el.getAttribute("data-value") || el.getAttribute("value") || el.getAttribute("data-option-value") || "").trim();
    return { handle, text: txt, value: val };
  });
  const debug = options.length === 0 ? {
    dropdown_class: dropdown.className,
    dropdown_tag: dropdown.tagName,
    child_count: dropdown.children.length,
    first_child_class: dropdown.firstElementChild?.className?.slice(0, 80),
    html_sample: dropdown.innerHTML.slice(0, 500),
  } : null;
  return actionResult(true, { options, ...(debug ? { _debug: debug } : {}) });
}

function findScrollable(el) {
  let p = el.parentElement;
  while (p && p !== document.body) {
    const st = window.getComputedStyle(p);
    const oy = st.overflowY || st.overflow;
    if (oy === "auto" || oy === "scroll" || oy === "overlay") return p;
    p = p.parentElement;
  }
  return document.scrollingElement || document.documentElement;
}

function scrollElementToTop(el) {
  let current = el;
  const seen = new Set();
  while (current && !seen.has(current)) {
    seen.add(current);
    const scrollable = findScrollable(current);
    if (scrollable === current) break;
    const rect = current.getBoundingClientRect();
    const isDoc = scrollable === document.scrollingElement || scrollable === document.documentElement;
    const delta = isDoc ? rect.top : rect.top - (scrollable.getBoundingClientRect?.()?.top ?? 0);
    if (Math.abs(delta) > 2) {
      scrollable.scrollTop = Math.max(0, (scrollable.scrollTop || 0) + delta);
    }
    if (isDoc) break;
    current = scrollable;
  }
}

function scrollIntoViewAction(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  const block = String(payload.block || "start").toLowerCase();
  if (block === "center") {
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
  } else {
    scrollElementToTop(el);
    if (window.frameElement) {
      window.frameElement.scrollIntoView({ block: "start", behavior: "auto" });
    }
  }
  return actionResult(true, { changed: true, element: elementMeta(el, newHandle(el)) });
}

async function waitFor(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const state = String(payload.state || "visible");
  const timeoutMs = Math.max(50, Number(payload.timeout_ms || 3000));
  const pollMs = Math.max(25, Number(payload.poll_ms || 120));
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const el = resolveFromLocator(locator);
    if (state === "attached" && el) return actionResult(true, { changed: true, message: "attached" });
    if (state === "visible" && el && isVisible(el)) return actionResult(true, { changed: true, message: "visible" });
    if (state === "hidden" && (!el || !isVisible(el))) return actionResult(true, { changed: true, message: "hidden" });
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  return actionResult(false, { error_code: "timeout", message: `wait_for timeout (${state})` });
}

function downloadFromLink(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  let anchor = el;
  const tag = String(el.tagName || "").toLowerCase();
  if (tag !== "a") {
    anchor = el.closest ? el.closest("a") : null;
    if (!anchor) return actionResult(false, { error_code: "not_a_link", message: "element is not a link and has no ancestor <a>" });
  }
  const href = String(anchor.href || anchor.getAttribute("href") || "").trim();
  if (!href || href === "#" || href.startsWith("javascript:")) {
    return actionResult(false, { error_code: "no_href", message: "link has no usable href" });
  }
  const absoluteUrl = href.startsWith("http") ? href : new URL(href, location.href).href;
  return actionResult(true, { changed: true, href: absoluteUrl, element: elementMeta(el, newHandle(el)) });
}

function getElementRect(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  let el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  if (NO_CLICK_SELECTORS.some((sel) => el.closest && el.closest(sel))) {
    return actionResult(false, { error_code: "forbidden", message: "element is in header/logo area" });
  }
  const tag = String(el.tagName || "").toLowerCase();
  const role = String(el.getAttribute?.("role") || "").toLowerCase();
  if ((tag === "svg" || tag === "path" || role === "img") && el.closest) {
    const btn = el.closest("button, [role='button']");
    if (btn) el = btn;
  }
  if (NO_CLICK_SELECTORS.some((sel) => el.closest && el.closest(sel))) {
    return actionResult(false, { error_code: "forbidden", message: "element is in header/logo area" });
  }
  el.scrollIntoView({ block: "center", inline: "center", behavior: "auto" });
  const r = el.getBoundingClientRect();
  let offsetX = 0;
  let offsetY = 0;
  try {
    if (typeof window !== "undefined" && window.frameElement) {
      const fr = window.frameElement.getBoundingClientRect();
      offsetX = fr.left;
      offsetY = fr.top;
    }
  } catch (_e) {}
  const x = Math.floor(r.left + r.width / 2 + offsetX);
  const y = Math.floor(r.top + r.height / 2 + offsetY);
  return actionResult(true, { x, y, left: r.left, top: r.top, width: r.width, height: r.height, in_iframe: !!window.frameElement, element: elementMeta(el, newHandle(el)) });
}

function assertAction(payload = {}) {
  const locator = (payload && payload.locator) || payload || {};
  const expectText = String(payload.expect_text || "");
  const expectValue = String(payload.expect_value || "");
  const el = resolveFromLocator(locator);
  if (!el) return actionResult(false, { error_code: "not_found", message: "element not found" });
  const currentText = textOf(el);
  const currentValue = String(el.value ?? "");
  if (expectText && !currentText.includes(expectText)) {
    return actionResult(false, { error_code: "assert_failed", message: "text assert failed", actual: { text: currentText } });
  }
  if (expectValue && currentValue !== expectValue) {
    return actionResult(false, { error_code: "assert_failed", message: "value assert failed", actual: { value: currentValue } });
  }
  return actionResult(true, { changed: false, actual: { text: currentText, value: currentValue } });
}

async function runAction(action, payload) {
  switch (action) {
    case "snapshot":
      return snapshot();
    case "locate":
      return locate(payload);
    case "click":
      return click(payload);
    case "type":
      return type(payload);
    case "hover":
      return hover(payload);
    case "press_key":
      return pressKey(payload);
    case "select_option":
      return selectOption(payload);
    case "get_dropdown_options":
      return getDropdownOptions(payload);
    case "scroll_into_view":
      return scrollIntoViewAction(payload);
    case "wait_for":
      return waitFor(payload);
    case "assert":
      return assertAction(payload);
    case "download_from_link":
      return downloadFromLink(payload);
    case "get_element_rect":
      return getElementRect(payload);
    case "reload_page":
      // 在当前 frame 内执行 location.reload()，避免整页重载导致重定向
      setTimeout(() => location.reload(), 0);
      return actionResult(true, { message: "reload scheduled" });
    default:
      return actionResult(false, { error_code: "unsupported_action", message: `unsupported action: ${action}` });
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.channel !== CHANNEL) return false;
  const action = String(msg.action || "");
  const payload = msg.payload || {};
  Promise.resolve(runAction(action, payload))
    .then((result) => sendResponse(result))
    .catch((err) => {
      sendResponse(actionResult(false, { error_code: "script_exception", message: String(err) }));
    });
  return true;
});
