# mcp-chrome 安装与配置

mcp-chrome 使 MyClaw Agent 能够通过 Chrome 扩展操作浏览器，复用用户已登录的会话，适合企业内网后台自动化。

## 前置条件

- Node.js >= 20
- Chrome 或 Chromium 浏览器

## 安装步骤

### 1. 安装 mcp-chrome-bridge（推荐：项目内自动管理）

使用 `start.bat` 启动时，会自动在 `backend/` 下安装 mcp-chrome-bridge 并注册到 Chrome，**无需全局安装**。

bridge 采用 Chrome Native Messaging 协议：**由 Chrome 在扩展点击 Connect 时自动启动**，无需单独运行进程。

如需手动安装与注册：

```bash
cd backend
npm install
npx mcp-chrome-bridge register --detect
```

或全局安装（可选）：

```bash
npm install -g mcp-chrome-bridge
```

### 2. 安装 Chrome 扩展

1. 打开 [mcp-chrome releases](https://github.com/hangwin/mcp-chrome/releases)
2. 下载最新版本的扩展 zip 并解压
3. 打开 Chrome，访问 `chrome://extensions/`
4. 开启「开发者模式」
5. 点击「加载已解压的扩展程序」，选择解压后的扩展目录

### 3. 启动 Bridge

bridge 由 **Chrome 在扩展连接时自动启动**，无需单独运行。

1. 点击 Chrome 工具栏中的 mcp-chrome 扩展图标
2. 点击「Connect」按钮
3. Chrome 会启动 bridge 进程，扩展显示端口 12306（或自定义端口）

### 4. 配置 MyClaw

**方式一（推荐）**：使用 `start.bat` 启动时，MCP Chrome 会自动启用。

**方式二**：在前端右侧「MCP 扩展」面板中直接启用/禁用 MCP Chrome 开关。

**方式三**：在 `backend/.env` 中设置：

```
MCP_CHROME_ENABLED=true
MCP_CHROME_URL=http://127.0.0.1:12306/mcp
MCP_CHROME_TIMEOUT=60
```

MyClaw 默认使用轻量 HTTP 客户端（POST-only），避免 Python MCP SDK 的 500/TaskGroup 问题。若需回退到 SDK，可设置 `MCP_CHROME_USE_SDK=true`。

项目通过 `patch-package` 对 mcp-chrome-bridge 打补丁，支持多客户端同时连接（如 Cursor + MyClaw）。首次 `npm install` 后若遇连接问题，请在扩展中「断开」后重新「Connect」以重启 bridge。

前端开关会覆盖 .env 设置并持久化到 `backend/config/mcp.json`。

### 5. 安装 Python 依赖

```bash
cd backend
pip install -r requirements.txt
```

## 企业内网使用

1. 在 Chrome 中打开企业后台登录页
2. 按企业要求完成扫码或账号登录
3. 登录成功后，在 MyClaw 中发起任务
4. Agent 会复用当前 Chrome 会话进行操作

若检测到需要重新登录，Agent 会提示「请在浏览器中完成扫码登录」。

## 常见问题

### 工具调用失败：无法连接 mcp-chrome-bridge

- 确认扩展已加载且点击了 Connect（Chrome 会在此刻启动 bridge）
- 若首次使用，`start.bat` 会自动执行 `mcp-chrome-bridge register --detect`；若失败可手动运行：`cd backend && npx mcp-chrome-bridge register --detect`
- 检查端口 12306 是否被占用
- **诊断**：访问 `http://localhost:8000/api/mcp/chrome/status` 查看 bridge 连接状态（http_reachable、tools_loaded）

### 扩展显示已连接但工具返回 "Failed to connect to MCP server"

表示 bridge 与扩展的 Native Messaging 连接已断开（扩展 UI 可能未同步）：
1. 在扩展中点击「断开」
2. 重新点击「Connect」
3. 若仍失败，重启 Chrome 后再试

### 返回 500 "Already connected to a transport"

表示 bridge 的 MCP 服务端仅允许单连接，而 Cursor 或其他客户端已占用。项目已通过 patch 修复此问题：
1. 确认 `backend/patches/mcp-chrome-bridge+1.0.31.patch` 存在
2. 运行 `cd backend && npm install` 确保补丁已应用
3. 在扩展中「断开」后重新「Connect」以重启 bridge 加载新代码

### MCP_CHROME_ENABLED 已设置但无浏览器工具

- 查看后端日志，确认是否有「Loaded N MCP Chrome tools」
- 若出现「MCP Chrome tools not available」，说明 bridge 未就绪，请先启动扩展并 Connect

### 企业网络限制

mcp-chrome 全部为 localhost 通信，无外网依赖，适合内网部署。
