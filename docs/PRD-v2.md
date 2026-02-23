# MyClaw V2 — 可视化 + AgentSkills 标准化 产品需求文档 (PRD)

> 版本：v2.0  
> 日期：2026-02-22  
> 状态：草案  
> 基线：基于 V1 (Phase 1-3 已验收) 进行迭代

---

## 1. 版本概述

### 1.1 迭代目标

V2 围绕三个核心目标进行迭代：

| # | 目标 | 动机 |
|---|------|------|
| G1 | **Skill 结构标准化** | 当前使用自研 `skill.yaml` 格式，不符合行业标准。迁移至 AgentSkills 规范（`SKILL.md`），支持渐进式披露 |
| G2 | **Prompt / Memory 文件化** | 系统提示词硬编码在 Python 中，对话记录仅保存在内存。改为 Markdown 文件存储，人类可读可编辑 |
| G3 | **Agent 执行可视化** | 前端仅有 Chat 时间线，无法直观观察 Agent 内部逻辑流转。新增实时执行图（Graph），显示初始化 Job、节点执行、Loop 循环、Prompt/Messages 快照 |

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **规范优先** | Skill 格式严格遵循 [AgentSkills 规范](https://agentskills.io/specification)，与 Anthropic Claude Skills、OpenClaw 生态兼容 |
| **渐进式披露** | 三层信息架构：Metadata → Instructions → Resources，最小化启动时上下文占用 |
| **文件即真相** | 系统提示词、对话记录、Skill 文档均以 Markdown 文件存储，版本可控、人类可读 |
| **向后兼容** | V1 的全部功能（对话、工具调用、链路可视化）保持不变，V2 为增量改进 |

---

## 2. 术语定义

| 术语 | 定义 |
|------|------|
| **AgentSkills 规范** | 由 Anthropic 主导的开放 Skill 标准（[agentskills.io](https://agentskills.io)），定义 `SKILL.md` 文件格式和目录结构 |
| **SKILL.md** | Skill 的核心定义文件，YAML frontmatter（元数据）+ Markdown body（指令文档） |
| **渐进式披露** | Progressive Disclosure — 分层加载信息：启动时仅加载 ~100 token 元数据，激活时加载指令（<5000 token），运行时按需加载资源文件 |
| **Discovery** | 启动时扫描 Skill 目录、解析 frontmatter `name` + `description` 的过程 |
| **Activation** | 导入 Skill 的 Python 工具函数、注册到 Agent 的过程 |
| **Init Job** | 应用启动阶段执行的初始化任务（加载配置、检查 LLM 连接、发现 Skill 等） |
| **Execution Graph** | 前端实时渲染的有向图，可视化 Agent 单次对话的完整执行路径 |
| **Node** | 执行图中的一个节点，可以是 LLM 调用、Tool 执行、用户输入或最终回答 |

---

## 3. Skill 结构标准化（F-10）

### 3.1 规范遵从

MyClaw V2 的 Skill 格式遵循 **AgentSkills 规范 v1**（[agentskills.io/specification](https://agentskills.io/specification)）。

**核心规则**：

| 规则 | 说明 |
|------|------|
| 必需文件 | 每个 Skill 目录必须包含 `SKILL.md` |
| 目录名 = name | `SKILL.md` frontmatter 中的 `name` 必须与父目录名一致 |
| name 格式 | 1-64 字符，仅小写字母、数字、连字符，不能以 `-` 开头或结尾，不能连续 `--` |
| description 格式 | 1-1024 字符，非空，描述 Skill 做什么以及何时使用 |
| frontmatter 字段 | `name`（必需）、`description`（必需）、`license`（可选）、`compatibility`（可选）、`metadata`（可选） |

### 3.2 目录结构

```
backend/skills/
└── datetime-skill/              # 目录名 = skill name
    ├── SKILL.md                 # 必需：元数据 + 指令文档
    ├── scripts/                 # 可选：可执行脚本
    │   └── tools.py             #   @tool 装饰的 Python 工具函数
    ├── references/              # 可选：参考文档
    │   └── timezone-list.md     #   时区完整列表等
    └── assets/                  # 可选：静态资源
        └── schema.json          #   数据模板等
```

**对比 V1**：

| 项目 | V1 (当前) | V2 (目标) |
|------|-----------|-----------|
| 元数据文件 | `skill.yaml` | `SKILL.md` (YAML frontmatter) |
| 工具实现 | `tools.py` (根目录) | `scripts/tools.py` (scripts 子目录) |
| 文档 | 无 | `SKILL.md` Markdown body |
| 参考资料 | 无 | `references/` 目录 |
| 静态资源 | 无 | `assets/` 目录 |

### 3.3 SKILL.md 格式

#### 3.3.1 Frontmatter（元数据）

```yaml
---
name: datetime-skill
description: >-
  Provides date and time utilities including current time queries
  and date difference calculations. Use when the user asks about
  current time, dates, or needs date-related calculations.
license: MIT
metadata:
  author: MyClaw
  version: "1.0.0"
---
```

**字段说明**：

| 字段 | 必需 | 约束 | 用途 |
|------|------|------|------|
| `name` | 是 | 1-64 字符，小写+数字+连字符 | Skill 标识，必须与目录名一致 |
| `description` | 是 | 1-1024 字符 | Skill 发现与路由的唯一依据 |
| `license` | 否 | 字符串 | 许可证声明 |
| `compatibility` | 否 | 1-500 字符 | 运行环境要求 |
| `metadata` | 否 | string→string 映射 | 扩展字段（作者、版本等） |

#### 3.3.2 Body（指令文档）

Frontmatter 之后的 Markdown 正文为 Skill 的**指令文档**，仅在 Skill **被激活时**加载。

```markdown
# DateTime Skill

## Quick Start

获取当前时间：
- 工具：`get_current_time`
- 参数：`timezone`（默认 `Asia/Shanghai`）

计算日期差：
- 工具：`calculate_date_diff`
- 参数：`date1`, `date2`（格式 `YYYY-MM-DD`）

## Notes

- 支持所有 IANA 时区标识符
- 详细时区列表参见 [references/timezone-list.md](references/timezone-list.md)
```

**最佳实践**（引自 Anthropic 官方指南）：

| 实践 | 说明 |
|------|------|
| **保持简洁** | body 控制在 500 行 / 5000 token 以内 |
| **不要解释常识** | LLM 已知的知识不需要重复说明 |
| **一层引用深度** | 从 SKILL.md 直接引用资源文件，避免嵌套引用 |
| **第三人称描述** | description 用第三人称（"Processes PDFs"，而非 "I can process PDFs"） |

### 3.4 渐进式披露架构

```
                    ┌─────────────────────────────────────────┐
                    │         Three-Tier Loading Model         │
                    ├─────────────────────────────────────────┤
                    │                                         │
 启动时 ──────────► │  Level 1: Metadata (~100 tokens/skill)  │
                    │    name + description                   │
                    │    → 注入 system prompt 的技能列表       │
                    │    → 极轻量，100个 Skill 也无压力         │
                    │                                         │
 激活时 ──────────► │  Level 2: Instructions (<5000 tokens)   │
 (Agent 构建时)     │    SKILL.md body                        │
                    │    → 导入 scripts/ 中的工具函数          │
                    │    → 注册为 LangChain Tool 对象          │
                    │                                         │
 按需 ────────────► │  Level 3: Resources (无限)              │
 (运行时)           │    references/ assets/ scripts/          │
                    │    → 仅在工具调用/用户查询时读取          │
                    │    → 脚本执行只返回输出，不占上下文       │
                    │                                         │
                    └─────────────────────────────────────────┘
```

**Token 开销估算**（引自 OpenClaw 实现）：

```
每个 Skill: ~97 字符 + len(name) + len(description)
基础开销（≥1 个 Skill 时）: 195 字符
粗略换算: ~4 字符/token

示例: 10 个 Skill，平均 description 150 字符
  = 195 + 10 × (97 + 20 + 150) = 2865 字符 ≈ 716 tokens
```

### 3.5 Skill 加载器改造

#### 3.5.1 两阶段加载流程

**Phase A — Discovery（应用启动时）**

```python
for skill_dir in skills_directory:
    if (skill_dir / "SKILL.md").exists():
        frontmatter = parse_yaml_frontmatter(skill_dir / "SKILL.md")
        catalog.append(SkillMeta(
            name=frontmatter["name"],
            description=frontmatter["description"],
            path=skill_dir,
            status="discovered",
            metadata=frontmatter.get("metadata", {}),
        ))
```

此阶段：
- 仅读取 SKILL.md 的 YAML frontmatter（通常不超过 10 行）
- **不读取** Markdown body
- **不导入** Python 模块
- **不执行**任何代码
- 结果：一个轻量 Skill 目录（name + description + path）

**Phase B — Activation（Agent 构建时）**

```python
for skill in catalog:
    if skill.status == "discovered":
        scripts_dir = skill.path / "scripts"
        tool_functions = scan_and_import_tools(scripts_dir)
        skill.tools = tool_functions
        skill.status = "activated"
```

此阶段：
- 扫描 `scripts/` 目录下所有 `.py` 文件
- 通过 `importlib` 动态导入模块
- 收集所有使用 `@tool` 装饰器的函数
- 注册为 LangChain Tool 对象供 Agent 使用

#### 3.5.2 工具发现机制

采用**约定优于配置**原则，无需在 frontmatter 中显式声明工具列表：

```
约定规则：
1. scripts/ 目录下所有 .py 文件会被扫描
2. 文件中所有使用 @tool 装饰器的函数自动注册
3. 函数的 docstring 作为工具 description（这是 LangChain @tool 的标准行为）
```

**对比 V1**：

| 项目 | V1 | V2 |
|------|-----|-----|
| 工具声明 | `skill.yaml` 中显式列出每个工具的 `name` + `entry` | 自动发现 `@tool` 装饰的函数 |
| 导入方式 | `importlib.import_module("skill_name.tools")` | 扫描 `scripts/*.py`，逐文件导入 |
| 模块路径 | `skills/datetime_skill/tools.py` | `skills/datetime-skill/scripts/tools.py` |

#### 3.5.3 Level 3 按需加载 API

```python
def get_skill_doc(skill_name: str) -> str:
    """按需读取 SKILL.md 的 Markdown body（Level 2 文档）"""
    skill = catalog.get(skill_name)
    if skill and skill.doc_content is None:
        full_content = (skill.path / "SKILL.md").read_text()
        skill.doc_content = extract_body(full_content)  # 去掉 frontmatter
    return skill.doc_content

def get_skill_reference(skill_name: str, ref_path: str) -> str:
    """按需读取 references/ 或 assets/ 中的资源文件（Level 3）"""
    skill = catalog.get(skill_name)
    file_path = skill.path / ref_path
    return file_path.read_text()
```

### 3.6 System Prompt 中的 Skill 注入

Agent 构建时，将所有 discovered/activated Skill 的 `name` + `description` 以紧凑格式注入 system prompt：

```
<available_skills>
<skill name="datetime-skill">Provides date and time utilities including current time queries and date difference calculations. Use when the user asks about current time, dates, or needs date-related calculations.</skill>
<skill name="web-search">Search the web for real-time information. Use when the user asks about current events, recent data, or needs up-to-date information.</skill>
</available_skills>
```

每个 Skill 仅占 ~100 tokens，大规模 Skill 库也不会显著膨胀 system prompt。

### 3.7 迁移方案：datetime_skill → datetime-skill

**V1 结构**：

```
skills/datetime_skill/
├── skill.yaml
└── tools.py
```

**V2 结构**：

```
skills/datetime-skill/
├── SKILL.md
└── scripts/
    └── tools.py
```

**SKILL.md 内容**：

```markdown
---
name: datetime-skill
description: >-
  Provides date and time utilities including current time queries
  and date difference calculations. Use when the user asks about
  current time, dates, or needs date-related calculations.
metadata:
  author: MyClaw
  version: "1.0.0"
---

# DateTime Skill

## Tools

### get_current_time

获取指定时区的当前日期和时间。

- **参数**: `timezone` (string, 默认 `Asia/Shanghai`) — IANA 时区标识
- **返回**: 格式化时间字符串，如 `2026-02-22 21:45:30 CST (UTC+0800)`

### calculate_date_diff

计算两个日期之间的天数差。

- **参数**: `date1`, `date2` (string, 格式 `YYYY-MM-DD`)
- **返回**: 两个日期之间的天数差描述
```

**`scripts/tools.py`** 内容与 V1 的 `tools.py` 完全相同（只是移到了 `scripts/` 子目录）。

---

## 4. Prompt / Memory 文件化（F-11）

### 4.1 文件结构

```
backend/
├── prompts/
│   └── system.md                    # 系统提示词
├── memory/
│   └── conversations/               # 对话记录
│       ├── conv_<session_id>.md      # 每个会话一个文件
│       └── ...
```

### 4.2 System Prompt 文件化

**当前状态**：系统提示词硬编码在 `backend/agent/engine.py` 的 `SYSTEM_PROMPT` 常量中。

**目标**：迁移至 `backend/prompts/system.md`，启动时读取。

**文件格式**：

```markdown
# MyClaw System Prompt

你是 MyClaw，一个通用 AI 助手。

你可以使用提供的工具来完成用户的任务。

## 执行原则

1. 仅处理用户最新一条消息的需求，不要重复处理历史已完成的任务
2. 每一步选择最合适的工具
3. 使用 python_executor 时，请将完整代码写在一次调用中，不要拆成多次调用
4. 工具调用获得结果后，直接用文字总结回复用户，不要重复调用相同工具
5. 如果工具执行失败，最多重试一次，然后给出解释
6. 最终给出清晰、完整的回答
```

**加载逻辑**：

```python
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def load_system_prompt() -> str:
    path = PROMPTS_DIR / "system.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT  # 降级为硬编码默认值
```

### 4.3 对话记录持久化

**目标**：每个 WebSocket 会话结束时（或每轮对话完成后），将对话记录保存为 Markdown 文件。

**文件格式**（`memory/conversations/conv_<session_id>.md`）：

```markdown
---
session_id: a1b2c3d4
created_at: 2026-02-22T21:45:00Z
updated_at: 2026-02-22T21:47:30Z
turns: 2
---

# 对话记录

## Turn 1

### 用户 (21:45:00)

现在几点了？

### Agent 决策 (Step 1)

**LLM → 工具调用**: `get_current_time`
**参数**: `{"timezone": "Asia/Shanghai"}`

### 工具结果 (Step 1)

**工具**: `get_current_time` | **状态**: 成功
```
2026-02-22 21:45:30 CST (UTC+0800)
```

### Agent 最终回答 (Step 2)

现在的时间是 **2026年2月22日 21:45:30**（北京时间，UTC+8）。

---

## Turn 2

### 用户 (21:46:15)

距离2026年国庆节还有多少天？

### Agent 决策 (Step 1)

**LLM → 工具调用**: `calculate_date_diff`
**参数**: `{"date1": "2026-02-22", "date2": "2026-10-01"}`

### 工具结果 (Step 1)

**工具**: `calculate_date_diff` | **状态**: 成功
```
2026-02-22 和 2026-10-01 之间相差 221 天
```

### Agent 最终回答 (Step 2)

距离 2026 年国庆节（10月1日）还有 **221 天**。
```

**写入时机**：

| 事件 | 动作 |
|------|------|
| 每轮对话完成（`final_answer` 或 `error` 后） | 追加当前 Turn 到文件 |
| WebSocket 断开 | 写入最终的 `updated_at` |
| 新建对话 | 创建新的 `conv_<session_id>.md` |

### 4.4 Prompt 管理 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/prompts/system` | 获取当前 system prompt 内容 |
| PUT | `/api/prompts/system` | 更新 system prompt（写入文件 + 热加载） |
| GET | `/api/conversations` | 列出所有对话记录摘要 |
| GET | `/api/conversations/{session_id}` | 获取指定对话的完整记录 |

#### GET /api/prompts/system 响应

```json
{
  "content": "# MyClaw System Prompt\n\n你是 MyClaw...",
  "path": "prompts/system.md",
  "updated_at": "2026-02-22T20:00:00Z"
}
```

#### PUT /api/prompts/system 请求

```json
{
  "content": "# MyClaw System Prompt\n\n你是 MyClaw（更新版）..."
}
```

---

## 5. 后端事件体系增强（F-12）

### 5.1 新增事件类型

在 V1 的 6 种事件基础上，V2 新增以下事件类型：

| 事件类型 | 触发时机 | 用途 |
|----------|----------|------|
| `init_status` | WebSocket 连接建立后 | 推送初始化 Job 执行结果和系统状态 |
| `graph_reset` | 每次用户提问开始前 | 通知前端清空运行时节点，准备新的执行图 |
| `node_enter` | 进入一个执行节点时 | 前端在 Graph 中新增节点并高亮为"执行中" |
| `node_exit` | 离开一个执行节点时 | 前端将节点标记为"已完成"或"失败" |

### 5.2 init_status 事件

WebSocket 连接建立后，后端立即推送一次 `init_status`，包含所有 Init Job 的执行结果。

```json
{
  "type": "init_status",
  "step": 0,
  "timestamp": "2026-02-22T21:44:00Z",
  "data": {
    "jobs": [
      {
        "name": "load_config",
        "status": "success",
        "detail": "已加载 .env 配置",
        "duration_ms": 2
      },
      {
        "name": "load_system_prompt",
        "status": "success",
        "detail": "prompts/system.md (328 字符)",
        "duration_ms": 1
      },
      {
        "name": "check_llm",
        "status": "success",
        "detail": "qwen-plus 连接正常",
        "duration_ms": 1200
      },
      {
        "name": "discover_skills",
        "status": "success",
        "detail": "发现 1 个 Skill: datetime-skill",
        "duration_ms": 5
      },
      {
        "name": "activate_skills",
        "status": "success",
        "detail": "激活 2 个工具: get_current_time, calculate_date_diff",
        "duration_ms": 15
      },
      {
        "name": "register_tools",
        "status": "success",
        "detail": "共 7 个工具就绪 (5 内置 + 2 Skill)",
        "duration_ms": 0
      }
    ],
    "system_prompt_preview": "你是 MyClaw，一个通用 AI 助手...",
    "tools": [
      {"name": "read_file", "source": "builtin"},
      {"name": "write_file", "source": "builtin"},
      {"name": "web_fetch", "source": "builtin"},
      {"name": "python_executor", "source": "builtin"},
      {"name": "shell_executor", "source": "builtin"},
      {"name": "get_current_time", "source": "datetime-skill"},
      {"name": "calculate_date_diff", "source": "datetime-skill"}
    ]
  }
}
```

**Init Job 清单**：

| Job | 执行内容 | 失败影响 |
|-----|----------|----------|
| `load_config` | 读取 `.env` 文件 | 致命：服务无法启动 |
| `load_system_prompt` | 读取 `prompts/system.md` | 降级：使用内置默认提示词 |
| `check_llm` | 向 Qwen API 发送 ping 验证连通性 | 警告：Agent 可能无法工作 |
| `discover_skills` | 扫描 `skills/` 目录，解析 SKILL.md frontmatter | 警告：部分 Skill 不可用 |
| `activate_skills` | 导入 Skill Python 模块，注册 @tool 函数 | 警告：部分工具不可用 |
| `register_tools` | 汇总所有内置 + Skill 工具 | 信息：报告最终可用工具数 |

### 5.3 node_enter / node_exit 事件

每当 Agent 执行图中的一个节点开始/完成时，推送对应事件。

#### node_enter（LLM 节点）

```json
{
  "type": "node_enter",
  "step": 1,
  "timestamp": "2026-02-22T21:45:01Z",
  "data": {
    "node_id": "llm_step_1",
    "node_type": "llm",
    "step": 1,
    "messages_snapshot": [
      {"role": "user", "content": "现在几点了？"}
    ]
  }
}
```

#### node_enter（Tool 节点）

```json
{
  "type": "node_enter",
  "step": 1,
  "timestamp": "2026-02-22T21:45:02Z",
  "data": {
    "node_id": "tool_step_1",
    "node_type": "tool",
    "tool_name": "get_current_time",
    "step": 1
  }
}
```

#### node_exit

```json
{
  "type": "node_exit",
  "step": 1,
  "timestamp": "2026-02-22T21:45:03Z",
  "data": {
    "node_id": "llm_step_1",
    "node_type": "llm",
    "has_tool_calls": true,
    "duration_ms": 1500
  }
}
```

#### messages_snapshot 说明

`node_enter` 的 `messages_snapshot` 字段在 LLM 节点中提供当前发送给模型的完整 messages 列表（不含 system prompt，system prompt 通过 `init_status` 已经下发）。这让前端 Graph 在点击 LLM 节点时可以展示：

- 当前轮发送了哪些消息给模型
- 包含之前的工具调用和结果
- 可清晰看到 Agent 的"思维链"

### 5.4 事件时序示例

以"现在几点了？"为例的完整事件流：

```
[连接建立]
  → init_status (6 jobs)

[用户发送]
  → user_input
  → graph_reset

[Agent Step 1: LLM 决策]
  → node_enter  {node_type:"llm",  step:1, messages_snapshot:[user_msg]}
  → node_exit   {node_type:"llm",  step:1, has_tool_calls:true}
  → tool_call   {name:"get_current_time", args:{timezone:"Asia/Shanghai"}}

[Agent Step 1: 工具执行]
  → node_enter  {node_type:"tool", step:1, tool_name:"get_current_time"}
  → tool_result {name:"get_current_time", status:"success", content:"2026-02-22 21:45:30..."}
  → node_exit   {node_type:"tool", step:1}

[Agent Step 2: LLM 最终回答]
  → node_enter  {node_type:"llm",  step:2, messages_snapshot:[user_msg, ai_tool_call, tool_result]}
  → node_exit   {node_type:"llm",  step:2, has_tool_calls:false}
  → llm_token   {token:"现"} ... (逐字)
  → final_answer {content:"现在的时间是 2026年2月22日 21:45:30..."}
```

---

## 6. 前端可视化（F-13）

### 6.1 布局改造：左右分栏

```
┌─────────────────────────────────────────────────────────────────┐
│  MyClaw - AI Agent                    [连接状态] [新建对话]       │
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│     Chat Panel (50%)     │       Graph Panel (50%)              │
│                          │                                      │
│  ┌────────────────────┐  │  ┌────────────────────────────────┐  │
│  │ [用户] 现在几点了？ │  │  │     Init Phase                 │  │
│  │                    │  │  │  ┌──────────────────────────┐  │  │
│  │ [🔧 get_current_   │  │  │  │ ✅ load_config           │  │  │
│  │   time]            │  │  │  │ ✅ load_system_prompt    │  │  │
│  │ [✅ 2026-02-22...] │  │  │  │ ✅ check_llm            │  │  │
│  │                    │  │  │  │ ✅ discover_skills       │  │  │
│  │ [AI] 现在的时间是   │  │  │  │ ✅ activate_skills      │  │  │
│  │ 2026年2月22日...    │  │  │  │ ✅ register_tools       │  │  │
│  │                    │  │  │  └──────────────────────────┘  │  │
│  └────────────────────┘  │  │                                │  │
│                          │  │     Runtime Graph               │  │
│                          │  │  [User] → [LLM①] → [Tool] →    │  │
│                          │  │           [LLM②] → [Answer]    │  │
│                          │  │                                │  │
│                          │  │  ← 点击节点查看详情 →            │  │
│                          │  └────────────────────────────────┘  │
│  ┌────────────────────┐  │                                      │
│  │ 输入消息... [发送]  │  │                                      │
│  └────────────────────┘  │                                      │
├──────────────────────────┴──────────────────────────────────────┤
│                       Resizable Divider                         │
└─────────────────────────────────────────────────────────────────┘
```

**布局规格**：

| 属性 | 值 |
|------|-----|
| 分栏比例 | 默认 50:50，支持拖拽调整 |
| 最小宽度 | Chat: 360px, Graph: 400px |
| 响应式 | 窗口宽度 < 900px 时切换为上下堆叠或 Tab 切换 |
| 分割条 | 可拖拽的垂直分割线，hover 时显示抓手光标 |

### 6.2 Graph 面板：初始化区域

Graph 面板的上半部分展示 Init Phase 的 Job 执行状态。

**节点渲染规则**：

| 状态 | 样式 |
|------|------|
| 成功 | 绿色背景 + ✅ 图标 |
| 失败 | 红色背景 + ❌ 图标 |
| 警告 | 黄色背景 + ⚠️ 图标 |
| 执行中 | 蓝色脉冲动画 |

**交互**：
- 点击 Job 节点 → 侧边弹出详情面板，显示 `detail`、`duration_ms`
- 点击 `discover_skills` 节点 → 展示发现的 Skill 列表（name + description）
- 点击 `register_tools` 节点 → 展示所有已注册工具列表

### 6.3 Graph 面板：运行时执行图

每次用户发送消息后（`graph_reset`），运行时区域清空并开始绘制新的执行图。

**节点类型**：

| 节点类型 | 形状 | 颜色 | 内容 |
|----------|------|------|------|
| User Input | 圆角矩形 | 蓝色 | 用户输入的文本（截断） |
| LLM Call | 圆角矩形 | 紫色 | "LLM (Step N)" |
| Tool Execution | 菱形 | 橙色 | 工具名称 |
| Final Answer | 圆角矩形 | 绿色 | "最终回答" |
| Error | 圆角矩形 | 红色 | "错误" |

**节点状态**：

| 状态 | 视觉效果 |
|------|----------|
| 等待中 | 灰色，虚线边框 |
| 执行中 | 对应颜色，脉冲动画边框 |
| 已完成 | 对应颜色，实线边框，✅ 标记 |
| 失败 | 红色边框，❌ 标记 |

**连线**：
- 实线箭头连接依次执行的节点
- LLM → Tool → LLM 形成的 Loop 用虚线回边标注 "Loop N"
- 连线上可选标注耗时

### 6.4 Loop 可视化

当 Agent 进行多轮 LLM ↔ Tool 循环时：

```
[User Input]
     │
     ▼
[LLM (1)] ─────────┐
     │               │
     ▼               │  Loop 1
[Tool: get_time] ◄──┘
     │
     ▼
[LLM (2)] ← 最终回答，无 tool_calls
     │
     ▼
[Final Answer]
```

**多轮 Loop 示例**（复杂任务）：

```
[User Input]
     │
     ▼
[LLM (1)] ──┐
     │        │ Loop 1
[Tool: A] ◄─┘
     │
[LLM (2)] ──┐
     │        │ Loop 2
[Tool: B] ◄─┘
     │
[LLM (3)] ← 最终回答
     │
[Final Answer]
```

每个 Loop 用半透明背景色框选，标注 "Loop N"。

### 6.5 节点详情面板

点击 Graph 中的任意节点，在 Graph 面板右侧或底部弹出详情抽屉：

**LLM 节点详情**：

| 字段 | 内容 |
|------|------|
| 节点 ID | `llm_step_1` |
| 类型 | LLM Call |
| 步骤 | Step 1 |
| 耗时 | 1500ms |
| 是否调用工具 | 是 → `get_current_time` |
| Messages 快照 | 完整的 messages 列表（可展开每条查看） |

**Tool 节点详情**：

| 字段 | 内容 |
|------|------|
| 节点 ID | `tool_step_1` |
| 工具名 | `get_current_time` |
| 参数 | `{"timezone": "Asia/Shanghai"}` |
| 执行状态 | 成功 |
| 返回结果 | `2026-02-22 21:45:30 CST (UTC+0800)` |
| 耗时 | 5ms |

**Messages 快照详情**（LLM 节点点击后展示）：

```
┌─────────────────────────────────────────────┐
│ Messages Snapshot — LLM Step 2              │
├─────────────────────────────────────────────┤
│ [1] role: user                              │
│     content: "现在几点了？"                  │
│                                             │
│ [2] role: assistant                         │
│     tool_calls: [{                          │
│       name: "get_current_time",             │
│       args: {"timezone":"Asia/Shanghai"}    │
│     }]                                      │
│                                             │
│ [3] role: tool                              │
│     name: "get_current_time"                │
│     content: "2026-02-22 21:45:30 CST..."   │
└─────────────────────────────────────────────┘
```

### 6.6 Skill 详情入口

在 Graph 面板的 `discover_skills` / `activate_skills` 节点，或通过菜单入口，可查看每个 Skill 的详情：

- **Level 1 信息**（始终可见）：`name`、`description`、`metadata`
- **Level 2 信息**（按需加载）：点击 "查看文档" → 调用 `/api/skills/{name}/doc` → 渲染 SKILL.md body
- **Level 3 信息**（按需加载）：点击具体资源文件 → 加载并展示

这完整体现了渐进式披露在 UI 层面的实现。

---

## 7. 技术选型更新

### 7.1 新增依赖

**后端**：

| 依赖 | 用途 |
|------|------|
| 无新增 | `pyyaml` 已有，用于解析 SKILL.md frontmatter |

**前端**：

| 依赖 | 版本 | 用途 |
|------|------|------|
| `@xyflow/react` | 最新 | 执行图渲染引擎（React Flow v12） |
| `dagre` | 最新 | 有向图自动布局算法 |
| `@types/dagre` | 最新 | dagre TypeScript 类型 |

### 7.2 更新后的项目目录结构

```
e:\myclaw\
├── docs/
│   ├── PRD.md                         # V1 PRD（归档）
│   └── PRD-v2.md                      # V2 PRD（本文档）
├── backend/
│   ├── main.py                        # FastAPI 入口（增加 init job 收集）
│   ├── requirements.txt
│   ├── .env
│   ├── prompts/                       # 【新增】提示词文件
│   │   └── system.md                  #   系统提示词（Markdown）
│   ├── memory/                        # 【新增】记忆文件
│   │   └── conversations/             #   对话记录
│   │       └── conv_<id>.md
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── engine.py                  # Agent 引擎（增加 node_enter/exit 事件）
│   │   ├── llm.py
│   │   ├── tool_registry.py
│   │   ├── skill_loader.py            # 【重构】两阶段加载，AgentSkills 规范
│   │   └── init_jobs.py               # 【新增】初始化 Job 收集器
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── read_file.py
│   │   ├── write_file.py
│   │   ├── web_fetch.py
│   │   ├── python_executor.py
│   │   └── shell_executor.py
│   ├── skills/                        # 【重构】遵循 AgentSkills 规范
│   │   └── datetime-skill/            #   目录名 = name（连字符）
│   │       ├── SKILL.md               #   frontmatter + 文档
│   │       └── scripts/
│   │           └── tools.py           #   工具实现
│   ├── models/
│   │   └── schemas.py                 # 增加新事件类型定义
│   └── api/
│       └── routes.py                  # 增加 prompt/conversation API
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                    # 【重构】左右分栏布局
│       ├── types/
│       │   └── index.ts              # 增加新事件类型
│       ├── hooks/
│       │   ├── useWebSocket.ts       # 增加新事件处理
│       │   └── useGraph.ts           # 【新增】Graph 状态管理
│       ├── components/
│       │   ├── ChatPanel.tsx          # 不变
│       │   ├── GraphPanel.tsx         # 【新增】Graph 面板容器
│       │   ├── InitJobsSection.tsx    # 【新增】初始化 Job 展示
│       │   ├── ExecutionGraph.tsx     # 【新增】运行时执行图
│       │   ├── NodeDetailDrawer.tsx   # 【新增】节点详情抽屉
│       │   ├── MessageList.tsx
│       │   ├── MessageItem.tsx
│       │   ├── UserMessage.tsx
│       │   ├── AssistantMessage.tsx
│       │   ├── ToolCallCard.tsx
│       │   ├── ToolResultCard.tsx
│       │   ├── ThinkingIndicator.tsx
│       │   ├── WelcomeScreen.tsx
│       │   ├── ErrorMessage.tsx
│       │   └── InputBar.tsx
│       └── styles/
│           └── global.css
```

---

## 8. 接口设计更新

### 8.1 WebSocket 事件类型汇总

| 事件类型 | 来源 | 方向 | 版本 |
|----------|------|------|------|
| `user_input` | 客户端发送 + 服务端回显 | 双向 | V1 |
| `llm_token` | LLM 流式 token | S→C | V1 |
| `tool_call` | LLM 决定调用工具 | S→C | V1 |
| `tool_result` | 工具执行完毕 | S→C | V1 |
| `final_answer` | Agent 最终回答 | S→C | V1 |
| `error` | 执行出错 | S→C | V1 |
| `init_status` | 初始化 Job 状态 | S→C | **V2 新增** |
| `graph_reset` | 新的执行开始 | S→C | **V2 新增** |
| `node_enter` | 进入执行节点 | S→C | **V2 新增** |
| `node_exit` | 离开执行节点 | S→C | **V2 新增** |

### 8.2 HTTP 接口汇总

| 方法 | 路径 | 描述 | 版本 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | V1 |
| GET | `/api/tools` | 工具列表 | V1 |
| GET | `/api/skills` | Skill 列表 | V1 |
| POST | `/api/skills/reload` | 重新加载 Skills | V1 |
| GET | `/api/skills/{name}/doc` | 获取 Skill 文档（Level 2） | **V2 新增** |
| GET | `/api/skills/{name}/reference/{path}` | 获取 Skill 资源文件（Level 3） | **V2 新增** |
| GET | `/api/prompts/system` | 获取 system prompt | **V2 新增** |
| PUT | `/api/prompts/system` | 更新 system prompt | **V2 新增** |
| GET | `/api/conversations` | 对话记录列表 | **V2 新增** |
| GET | `/api/conversations/{session_id}` | 获取对话记录 | **V2 新增** |

---

## 9. 开发计划

### Phase 4 — V2 迭代（6 个步骤）

#### Step 4.1 — Skill 结构重构

**范围**：后端 Skill 加载机制改造

**改动清单**：
1. 将 `datetime_skill/` 重命名为 `datetime-skill/`
2. `skill.yaml` → `SKILL.md`（YAML frontmatter + Markdown body）
3. `tools.py` → `scripts/tools.py`
4. 重写 `skill_loader.py`：两阶段加载（Discovery + Activation）
5. `skill_loader.py` 解析 SKILL.md frontmatter（仅 `name` + `description`）
6. 自动发现 `scripts/*.py` 中的 `@tool` 函数
7. 添加 `/api/skills/{name}/doc` 和 `/api/skills/{name}/reference/{path}` 接口

**回归测试**：
- Agent 正常启动，datetime-skill 的两个工具可用
- "现在几点了？" 正确调用 get_current_time
- `/api/skills` 返回正确的 Skill 信息
- `/api/skills/reload` 正常工作

#### Step 4.2 — Prompt / Memory 文件化

**范围**：后端提示词和对话记录管理

**改动清单**：
1. 创建 `backend/prompts/system.md`
2. `engine.py` 从文件加载 system prompt（含降级逻辑）
3. 创建 `backend/memory/conversations/` 目录
4. `routes.py` 在每轮对话完成后写入对话记录
5. 新增 `/api/prompts/system` (GET/PUT) 接口
6. 新增 `/api/conversations` 和 `/api/conversations/{id}` 接口

**回归测试**：
- Agent 启动后正确读取 system.md 作为系统提示词
- 对话后在 `memory/conversations/` 目录下生成 .md 文件
- 通过 API 修改 system prompt 后立即生效
- 原有对话功能不受影响

#### Step 4.3 — 后端 Init Job 收集 + 丰富事件

**范围**：后端初始化报告和执行事件增强

**改动清单**：
1. 创建 `init_jobs.py` — Init Job 收集器
2. 修改 `main.py` lifespan：逐 Job 执行并收集结果
3. `routes.py`：WebSocket 连接后推送 `init_status`
4. `engine.py`：在 astream 循环中发射 `node_enter`/`node_exit` 事件
5. `engine.py`：在 LLM node_enter 中携带 `messages_snapshot`
6. `routes.py`：用户消息开始处理前推送 `graph_reset`
7. `schemas.py`：新增事件类型定义

**回归测试**：
- WebSocket 连接后收到 `init_status`，包含所有 Job 状态
- 发送消息后收到 `graph_reset` → `node_enter` → `tool_call` → `tool_result` → `node_exit` → `node_enter` → `final_answer` 的完整事件序列
- 原有前端仍能正常显示消息（忽略未知事件类型）

#### Step 4.4 — 前端左右分栏 + Graph 基础渲染

**范围**：前端布局改造和 Graph 面板搭建

**改动清单**：
1. 安装 `@xyflow/react`、`dagre`
2. 重构 `App.tsx`：左右分栏布局（可拖拽分割）
3. 新建 `GraphPanel.tsx`：Graph 面板容器
4. 新建 `InitJobsSection.tsx`：渲染初始化 Job 节点
5. 新建 `ExecutionGraph.tsx`：运行时执行图（@xyflow/react）
6. `useWebSocket.ts`：处理 `init_status`、`graph_reset` 事件
7. 新建 `useGraph.ts`：管理 Graph 节点和边的状态

**回归测试**：
- 页面左侧 Chat 面板功能不变
- 右侧 Graph 面板显示 Init Job 节点（全部绿色表示成功）
- 发送消息后右侧出现运行时节点

#### Step 4.5 — Graph 实时状态 + 节点详情

**范围**：Graph 交互增强

**改动清单**：
1. `useGraph.ts`：处理 `node_enter`/`node_exit` 事件，更新节点状态（颜色、动画）
2. `ExecutionGraph.tsx`：实现自定义节点渲染（不同类型不同形状/颜色）
3. 实现 Loop 可视化（半透明背景框 + Loop 标签）
4. 新建 `NodeDetailDrawer.tsx`：点击节点弹出详情抽屉
5. 详情抽屉展示 messages_snapshot（LLM 节点）和工具参数/结果（Tool 节点）
6. dagre 自动布局，节点动态添加时自动重新排列

**回归测试**：
- LLM 节点执行时有脉冲动画，完成后变绿
- Tool 节点执行时有脉冲动画，完成后变绿/红
- 多步工具调用（如"读取文件并总结"）正确显示 Loop
- 点击任意节点可查看详细信息
- messages_snapshot 内容正确，可展开查看每条消息

#### Step 4.6 — Prompt 管理 + Skill 文档入口

**范围**：前端管理界面

**改动清单**：
1. Graph 面板中 `discover_skills` 节点可点击查看 Skill 列表
2. Skill 列表中每项可点击 "查看文档" → 调用 API 加载 SKILL.md body → Markdown 渲染
3. Header 区域添加 "Prompt 管理" 入口
4. Prompt 管理页面：展示当前 system.md 内容 + 在线编辑 + 保存

**回归测试**：
- 点击 Skill 节点 → 展示 Skill 列表（name + description）
- 点击 "查看文档" → 异步加载并渲染 SKILL.md body
- Prompt 管理页面正确显示 system prompt
- 编辑并保存后，新对话使用更新后的 prompt

---

## 10. 验收标准

### V1 保留验收项

| 编号 | 验收项 | 通过条件 |
|------|--------|----------|
| AC-01 | 基本对话 | 用户发送消息，Agent 正确回复 |
| AC-02 | 文件读取 | Agent 调用 read_file 并展示内容 |
| AC-03 | 网页抓取 | Agent 调用 web_fetch 并总结 |
| AC-04 | Python 执行 | Agent 调用 python_executor 并展示结果 |
| AC-05 | 链路可视化 | Chat 面板能看到完整的工具调用过程 |
| AC-06 | Skill 扩展 | datetime-skill 的工具可用 |
| AC-07 | 多轮对话 | Agent 能理解上下文 |
| AC-08 | 错误处理 | 工具执行失败时优雅处理 |

### V2 新增验收项

| 编号 | 验收项 | 通过条件 |
|------|--------|----------|
| AC-09 | Skill 结构标准化 | `datetime-skill/SKILL.md` + `scripts/tools.py` 结构正常工作 |
| AC-10 | 渐进式披露 | 启动日志显示仅读取了 frontmatter；SKILL.md body 未在启动时加载 |
| AC-11 | System Prompt 文件化 | `prompts/system.md` 存在且被 Agent 正确使用 |
| AC-12 | 对话记录持久化 | `memory/conversations/` 下有对话记录 Markdown 文件 |
| AC-13 | Init Job 可视化 | Graph 面板显示 6 个 Init Job 节点及状态 |
| AC-14 | 执行图实时更新 | 发送消息后，Graph 实时显示 LLM/Tool 节点执行过程 |
| AC-15 | 节点状态动画 | 执行中节点有脉冲动画，完成后变绿 |
| AC-16 | Loop 可视化 | 多步工具调用能看到 Loop 标注 |
| AC-17 | 节点详情查看 | 点击 LLM 节点可查看完整 messages_snapshot |
| AC-18 | Skill 文档查看 | 通过 Graph 可查看 Skill 的 SKILL.md 文档内容 |
| AC-19 | Prompt 在线编辑 | 通过前端可查看和编辑 system prompt |

---

## 附录 A：研究参考

本 PRD 的 Skill 架构设计基于以下权威来源的深入研究：

| 来源 | URL | 关键洞察 |
|------|-----|----------|
| AgentSkills 规范 | agentskills.io/specification | SKILL.md 格式标准、目录结构约定、frontmatter 字段定义 |
| Anthropic Agent Skills Overview | platform.claude.com/docs/en/agents-and-tools/agent-skills/overview | 三层渐进式披露模型、Token 开销分析、filesystem-based 架构 |
| Anthropic Skills Best Practices | platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices | 简洁原则、自由度匹配、progressive disclosure patterns、反模式 |
| OpenClaw Skills 文档 | docs.openclaw.ai/tools/skills | 加载优先级、gating 机制、token impact 计算公式、session snapshot |
| OpenClaw Creating Skills | docs.openclaw.ai/tools/creating-skills | 实际 Skill 开发流程、最小化示例 |

### 关键设计决策记录

**决策 1：工具发现机制**

| 方案 | 描述 | 优劣 |
|------|------|------|
| A: frontmatter 显式声明 | 在 SKILL.md metadata 中列出每个工具 | 明确但冗余，违反 AgentSkills 规范（metadata 是 string→string） |
| B: 约定式自动发现 | 扫描 scripts/*.py 中的 @tool 函数 | ✅ 采用。符合 AgentSkills 规范精神，零配置，convention over configuration |
| C: 单独 manifest 文件 | scripts/ 下放一个 tools.json | 额外文件，增加维护负担 |

**决策 2：何时 Activate（导入 Python 模块）**

| 方案 | 描述 | 优劣 |
|------|------|------|
| A: 启动时全部激活 | lifespan 中 Discovery + Activation 一起完成 | 简单直接，启动后立即可用 |
| B: 首次消息时激活 | Discovery 在启动时，Activation 延迟到第一条消息 | 启动快，但首次消息延迟高 |
| C: Lazy Proxy | 创建代理 Tool，首次调用时真正 import | 最优雅，但 LangChain 的 Tool 需要完整 schema |
| ✅ 采用方案 A | 启动时全部激活 | 对于 MyClaw 的规模（<20 Skills），启动延迟可忽略；且 LangChain create_agent 需要完整 Tool 对象 |

**决策说明**：虽然 Anthropic 的 Claude Skills 可以做到纯粹的 Level 1-only 启动（因为 Claude 通过 bash 自行读取 SKILL.md），但 MyClaw 基于 LangChain 的 `create_agent`，需要在构建 Agent 时提供完整的 Tool 对象列表。因此 Activation 必须在 Agent 构建前完成。我们选择在启动时完成 Activation，但在概念上保持 Discovery 和 Activation 的分离（两个独立的 Init Job），以便未来支持按需激活/禁用单个 Skill。
