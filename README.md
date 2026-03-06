# MyClaw

[![GitHub](https://img.shields.io/badge/GitHub-GalaxyCcx%2FMyClaw-blue)](https://github.com/GalaxyCcx/MyClaw)

一个可扩展的通用 AI Agent 平台，支持通过挂载 Skills 扩展能力，集成 MyClaw Browser Agent V3 浏览器自动化。

## 特性

- **自然语言对话** — 通过 Chat 界面与 Agent 交互
- **实时执行图** — 可视化 Agent 的推理和工具调用流程
- **可插拔 Skills** — 基于 AgentSkills 规范的 SKILL.md 文档挂载，渐进式披露
- **内置工具** — 文件读写、网页抓取、联网搜索、Python/Shell 执行器
- **Browser Agent V3** — 浏览器自动化，复用用户登录态，适合企业内网后台
- **数据分析链路** — DuckDB、Pandas、报告导出等 Skills

## 前置条件

- Python 3.10+
- Node.js 18+
- Chrome 或 Chromium（用于浏览器自动化）

## 快速开始

### 一键启动（推荐）

Windows 下双击项目根目录的 `start.bat`，脚本会自动完成：

1. 检查 Python 和 Node.js 环境
2. 创建 Python 虚拟环境（如不存在）
3. 安装后端、前端依赖
4. 启动后端和前端服务
5. 自动打开浏览器

停止服务：双击 `stop.bat` 或关闭弹出的终端窗口。

### 配置

首次使用前，复制并编辑后端环境变量：

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

需要配置的 Key：

- `LLM_API_KEY` — 阿里云百炼 API Key（[获取地址](https://bailian.console.aliyun.com/)）
- `TAVILY_API_KEY` — Tavily 搜索 API Key（[获取地址](https://tavily.com/)）

### Browser Agent V3 浏览器自动化（可选）

1. 在 `extensions/myclaw-browser-agent-v3` 加载本地扩展（开发者模式）
2. 保持后端运行并打开目标页面
3. 扩展会自动连接 `ws://127.0.0.1:8000/ws/browser-gateway`

### 手动安装

```bash
# 后端
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-skills.txt
# 前端
cd ../frontend
npm install

```

### 手动启动

```bash
# 后端
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 25 --ws-ping-timeout 300

# 前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173 即可使用。

## 项目结构

```
MyClaw/
├── backend/
│   ├── agent/          # Agent 核心逻辑（引擎、LLM、技能加载）
│   ├── api/            # FastAPI 路由（WebSocket、REST）
│   ├── memory/         # 对话记录持久化
│   ├── models/         # Pydantic 数据模型
│   ├── prompts/        # System Prompt (Markdown)
│   ├── skills/         # 可插拔 Skills 目录
│   ├── tools/          # 内置工具
│   └── main.py
├── frontend/           # React + Vite + Ant Design + React Flow
├── docs/               # 文档（PRD、browser-mcp-setup 等）
├── start.bat           # 一键启动（Windows）
└── stop.bat            # 停止服务
```

## Skills 开发

Skills 采用纯文档型架构，遵循 [AgentSkills 规范](https://agentskills.io/specification)：

1. 在 `backend/skills/` 下创建目录（如 `my-skill/`）
2. 编写 `SKILL.md`，包含 YAML frontmatter（name、description）和详细文档
3. Agent 通过 `read_skill_doc` 读取文档，然后使用 `shell_executor` 或 `python_executor` 执行操作

示例 SKILL.md 结构：

```markdown
---
name: my-skill
description: 一句话描述 skill 的能力
metadata:
  version: "1.0"
  tags: [tag1, tag2]
---

# My Skill

详细使用说明和代码模板...
```

## 技术栈

- **后端**: FastAPI + LangChain + LangGraph + Qwen (阿里云百炼)
- **前端**: React + Vite + Ant Design + React Flow
- **浏览器自动化**: MyClaw Browser Agent V3 + WebSocket
- **搜索**: Tavily API

## 文档

- [PRD 当前版本](docs/PRD-current.md)
- [Skills 框架设计](docs/skills-framework-agent-design.md)

## AlphaBI 本地调试文件

AlphaBI 相关的本地调试截图、临时计划文件、下载结果等运行产物默认不纳入版本控制。  
请参考项目根目录 `.gitignore` 中 `AlphaBI local artifacts` 段落。
