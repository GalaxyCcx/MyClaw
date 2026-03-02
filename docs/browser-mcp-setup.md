# Browser MCP 安装与配置

Browser MCP 使 MyClaw Agent 能够通过 Chrome 扩展操作当前浏览器标签页，复用用户已登录的会话，适合企业内网后台自动化。

## 前置条件

- Node.js >= 18（用于 `npx @browsermcp/mcp`）
- Chrome 或 Chromium 浏览器

## 安装步骤

### 1. 安装 Chrome 扩展

1. 打开 [Chrome 网上应用店 - Browser MCP](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)
2. 点击「添加至 Chrome」安装扩展
3. 在 Chrome 工具栏中固定扩展图标便于使用

### 2. 配置 MyClaw

**方式一（推荐）**：使用 `start.bat` 启动时，Browser MCP 会自动启用。

**方式二**：在前端右侧「MCP 扩展」面板中直接启用 Browser MCP 开关。

**方式三**：在 `backend/.env` 中设置：

```
BROWSER_MCP_ENABLED=true
BROWSER_MCP_TIMEOUT=60
```

如需接入本地改造版 Browser MCP（方案 B），可额外设置：

```
BROWSER_MCP_COMMAND=npx
BROWSER_MCP_ARGS=-y @browsermcp/mcp@latest
# 或使用 JSON 形式（优先级更高）
# BROWSER_MCP_ARGS_JSON=["-y","@browsermcp/mcp@latest"]
```

前端开关会覆盖 .env 设置并持久化到 `backend/config/mcp.json`。

### 3. 连接扩展

1. 在 Chrome 中打开要操作的页面（或空白页）
2. 点击 Browser MCP 扩展图标
3. 点击「Connect」将当前标签页连接到 MCP 服务

**重要**：MyClaw 后端通过 stdio 启动 `npx @browsermcp/mcp` 子进程，扩展会连接到该进程。必须在目标标签页点击 Connect 后，Agent 才能操作该页面。

## 企业内网使用

1. 在 Chrome 中打开企业后台登录页
2. 按企业要求完成扫码或账号登录
3. 登录成功后，在目标页面点击扩展的 Connect
4. 在 MyClaw 中发起任务，Agent 会复用当前 Chrome 会话进行操作

若检测到需要重新登录，Agent 会提示「请在浏览器中完成扫码登录」。

## 常见问题

### 工具调用失败：扩展未连接

- 确认已在目标标签页点击扩展的 Connect
- 若切换了标签页，需在新标签页重新点击 Connect
- **诊断**：访问 `http://localhost:8000/api/mcp/browser/status` 查看 tools_loaded、tool_count

### 扩展显示已连接但工具返回错误

1. 在扩展中点击「断开」
2. 重新点击「Connect」
3. 若仍失败，重启 Chrome 后再试

### 我安装的是应用商店扩展，如何改造？

应用商店安装包不能直接在线修改。若要实现“新开页面自动接管”等深度能力，建议：

1. 获取 Browser MCP 扩展源码（fork 到你自己的仓库）。
2. 在 Chrome 打开 `chrome://extensions`，启用开发者模式。
3. 选择“加载已解压的扩展”，加载你本地编译后的扩展目录。
4. 禁用商店版扩展，避免两个同类扩展冲突。
5. 让后端通过 `BROWSER_MCP_COMMAND/BROWSER_MCP_ARGS` 指向你本地改造版服务（如自定义 npm 包或本地 node 启动脚本）。

### 一键生成“开发者补丁版扩展”（推荐）

项目已提供脚本：`scripts/prepare_browsermcp_patched_extension.py`  
作用：从你本机已安装的 Browser MCP 商店扩展目录复制一份“开发者版副本”，并注入“新开 tab 自动接管”补丁。

执行：

```bash
python scripts/prepare_browsermcp_patched_extension.py
```

默认输出目录：

`output/browsermcp-extension-patched`

然后在 Chrome 中：

1. 打开 `chrome://extensions`
2. 开启“开发者模式”
3. 禁用商店版 Browser MCP 扩展
4. 点击“加载已解压的扩展程序”，选择 `output/browsermcp-extension-patched`

说明：

- 该补丁通过监听 `webNavigation.onCreatedNavigationTarget`，当新 tab 来源于当前已连接 tab 时，自动切换控制目标到新 tab。
- 这是本地补丁，不依赖重新打包商店扩展。

### BROWSER_MCP_ENABLED 已设置但无浏览器工具

- 查看后端日志，确认是否有「Loaded N Browser MCP tools」
- 若出现「Browser MCP tools not available」，说明扩展未 Connect，请先在目标标签页点击 Connect

### 未找到 npx

- 安装 Node.js（https://nodejs.org/），确保 `npx` 在 PATH 中
- Windows 下可运行 `where npx` 验证

## 技术说明

- **连接方式**：MyClaw 后端以 stdio 方式启动 `npx @browsermcp/mcp`，扩展通过本地 WebSocket 连接该进程
- **单标签**：Browser MCP 仅操作当前 Connect 的标签页，不支持多标签切换
- **无外网依赖**：全部为 localhost 通信，适合内网部署
