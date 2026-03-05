---
name: browser-automation
description: >-
  通过原生浏览器扩展通道（native_extension）操作当前浏览器标签页。适用于企业内网后台：
  登录提示、页面读取、表单填写、数据下载。
metadata:
  author: MyClaw
  version: "2.1.0"
  tags: [browser, automation, enterprise, form, login]
---

# Browser Automation 浏览器自动化

通过原生浏览器工具操作用户已附着的 Chrome 标签页。复用现有登录状态，适合企业内网、需扫码登录的后台系统。

## 前置条件

- 已设置 `BROWSER_TRANSPORT=native_extension`
- 已安装并加载 `myclaw-browser-agent` 扩展
- 扩展通道状态为已连接（`/api/browser/channel/status` 显示 `connected=true`）

## 强制规则

1. **必须直接调用浏览器工具**：若工具列表中有 `browser_navigate`、`browser_click` 等，必须直接调用。**禁止**使用 `shell_executor` 或 `python_executor` 模拟调用。
2. **连接失败处理**：工具返回“浏览器通道未连接/目标标签页不可用”时，告知用户检查扩展是否已加载、后端是否运行、并刷新页面后重试。
3. **二级页面优先同 tab 打开**：若可提取目标链接 URL，优先在当前已连接 tab 使用 `browser_navigate` 跳转，避免点击后新开 tab 导致连接丢失。
4. **跳转后必须校验状态**：执行跳转动作后，必须用页面标题/关键字段校验是否已进入目标页面，校验失败禁止继续下一步。
5. **禁止无限重试**：同一跳转动作最多尝试 2 次；超限后必须进入重连或改道流程。
6. **检测新窗口信号并优先改道**：当元素存在“新窗口/新标签页”信号（如 target="_blank"、新窗口图标、window.open 行为）时，优先提取 URL 后 `browser_navigate`；若无法提取 URL，允许一次点击探测并立即校验连接状态。
7. **下载任务必须本地落盘校验**：仅“点击下载成功”或“任务中心状态已成功”不算完成，必须验证本地下载目录出现目标文件后才可宣布成功。
8. **下载失败必须收集证据**：若下载未落盘，必须补采浏览器控制台日志与页面状态，再给出失败原因与下一步建议。
9. **同名元素禁止模糊点击**：`browser_click(text=...)` 若返回 `ambiguous text match`，必须先 `browser_snapshot` 选定目标 `ref` 后再点击。
10. **输入必须值校验**：`browser_type` 后必须验证返回中的 `after` 与预期一致；若出现 `typed value mismatch`，判定失败并切换策略。
11. **截图严禁回传大体积内容**：截图仅用于人工取证，不得把 base64 内容继续喂给模型上下文。

## 元素定位（重要）

- **优先用 ref**：先调用 `browser_snapshot` 获取页面可访问性快照（含元素 ref），再用 `browser_click`、`browser_type` 的 `ref` 参数定位。
- `browser_snapshot` 返回的 ref 用于后续 `browser_click`、`browser_type`、`browser_select_option` 等。
- 当页面存在多个同名按钮（如“查询”）时，禁止直接按 `text` 点击；必须结合区块锚点 + `ref` 精确定位。

## 动作后强校验（新增）

每个高风险动作后必须执行可见结果校验：

1. **填值动作**：检查 `browser_type` 结果中的 `before/after`，并确认 `after == 期望值`。
2. **点击查询/提交**：执行 `browser_wait(1000~2000ms)` 后 `browser_snapshot`，校验关键字段变化（如日期值、结果条数、核心指标）。
3. **校验失败**：禁止继续后续步骤，需切换到备用路径（重新定位 ref、键盘兜底、或提示用户确认页面状态）。

## 能力边界

- **单标签优先**：原生通道默认操作当前附着标签页。若需切到其他页面，优先使用 `browser_navigate` 到目标 URL，避免依赖手工切换。

## 二级页面与新开 Tab 兼容流程（关键）

当点击“详情/钻取/查看明细”等操作可能打开二级页面时，按以下固定流程执行：

1. 先 snapshot 定位触发元素，并尝试识别其目标 URL（如链接文本、href）。
2. 若能拿到 URL：优先 `browser_navigate(url=...)` 在当前已连接 tab 打开目标页。
3. 若拿不到 URL：执行一次 `browser_click`，随后立即 snapshot 校验是否已进入目标页。
4. 若出现“目标标签页不可用/通道未连接”：判定为新开 tab 或通道漂移，先执行通道恢复，再校验目标页锚点。
5. 用户确认后，先 snapshot 校验“当前页是否目标页”；命中后再继续后续步骤。
6. 若重连后仍未进入目标页，回到父页并改走“提取 URL + browser_navigate”路径，不继续盲点。

## 下载页跳转（防新窗口）

下载中心/导出页常通过新窗口打开。请使用以下固定策略：

