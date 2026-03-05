# PRD：Alpha BI 下拉选项选择

> 版本：1.0  
> 日期：2026-03-03  
> 状态：已完成

---

## 1. 背景

Alpha BI 报表页使用 Ant Design 的 `ant-select` 组件实现筛选下拉（品类组、聚合维度、大区、城市等），而非原生 `<select>`。现有 `select_option` 动作仅支持原生 `<select>`，无法直接操作 ant-select。

需要实现「点击展开 → 扩展读取选项列表 → Python job 根据目标值匹配并点击」的完整链路，使 Agent 能自动完成「将品类组设为 X」等任务。

---

## 2. 用户故事

| 场景 | 用户期望 |
|------|----------|
| 单选下拉 | 用户指定「将品类组设为 全品类」时，系统自动完成展开、选择、校验 |
| 筛选组合 | 用户指定多个筛选条件时，系统能依次完成各下拉选择，再点击查询 |

---

## 3. 功能需求

### 3.1 扩展动作 `get_dropdown_options`

- **触发时机**：下拉已展开（用户或 job 已点击 ant-select 触发器）
- **输入**：可选 `locator` 限定在某个 dropdown 容器
- **输出**：`{ ok, options: [{ handle, text, value }] }`，`handle` 用于后续 `click`
- **错误**：无可见 dropdown 时返回 `dropdown_not_visible`

### 3.2 Python Job `select-dropdown`

- **输入**：`trigger_locator`（下拉触发器）、`target_value`（目标选项文本）
- **流程**：navigate（可选）→ click(触发器) → wait(350ms) → get_dropdown_options → 匹配 → click(handle) → wait(200ms) → snapshot 校验
- **输出**：`{ ok, matched_option, actions_log }`

### 3.3 选项匹配

- 优先精确匹配（`text == target_value`）
- 其次包含匹配（`target_value in text`）
- 无匹配时返回 `ok=false`、`options` 列表，便于调试

---

## 4. 非功能需求

- 选项匹配支持精确/包含
- 失败时返回 options 列表便于调试
- 与现有 `single-select.md` 流程兼容

---

## 5. 验收标准

- **扩展**：在 Alpha BI 页面展开任意 ant-select 下拉后，`get_dropdown_options` 返回非空 options，且每项含 `handle`、`text`
- **Job**：给定有效 `trigger_locator` 和 `target_value`，job 返回 `ok=true`，且页面展示值等于目标
- **失败场景**：`target_value` 不存在时，返回 `ok=false`、`options` 列表

---

## 6. 范围与后续

- 本期：单选下拉
- 后续：多选下拉（复用 get_dropdown_options，多次点击）
