# MyClaw — 数据分析 Skills + 虚拟环境 产品需求文档 (PRD)

> 版本：v4.0  
> 日期：2026-02-23  
> 状态：待实现  
> 基于：PRD-v3（Web Search）

---

## 1. 背景与动机

### 1.1 现状

MyClaw Agent 已具备完整的通用基座能力（搜索、文件操作、代码执行、Skill 扩展体系）。但在面对**大数据处理和分析**场景时，Agent 缺少专业的数据分析工具链。

此外，项目当前直接使用系统级 Python 环境，所有依赖全局安装，不利于项目打包、移植和在其他机器上部署。

### 1.2 核心目标

| 目标 | 说明 |
|------|------|
| 大数据分析能力 | Agent 能对 CSV/Parquet/JSON 等格式的大数据文件进行 SQL 查询、统计分析、可视化 |
| 虚拟环境管理 | 项目运行在独立虚拟环境中，依赖隔离，一键安装，可移植到其他机器 |
| 零额外云服务 | 新增 Skills 全部基于本地工具，不需要注册新的 API Key |

---

## 2. 功能需求

### 2.1 DuckDB 数据分析 Skill（F-DA-01）

**定位**：大数据文件的 SQL 查询引擎。适合快速预览、聚合统计、格式转换、多文件 JOIN 等场景。

**为什么选 DuckDB**：
- 直接对文件执行 SQL，无需导入数据库
- 处理 GB 级文件速度远快于 pandas
- CLI 模式天然适配 MyClaw 的 `shell_executor` 执行模式
- 开源免费，本地运行，无云依赖

| ID | 需求 | 优先级 |
|----|------|--------|
| F-DA-01-01 | Skill 目录结构遵循 MyClaw 标准：`skills/duckdb-analysis/SKILL.md` + `scripts/` | P0 |
| F-DA-01-02 | SKILL.md 包含 YAML frontmatter（name、description、metadata）和完整调用文档 | P0 |
| F-DA-01-03 | 提供 `inspect` 命令：扫描文件/目录，输出 schema、行数、大小等元数据 | P0 |
| F-DA-01-04 | 提供 `query` 命令：执行 SQL 查询，支持 CSV/Parquet/JSON 文件 | P0 |
| F-DA-01-05 | 提供 `convert` 命令：格式转换（CSV↔Parquet↔JSON） | P1 |
| F-DA-01-06 | 查询结果支持多种输出格式（table、csv、json、markdown） | P1 |
| F-DA-01-07 | 大文件查询自动加 LIMIT 保护，防止输出爆内存 | P1 |

**Skill 目录结构**：

```
backend/skills/duckdb-analysis/
├── SKILL.md                    # 元数据 + Agent 调用文档
└── scripts/
    └── duckdb_tool.py          # CLI 工具入口
```

**输出内容**：
- SQL 查询结果（文本格式：表格/CSV/JSON/Markdown）
- 格式转换后的文件路径
- 数据元信息（schema、行数、文件大小）

### 2.2 Pandas 数据分析 Skill（F-DA-02）

**定位**：精细数据分析与可视化引擎。适合统计分析、趋势识别、异常检测、图表生成、报告输出等场景。

**与 DuckDB Skill 的关系**：互补。DuckDB 负责"大数据快速查询"，pandas 负责"精细分析 + 可视化"。典型流程：DuckDB 从 GB 级文件中筛选出子集 → pandas 对子集做深度分析和画图。

| ID | 需求 | 优先级 |
|----|------|--------|
| F-DA-02-01 | Skill 目录结构遵循 MyClaw 标准 | P0 |
| F-DA-02-02 | 提供 `profile` 命令：生成数据概况报告（shape、dtypes、缺失值、基本统计量） | P0 |
| F-DA-02-03 | 提供 `analyze` 命令：执行分析脚本（分组聚合、相关性、趋势等），输出文本结果 | P0 |
| F-DA-02-04 | 提供 `chart` 命令：生成可视化图表（柱状图、折线图、饼图、热力图等），保存为 PNG | P0 |
| F-DA-02-05 | 提供 `report` 命令：将分析结果组装为 Markdown 报告文件 | P1 |
| F-DA-02-06 | 图表默认保存到 `output/` 目录，路径在结果中返回给 Agent | P1 |
| F-DA-02-07 | 支持中文字体渲染（matplotlib CJK 字体配置） | P1 |

**Skill 目录结构**：

```
backend/skills/pandas-analysis/
├── SKILL.md
└── scripts/
    ├── profile_data.py         # 数据概况
    ├── analyze_data.py         # 分析执行
    ├── chart_data.py           # 图表生成
    └── report_data.py          # 报告组装
```

**输出内容**：
- 分析文本（统计摘要、聚合结果、相关性矩阵）
- 图表文件（PNG 图片路径）
- Markdown 报告文件路径

