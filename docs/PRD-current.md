# MyClaw 产品需求文档 (PRD) — 当前版本

> 版本：v5.0 (Current)  
> 日期：2026-02-27  
> 状态：已实现

---

## 1. 产品概述

MyClaw 是一个可扩展的通用 AI Agent 平台，支持通过挂载 Skills 扩展能力，集成 Browser MCP 浏览器自动化，适用于企业内网后台、数据分析、报告生成等场景。

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
| 浏览器自动化 | Browser MCP 扩展 + stdio (npx @browsermcp/mcp) |
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

### 2.3 Browser MCP 浏览器自动化

**能力**：通过 Browser MCP 扩展操作当前浏览器标签页，复用用户已登录会话。

**工具**（启用 Browser MCP 后可用）：

- `browser_navigate` — 导航到 URL
- `browser_snapshot` — 获取页面可访问性快照（含元素 ref）
- `browser_click` — 点击元素
- `browser_type` — 在可编辑元素中输入文本
- `browser_select_option` — 选择下拉选项
- `browser_screenshot` — 截取截图
- `browser_hover` — 悬停元素
- `browser_wait` — 等待指定秒数
- `browser_go_back` / `browser_go_forward` — 前进/后退
- `browser_press_key` — 模拟按键

**技术实现**：

- **连接方式**：stdio 子进程 `npx @browsermcp/mcp`，扩展通过本地 WebSocket 连接
- **客户端**：Python mcp 包 StdioServerParameters + stdio_client + ClientSession

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
- Browser MCP 状态检查
- Skill 发现与加载

---

## 3. 部署与启动

### 3.1 前置条件

- Python 3.10+
- Node.js 18+（Browser MCP 需 npx）
- Chrome 或 Chromium 浏览器（用于浏览器自动化）

### 3.2 一键启动 (Windows)

```batch
start.bat
```

自动完成：环境检查、虚拟环境创建、依赖安装、服务启动。

### 3.3 配置

- **API Key**：`backend/.env` 中配置 `LLM_API_KEY`、`TAVILY_API_KEY`
- **Browser MCP**：前端「MCP 扩展」面板启用，或 `BROWSER_MCP_ENABLED=true`

---

## 4. 项目结构

```
MyClaw/
├── backend/
│   ├── agent/           # Agent 引擎、LLM、Skill 加载
│   ├── api/             # FastAPI 路由、WebSocket
│   ├── config/          # MCP 配置
│   ├── mcp_client/      # Browser MCP stdio 客户端
│   ├── memory/          # 对话记录
│   ├── models/          # Pydantic 模型
│   ├── prompts/        # System Prompt
│   ├── skills/         # Skills 目录
│   ├── tools/          # 内置工具
│   └── main.py
├── frontend/            # React 前端
├── docs/                # 文档
├── start.bat            # 一键启动
└── stop.bat             # 停止服务
```

---

## 5. 已知限制与注意事项

- **Browser MCP**：需安装 Browser MCP 扩展，在目标标签页点击 Connect 后 Agent 才能操作
- **企业内网**：浏览器自动化复用用户登录态，适合需扫码/验证的后台
- **Token 经济**：Skill 采用渐进式披露，按需加载文档以控制上下文长度

---

## 6. 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v2 | 2026-02-22 | Skill 标准化、Prompt/Memory 文件化、执行图 |
| v4 | - | 数据分析 Skills |
| v5 | 2026-02-27 | Browser MCP 集成、stdio 客户端、start.bat 集成 |
