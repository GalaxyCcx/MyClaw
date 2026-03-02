# Plan File Template

将以下模板写入临时 plan 文件，并按执行过程持续更新。

```markdown
# Execution Plan

- plan_id: <plan_alpha_bi_export_20260302_173500>
- task: <用户任务简述>
- status: in_progress
- created_at: <ISO8601>
- last_update: <ISO8601>
- owner: agent

## Steps

| id | step | status | done_criteria | notes |
|---|---|---|---|---|
| S1 | <步骤1> | in_progress | <完成标准> | |
| S2 | <步骤2> | pending | <完成标准> | |
| S3 | <步骤3> | pending | <完成标准> | |
| S4 | <步骤4> | pending | <完成标准> | |

## Execution Log

- <timestamp> INIT: plan created
- <timestamp> S1: started

## Plan Revisions

- rev: 1
  - time: <timestamp>
  - reason: <初始化>
  - change: <初始步骤定义>
```

## 状态枚举

- `pending`: 尚未开始
- `in_progress`: 当前执行中
- `blocked`: 被阻塞，需改策略或补前置条件
- `done`: 已完成并通过该步完成标准
- `cancelled`: 因计划变更而取消

## 完成判定

仅当 `Steps` 全部为 `done` 或 `cancelled` 且无 `in_progress/blocked` 时，才可将全局 `status` 置为 `done`。
