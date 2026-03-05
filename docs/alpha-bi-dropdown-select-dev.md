# Alpha BI 下拉选项选择 — 开发文档

## 1. 概述

实现 Ant Design 下拉（ant-select）的自动化选择：点击展开 → 扩展读取选项 → Python job 匹配并点击。

## 2. Ant Design 下拉 DOM 结构

| 选择器 | 说明 |
|--------|------|
| `.ant-select-dropdown` | 下拉容器（挂载在 body 下） |
| `.ant-select-item` | 选项项（Ant Design v4+） |
| `.ant-select-dropdown-menu-item` | 兼容旧版选项项 |

## 3. 扩展 `get_dropdown_options` 接口

### 3.1 Payload

```json
{
  "locator": {
    "selector": ".ant-select-dropdown",
    "index": 0
  }
}
```

- `locator` 可选：不传时取第一个可见的 `.ant-select-dropdown`

### 3.2 返回值

```json
{
  "ok": true,
  "options": [
    { "handle": "e123", "text": "全品类", "value": "" },
    { "handle": "e124", "text": "品类A", "value": "a" }
  ]
}
```

### 3.3 错误码

| 错误码 | 说明 |
|--------|------|
| `dropdown_not_visible` | 无可见 dropdown |
| `dropdown_not_found` | 未找到 dropdown 元素 |

## 4. Python Job 请求/响应

### 4.1 Request

```json
{
  "url": "https://alpha-bi.ddxq.mobi/report?...",
  "wait_after_navigate_ms": 3000,
  "trigger_locator": {
    "selector": ".ant-select",
    "text": "品类组",
    "before": { "selector": "text:一、核心指标" }
  },
  "target_value": "全品类"
}
```

### 4.2 Response (成功)

```json
{
  "ok": true,
  "matched_option": { "handle": "e123", "text": "全品类", "value": "" },
  "actions_log": [...]
}
```

### 4.3 Response (失败)

```json
{
  "ok": false,
  "error": "option_not_found",
  "options": [{ "handle": "e123", "text": "品类A" }, ...],
  "actions_log": [...]
}
```

## 5. 与 single-select.md 的对应关系

- 原流程：`snapshot` → 取 elements 中的 option ref → click
- 新流程：`get_dropdown_options` → 取 options 中的 handle → click
- 当扩展支持 `get_dropdown_options` 时，优先使用新流程（v2 snapshot 不返回 elements）

## 6. 已知限制

- 多个 ant-select-dropdown 同时存在时，默认取第一个可见的
- 虚拟列表导致选项未渲染时，需额外滚动或键盘方案
- handle 需在展开后尽快使用，DOM 变化可能导致过期
