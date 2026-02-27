# MyClaw 产品需求文档 (PRD) — 当前版本

> 版本：v5.0 (Current)  
> 日期：2026-02-27  
> 状态：已实现

---

## 1. 产品概述

MyClaw 是一个可扩展的通用 AI Agent 平台，支持通过挂载 Skills 扩展能力，集成 MCP Chrome 浏览器自动化，适用于企业内网后台、数据分析、报告生成等场景。

### 1.1 核心价值

| 价值 | 说明 |
|------|------|
| **自然语言驱动** | 用户通过对话即可完成复杂任务，无需编写代码 |
| **可插拔 Skills** | 基于 AgentSkills 规范的 SKILL.md 文档挂载，渐进式披露 |
| **浏览器自动化** | 复用 Chrome 登录态，支持企业内网扫码登录、表单填写 |
| **数据分析链路** | DuckDB → Pandas → 报告导出，覆盖从 SQL 到可视化的完整流程 |

### 1.2 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + LangChain + LangGraph + Qwen (阿里云百炼) |
| 前端 | React + Vite + Ant Design + React Flow |
| 浏览器自动化 | mcp-chrome 扩展 + mcp-chrome-bridge (Native Messaging) |
| 搜索 | Tavily API |

---

## 2. 功能模块

### 2.1 对话与 Agent 引擎

- **Chat 界面**：多轮对话，支持 Markdown 渲染
- **实时执行图**：可视化 Agent 推理、工具调用、Loop 循环
- **System Prompt**：Markdown 文件存储 (`backend/prompts/system.md`)，支持在线编辑
- **对话记忆**：持久化至 `backend/memory/conversations/`

### 2.2 内置工具

| 工具 | 说明 |
|------|------|
| `read_file` | 读取本地文件 |
| `write_file` | 写入本地文件 |
| `web_fetch` | 抓取网页内容 |
| `web_search` | Tavily 联网搜索 |
| `python_executor` | 执行 Python 代码 |
| `shell_executor` | 执行 Shell 命令 |
| `read_skill_doc` | 读取 Skill 文档 |
| `read_skill_reference` | 读取 Skill 参考资源 |

### 2.3 MCP Chrome 浏览器自动化

**能力**：通过 Chrome 扩展操作浏览器，复用用户已登录会话。

**工具**（启用 MCP Chrome 后可用）：

- `get_windows_and_tabs` — 获取窗口和标签列表
- `chrome_navigate` — 导航到 URL（支持 `newWindow: true` 在新窗口打开）
- `chrome_switch_tab` — 切换活动标签
- `chrome_get_web_content` — 提取页面内容
- `chrome_get_interactive_elements` — 获取可点击元素
- `chrome_click_element` — 点击元素
- `chrome_fill_or_select` — 填写表单
- `chrome_screenshot` — 截取截图
- `chrome_keyboard` — 模拟键盘输入

**技术实现**：

- **Bridge**：mcp-chrome-bridge，Chrome Native Messaging 协议，端口 12306
- **客户端**：轻量 HTTP 客户端（POST-only），解析 SSE 响应，绕过 Python MCP SDK 的 500/TaskGroup 问题
- **多连接补丁**：`patch-package` 对 mcp-chrome-bridge 打补丁，将 `getMcpServer()` 从单例改为工厂，支持 Cursor + MyClaw 同时连接

### 2.4 Skills 体系

**目录**：`backend/skills/`

| Skill | 说明 |
|-------|------|
| `browser-automation` | 浏览器自动化工作流与注意事项 |
| `data-analysis` | 数据分析方法论与流程 |
| `duckdb-analysis` | DuckDB SQL 预筛选 |
| `pandas-analysis` | Pandas 数据处理与可视化 |
| `report-export` | HTML 报告导出 |
| `datetime-skill` | 日期时间处理 |
| `deep-research` | 深度调研流程 |

**格式**：遵循 AgentSkills 规范，`SKILL.md` 含 YAML frontmatter + Markdown 指令。

### 2.5 初始化任务 (Init Jobs)

启动时在 Graph 面板展示：

- LLM 连接检查
- MCP Chrome Bridge 状态检查
- Skill 发现与加载

---

## 3. 部署与启动

### 3.1 前置条件

- Python 3.10+
- Node.js 18+（MCP Chrome 需 Node.js 20+）
- Chrome 或 Chromium 浏览器（用于浏览器自动化）

### 3.2 一键启动 (Windows)

```batch
start.bat
```

自动完成：环境检查、虚拟环境创建、依赖安装、patch 应用、bridge 注册、服务启动。

### 3.3 配置

- **API Key**：`backend/.env` 中配置 `LLM_API_KEY`、`TAVILY_API_KEY`
- **MCP Chrome**：前端「MCP 扩展」面板启用，或 `MCP_CHROME_ENABLED=true`

---

## 4. 项目结构

```
MyClaw/
├── backend/
│   ├── agent/           # Agent 引擎、LLM、Skill 加载
│   ├── api/             # FastAPI 路由、WebSocket
│   ├── config/          # MCP 配置
│   ├── mcp_client/      # MCP Chrome HTTP 客户端
│   ├── memory/          # 对话记录
│   ├── models/          # Pydantic 模型
│   ├── prompts/        # System Prompt
│   ├── skills/         # Skills 目录
│   ├── tools/          # 内置工具
│   ├── patches/        # patch-package 补丁
│   └── main.py
├── frontend/            # React 前端
├── docs/                # 文档
├── start.bat            # 一键启动
└── stop.bat             # 停止服务
```

---

## 5. 已知限制与注意事项

- **MCP Chrome**：bridge 由 Chrome 扩展点击 Connect 时启动，需先安装 mcp-chrome 扩展
- **企业内网**：浏览器自动化复用用户登录态，适合需扫码/验证的后台
- **Token 经济**：Skill 采用渐进式披露，按需加载文档以控制上下文长度

---

## 6. 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v2 | 2026-02-22 | Skill 标准化、Prompt/Memory 文件化、执行图 |
| v4 | - | 数据分析 Skills |
| v5 | 2026-02-27 | MCP Chrome 集成、HTTP 客户端、多连接补丁、start.bat 集成 |
