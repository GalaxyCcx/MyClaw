---
name: browser-automation
description: >-
  通过 Chrome 浏览器扩展操作网页。适用于企业内网后台：登录提示、页面读取、
  表单填写、数据下载。需启用 MCP_CHROME_ENABLED 并安装 mcp-chrome 扩展。
metadata:
  author: MyClaw
  version: "1.0.0"
  tags: [browser, chrome, automation, enterprise, form, login]
---

# Browser Automation 浏览器自动化

通过 mcp-chrome 工具操作用户已打开的 Chrome 浏览器。复用现有登录状态，适合企业内网、需扫码登录的后台系统。

## 前置条件

- 已设置 `MCP_CHROME_ENABLED=true`
- 已安装 mcp-chrome 扩展并点击 Connect 启动 bridge
- 用户已在 Chrome 中打开目标页面（或可导航至目标 URL）

## 可用工具

当 MCP Chrome 启用且 bridge 已连接时，以下工具会出现在你的工具列表中，**直接通过 function calling 调用**：

**重要**：若你的工具列表中**没有** `chrome_navigate`、`get_windows_and_tabs` 等，说明 bridge 未就绪。此时应**直接告知用户**「请先在 Chrome 扩展中点击 Connect 启动 bridge」，**禁止**使用 `shell_executor` 或 `python_executor` 通过 curl/socket 等方式尝试连接（bridge 使用 MCP 协议，非简单 HTTP）。

- `get_windows_and_tabs` — 获取当前窗口和标签列表
- `chrome_navigate` — 导航到指定 URL
- `chrome_switch_tab` — 切换活动标签
- `chrome_get_web_content` — 提取当前页面 HTML/文本内容
- `chrome_get_interactive_elements` — 获取可点击元素列表
- `chrome_click_element` — 使用选择器点击元素
- `chrome_fill_or_select` — 填写表单或选择下拉项
- `chrome_screenshot` — 截取页面或元素截图
- `chrome_keyboard` — 模拟键盘输入

## 工作流

### 1. 登录检测与提示

当页面需要登录（如出现登录框、二维码、验证码）时：

1. 使用 `chrome_get_web_content` 或 `chrome_screenshot` 判断当前是否为登录页
2. 若为登录页，**明确告知用户**：「请在浏览器中完成扫码/登录，完成后告诉我继续」
3. 等待用户确认后再继续后续操作

### 2. 页面读取

1. 使用 `chrome_navigate` 打开目标 URL（若尚未打开）
2. 使用 `chrome_get_web_content` 获取页面文本内容
3. 若需定位可操作元素，使用 `chrome_get_interactive_elements`

### 3. 表单填写

1. 使用 `chrome_get_interactive_elements` 获取表单字段
2. 使用 `chrome_fill_or_select` 按字段填写或选择
3. 使用 `chrome_click_element` 点击提交按钮

### 4. 文件下载

- 点击下载链接后，文件会保存到用户 Chrome 的默认下载目录
- 告知用户：「文件已触发下载，请到下载目录查看」

## 注意事项

- 操作的是用户真实 Chrome 会话，请勿在敏感页面执行不可逆操作
- 企业内网可能较慢，适当增加等待或重试
- 若 bridge 未连接，工具调用会失败，提示用户检查扩展和 Connect 状态
- **扩展已显示连接但工具返回 "Failed to connect to MCP server"**：表示 bridge 与扩展的 Native Messaging 连接已断开。请告知用户：在扩展中点击「断开」后重新点击「Connect」，或重启 Chrome。

## 技术参数（供诊断参考）

- **Bridge 端口**：12306（默认）
- **Bridge URL**：http://127.0.0.1:12306/mcp
- **连接检查**：直接调用 `get_windows_and_tabs` 验证即可，勿用 Python/shell 检查端口