### 2.3 虚拟环境与依赖管理（F-ENV-01）

**定位**：为项目创建独立 Python 虚拟环境，所有后端依赖和 Skill 依赖统一管理。

| ID | 需求 | 优先级 |
|----|------|--------|
| F-ENV-01-01 | 项目根目录使用 `python -m venv .venv` 创建虚拟环境 | P0 |
| F-ENV-01-02 | `requirements.txt` 包含所有后端核心依赖 | P0 |
| F-ENV-01-03 | `requirements-skills.txt` 包含所有 Skill 所需的额外依赖 | P0 |
| F-ENV-01-04 | 提供一键安装脚本 `scripts/setup.sh`（Linux/Mac）和 `scripts/setup.ps1`（Windows） | P0 |
| F-ENV-01-05 | `python_executor` 和 `shell_executor` 使用虚拟环境中的 Python 解释器 | P0 |
| F-ENV-01-06 | README.md 更新安装指南，说明虚拟环境使用方式 | P1 |
| F-ENV-01-07 | `.gitignore` 排除 `.venv/`、`output/`、`__pycache__/` 等 | P1 |

**依赖分层**：

```
requirements.txt              # 后端核心依赖（已有）
├── langchain, fastapi, uvicorn, httpx ...

requirements-skills.txt       # Skill 扩展依赖（新增）
├── duckdb                    # DuckDB Python binding（含 CLI）
├── pandas                    # 数据分析
├── matplotlib                # 静态图表
├── seaborn                   # 统计图表增强
└── openpyxl                  # Excel 读写支持
```

**一键安装流程**：

```bash
# Windows
cd e:\myclaw\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-skills.txt

# Linux / Mac
cd /path/to/myclaw/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-skills.txt
```

---

## 3. 技术设计

### 3.1 Agent 调用 Skill 流程

```
用户：帮我分析 data/sales.csv 的销售趋势

Agent 思考：需要数据分析能力
  ↓
① read_skill_doc("duckdb-analysis")  →  获取调用文档
  ↓
② shell_executor("python skills/duckdb-analysis/scripts/duckdb_tool.py inspect --path=data/sales.csv")
  →  返回：10 列, 150,000 行, 23.4 MB, schema: date|region|product|revenue|...
  ↓
③ shell_executor("python skills/duckdb-analysis/scripts/duckdb_tool.py query --sql=\"SELECT region, SUM(revenue) as total FROM 'data/sales.csv' GROUP BY region ORDER BY total DESC\"")
  →  返回：聚合结果表格
  ↓
④ read_skill_doc("pandas-analysis")  →  获取调用文档
  ↓
⑤ shell_executor("python skills/pandas-analysis/scripts/chart_data.py --input=data/sales.csv --type=line --x=date --y=revenue --group=region --output=output/trend.png")
  →  返回：图表已保存: output/trend.png
  ↓
⑥ Agent 综合文字回答 + 引用图表路径
```

### 3.2 数据处理原则

**数据不进上下文，只有结论进上下文。**

- Agent **不会** `read_file` 读取 CSV 原始内容（会爆上下文）
- Agent 通过 Skill 脚本在数据侧执行分析，只拿回汇总结果
- 大文件预览使用 `inspect`（只读元数据 + 前几行）
- 图表保存为文件，Agent 只返回文件路径

### 3.3 虚拟环境与工具执行器

当前 `python_executor` 使用 `sys.executable` 启动子进程，这意味着如果主进程在虚拟环境中运行，子进程也自动使用虚拟环境的 Python。

`shell_executor` 执行 shell 命令时，需要确保虚拟环境的 PATH 生效。两种方式：
- **方式 A**（推荐）：主服务在虚拟环境中启动（`activate` 后启动 uvicorn），子进程自动继承环境
- **方式 B**：在 Skill 脚本中使用绝对路径调用虚拟环境的 Python

选用方式 A，最简单且无侵入。

### 3.4 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/.venv/` | 新增 | Python 虚拟环境（gitignore） |
| `backend/requirements-skills.txt` | 新增 | Skill 扩展依赖 |
| `backend/skills/duckdb-analysis/SKILL.md` | 新增 | DuckDB Skill 文档 |
| `backend/skills/duckdb-analysis/scripts/duckdb_tool.py` | 新增 | DuckDB CLI 工具脚本 |
| `backend/skills/pandas-analysis/SKILL.md` | 新增 | Pandas Skill 文档 |
| `backend/skills/pandas-analysis/scripts/profile_data.py` | 新增 | 数据概况脚本 |
| `backend/skills/pandas-analysis/scripts/chart_data.py` | 新增 | 图表生成脚本 |
| `backend/skills/pandas-analysis/scripts/analyze_data.py` | 新增 | 分析执行脚本 |
| `backend/skills/pandas-analysis/scripts/report_data.py` | 新增 | 报告组装脚本 |
| `scripts/setup.ps1` | 新增 | Windows 一键安装脚本 |
| `scripts/setup.sh` | 新增 | Linux/Mac 一键安装脚本 |
| `backend/.gitignore` | 新增/修改 | 排除 .venv、output 等 |
| `README.md` | 修改 | 更新安装指南 |

