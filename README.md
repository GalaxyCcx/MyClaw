# MyClaw

一个可扩展的通用 AI Agent 平台，支持通过挂载 Skills 扩展能力。

## 特性

- **自然语言对话** — 通过 Chat 界面与 Agent 交互
- **实时执行图** — 可视化 Agent 的推理和工具调用流程
- **可插拔 Skills** — 通过 SKILL.md 文档挂载新能力，无需编写代码
- **内置工具** — 文件读写、网页抓取、联网搜索、Python/Shell 执行器
- **Prompt 管理** — System Prompt 以 Markdown 文件存储，支持在线编辑

## 前置条件

- Python 3.10+
- Node.js 18+
- npm 9+

## 快速开始

### 一键启动（推荐）

Windows 下双击项目根目录的 `start.bat`，脚本会自动完成以下工作：

1. 检查 Python 和 Node.js 环境
2. 创建 Python 虚拟环境（如不存在）
3. 安装所有后端和前端依赖（首次运行）
4. 启动后端和前端服务
5. 自动打开浏览器

停止服务：双击 `stop.bat` 或关闭两个弹出的终端窗口。

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

### 手动安装

如果不使用一键启动脚本：

```bash
# 后端
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

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
# Windows
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
# Linux/macOS
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端（新终端）
cd frontend
npm run dev
```

访问 http://localhost:5173 即可使用。

## 项目结构

```
myclaw/
├── backend/
│   ├── agent/          # Agent 核心逻辑（引擎、LLM、技能加载）
│   ├── api/            # FastAPI 路由（WebSocket、REST）
│   ├── memory/         # 对话记录持久化
│   ├── models/         # Pydantic 数据模型
│   ├── prompts/        # System Prompt (Markdown)
│   ├── skills/         # 可插拔 Skills 目录
│   ├── tools/          # 内置工具（read_file, web_fetch, python_executor 等）
│   ├── main.py         # FastAPI 应用入口
│   ├── requirements.txt
│   └── requirements-skills.txt
├── frontend/
│   └── src/
│       ├── components/ # React 组件（Chat、Graph、NodeDetail 等）
│       ├── hooks/      # 自定义 Hooks（WebSocket、Graph 状态）
│       ├── styles/     # 样式文件
│       └── types/      # TypeScript 类型定义
├── docs/               # PRD 文档
└── scripts/            # 安装脚本
```

## Skills 开发

Skills 采用纯文档型架构：

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
- **搜索**: Tavily API