1. 在父页定位“下载/导出/明细”入口后，优先识别目标 URL。
2. 识别到 URL 时，使用 `browser_navigate` 在当前已连接 tab 打开下载页。
3. 若只能点击，允许 1 次点击探测；点击后立即校验通道状态，出现“目标标签页不可用”时停止后续点击并进入恢复流程。
4. 重连后先校验“是否已在下载页”，再执行下载动作。

## 效率与上下文控制

工具返回内容会占用模型上下文，过多或过大会导致任务失败。请严格遵循：

1. **搜索类任务**：优先用 `browser_navigate` 直接打开搜索 URL（如 `https://www.baidu.com/s?wd=关键词`），避免先打开首页再 fill/click。
2. **页面内容**：`browser_snapshot` 仅取必要模式（默认 summary）；只在定位或校验时调用，避免连续 full snapshot。
3. **失败重试**：同一操作连续失败 2 次后，换方案或明确告知用户，避免反复重试。
4. **任务完成**：获得所需结果后立即总结回复用户，不要额外验证或重复操作。
5. **证据最小化**：优先使用结构化结果（`title/url/elements/ref`）；截图仅在失败取证时使用。
6. **多步任务优先批量执行**：当步骤可提前确定时，优先使用 `browser_run_plan` 一次执行多步，减少“逐步调用 + 逐步等待”的往返开销。

## 可用工具

当原生浏览器通道已连接时，以下工具会出现在你的工具列表中，**直接通过 function calling 调用**：

**重要**：若你的工具列表中**没有** `browser_navigate`、`browser_click` 等，说明浏览器通道未就绪。此时应直接告知用户检查扩展加载与后端状态接口。

- `browser_navigate` — 导航到指定 URL
- `browser_snapshot` — 获取页面可访问性快照（含元素 ref），**优先用于定位**
- `browser_click` — 点击元素（使用 ref 或 element 参数）
- `browser_type` — 在可编辑元素中输入文本
- `browser_select_option` — 选择下拉选项
- `browser_run_plan` — 批量执行多个浏览器步骤（推荐用于固定流程）
- `browser_screenshot` — 截取当前页面截图
- `browser_hover` — 悬停元素
- `browser_wait` — 等待指定秒数
- `browser_go_back` — 后退
- `browser_go_forward` — 前进
- `browser_press_key` — 模拟按键

## 工作流

### 1. 登录检测与提示

当页面需要登录（如出现登录框、二维码、验证码）时：

1. 使用 `browser_snapshot` 或 `browser_screenshot` 判断当前是否为登录页
2. 若为登录页，**明确告知用户**：「请在浏览器中完成扫码/登录，完成后告诉我继续」
3. 等待用户确认后再继续后续操作

### 2. 页面读取与操作

1. 使用 `browser_navigate` 打开目标 URL（若尚未打开）
2. **优先**使用 `browser_snapshot` 获取页面结构，找到目标元素的 ref
3. 使用 `browser_click` 的 `ref` 点击，或 `browser_type` 的 `ref` 填写
4. 对 `type/select` 立即校验返回值；出现 mismatch 立刻失败并改道

### 3. 表单填写

1. 使用 `browser_snapshot` 获取页面结构，找到目标输入框、按钮的 ref
2. 使用 `browser_type` 的 ref 参数按字段填写
3. 下拉选择使用 `browser_select_option`
4. 提交按钮使用 `browser_click`
5. 提交后必须做“字段值 + 结果区”双校验，未变化不得宣告成功

### 4. 文件下载

- 点击下载链接后，不得立即宣布成功。
- 必须执行“页面侧 + 本地侧”双重校验：
  1. 页面侧：任务中心状态为“已成功”，且下载动作已触发。
  2. 本地侧：通过本地检查确认文件已落盘（文件名命中、修改时间在本次任务窗口内）。
- 仅当双重校验通过，才可输出“下载成功”。
- 若仅完成触发、未完成本地落盘校验，必须明确输出“已触发下载，待本地确认”。

### 下载落盘校验模板（建议）

1. 记录下载前时间戳 `t0`。
2. 点击下载后等待短时间（如 1~3 秒）并轮询下载目录。
3. 校验条件：
   - 文件名包含任务关键字（如报表名/任务名）；
   - 文件 `mtime >= t0`；
   - 文件大小大于 0（可选）。
4. 超时未命中（如 30~60 秒）则判定“下载未确认”，进入异常流程。

推荐工具调用：

- `check_download_file(keyword=..., timeout_seconds=..., modified_within_seconds=...)`
- `browser_get_console_logs()`（下载失败时）

## 注意事项

- 操作的是用户真实 Chrome 会话，请勿在敏感页面执行不可逆操作
- 企业内网可能较慢，适当增加 `browser_wait` 或重试
- 若浏览器通道未连接，工具调用会失败，提示用户检查扩展加载状态与 `/api/browser/channel/status`
- **工具结果截断**：大体积工具（如 `browser_snapshot`）返回可能被截断。完整内容会保存至 `backend/memory/tool_outputs/`，可用 `read_file(path)` 查看。