---

## 4. 验收标准

### 4.1 虚拟环境（AC-ENV）

| ID | 验收项 | 通过条件 |
|----|--------|---------|
| AC-ENV-01 | 虚拟环境创建 | `backend/.venv/` 存在且可激活 |
| AC-ENV-02 | 核心依赖安装 | 激活后 `python -c "import langchain; import fastapi"` 无报错 |
| AC-ENV-03 | Skill 依赖安装 | 激活后 `python -c "import duckdb; import pandas; import matplotlib"` 无报错 |
| AC-ENV-04 | 服务启动 | 在虚拟环境中 `uvicorn main:app` 正常启动 |
| AC-ENV-05 | 工具执行器继承环境 | `python_executor` 中 `import pandas` 能成功 |

### 4.2 DuckDB Skill（AC-DA-01）

| ID | 验收项 | 通过条件 |
|----|--------|---------|
| AC-DA-01-01 | Skill 发现 | 初始化面板显示 `duckdb-analysis` Skill |
| AC-DA-01-02 | 渐进式披露 | Agent 先调 `read_skill_doc` 再调 `shell_executor` |
| AC-DA-01-03 | inspect 命令 | 对测试 CSV 执行 inspect，返回 schema、行数、大小 |
| AC-DA-01-04 | query 命令 | 执行 SQL 聚合查询，返回正确结果 |
| AC-DA-01-05 | convert 命令 | CSV 转 Parquet 成功，文件可再次查询 |
| AC-DA-01-06 | Graph 可视化 | 右侧图中显示 `read_skill_doc` → `shell_executor` 节点链 |

### 4.3 Pandas Skill（AC-DA-02）

| ID | 验收项 | 通过条件 |
|----|--------|---------|
| AC-DA-02-01 | Skill 发现 | 初始化面板显示 `pandas-analysis` Skill |
| AC-DA-02-02 | profile 命令 | 输出 shape、dtypes、缺失值统计、基本描述统计 |
| AC-DA-02-03 | chart 命令 | 生成柱状图 PNG 文件到 output/ 目录 |
| AC-DA-02-04 | 中文支持 | 图表中的中文标签正常显示（不乱码） |
| AC-DA-02-05 | 端到端测试 | 用户问"分析 xxx.csv 的销售趋势"，Agent 完成搜索元数据 → SQL 查询 → 图表生成 → 文字总结 |

---

## 5. 迭代计划

### 大迭代 A：虚拟环境基础设施

| 步骤 | 任务 | 验收 |
|------|------|------|
| A-1 | 创建虚拟环境，安装核心依赖 | AC-ENV-01, AC-ENV-02 |
| A-2 | 创建 `requirements-skills.txt`，安装 Skill 依赖 | AC-ENV-03 |
| A-3 | 在虚拟环境中重启后端服务，验证一切正常 | AC-ENV-04, AC-ENV-05 |
| A-4 | 创建安装脚本、更新 .gitignore 和 README | — |

### 大迭代 B：DuckDB 数据分析 Skill

| 步骤 | 任务 | 验收 |
|------|------|------|
| B-1 | 创建 Skill 目录结构和 SKILL.md | AC-DA-01-01 |
| B-2 | 实现 `duckdb_tool.py`（inspect / query / convert） | AC-DA-01-03 ~ 05 |
| B-3 | 端到端测试：用户提问 → Agent 调用 Skill | AC-DA-01-02, AC-DA-01-06 |

### 大迭代 C：Pandas 数据分析 Skill

| 步骤 | 任务 | 验收 |
|------|------|------|
| C-1 | 创建 Skill 目录结构和 SKILL.md | AC-DA-02-01 |
| C-2 | 实现 profile / chart / analyze / report 脚本 | AC-DA-02-02 ~ 04 |
| C-3 | 端到端测试：完整数据分析链路 | AC-DA-02-05 |

---

## 6. 后续演进

| 方向 | 说明 | 优先级 |
|------|------|--------|
| Deep Research Skill | 基于 web_search + web_fetch 的多源研究报告生成 | P1 |
| 前端图表展示 | 在聊天窗口内嵌显示 Agent 生成的图表（PNG/HTML） | P2 |
| Docker 容器化 | 将虚拟环境升级为 Docker 镜像，进一步简化部署 | P2 |
| 数据源扩展 | 支持 Excel（.xlsx）、数据库连接（PostgreSQL/MySQL） | P3 |
