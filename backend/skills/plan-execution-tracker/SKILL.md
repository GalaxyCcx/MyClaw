---
name: plan-execution-tracker
description: >-
  为复杂多步骤任务提供文件化执行计划与进度追踪。先生成临时 plan 文件并按步骤执行，
  每步前读取、每步后更新状态；遇到阻塞可修订计划；全部完成后删除临时文件并输出阶段总结。
  适用于用户要求先做计划、按 todo/checklist 执行、需要过程可追踪与可回溯的场景。
metadata:
  author: MyClaw
  version: "1.0.0"
  tags: [plan, checklist, execution, workflow, tracking]
---

# Plan Execution Tracker

用于将复杂任务转为可追踪的文件化执行流程。执行时必须维护一个临时 plan 文件。

## 适用场景

- 用户明确要求“先做计划再执行”
- 任务步骤多、依赖强、容易中途跑偏
- 需要可审计的执行轨迹（每步状态可回看）

## 强制规则

1. 先创建临时 plan 文件，再开始任何实质执行。
2. 每执行一步前必须先 `read_file` 读取当前 plan 文件。
3. 每执行一步后必须更新该步状态并写回 plan 文件。
4. 若执行中需改计划，必须在同一 plan 文件内记录修订原因与变更内容。
5. 所有步骤 `done` 后，删除临时 plan 文件并输出阶段性总结。
6. 若未删除临时文件，不得宣称流程完整收尾。

## 临时文件路径约定

- 目录：`backend/memory/runtime_plans/`
- 文件名：`plan_<task_slug>_<YYYYMMDD_HHMMSS>.md`

示例：`backend/memory/runtime_plans/plan_alpha_bi_export_20260302_173500.md`

## 执行流程

### 1) 初始化计划文件

1. 生成任务 slug 与时间戳。
2. 依据模板创建 plan 文件（见 `reference/plan-file-template.md`）。
3. 初始状态：
   - 全局 `status: in_progress`
   - 第一个步骤 `in_progress`
   - 其他步骤 `pending`

### 2) 按步骤执行（循环）

每轮循环都执行以下顺序：

1. `read_file(plan_path)` 读取最新计划
2. 选择当前 `in_progress` 步骤
3. 执行该步骤的一个最小动作
4. 校验该步骤是否达成完成标准
5. 更新计划文件并 `write_file` 整体写回：
   - 完成则改为 `done`，下一步改 `in_progress`
   - 未完成则记录 `blocked` 或保留 `in_progress`
   - 记录 `last_update` 与简短日志

### 3) 计划修订

触发条件：

- 连续失败 >= 2 次
- 页面结构或前提变化
- 用户追加/修改需求

修订要求：

1. 在 `Plan Revisions` 追加一条修订记录
2. 在 `Steps` 中增删改步骤
3. 已 `done` 步骤默认保留，不可随意回退
4. `write_file` 写回完整计划

### 4) 收尾

当所有步骤状态均为 `done`：

1. 生成阶段性总结（目标、结果、关键决策、异常与处理）
2. 删除临时文件（推荐用 `python_executor` 执行删除）
3. 向用户确认流程完成

删除示例（通过 `python_executor`）：

```python
from pathlib import Path
p = Path("backend/memory/runtime_plans/plan_example_20260302_173500.md")
if p.exists():
    p.unlink()
print("deleted" if not p.exists() else "delete_failed")
```

## 与其他 Skill 协作

- 浏览器任务：先读 `browser-automation`，再读对应业务 skill（如 `alpha-bi-browser`）
- 本 skill 负责“计划与状态机”，其他 skill 负责“领域操作细节”

## 参考文档

- 模板：`reference/plan-file-template.md`
- 状态更新规则：`reference/update-rules.md`
