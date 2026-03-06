---
name: alphabi-operator
description: AlphaBI 页面专项操作规范（V3）。覆盖初始化全屏扫描、Tab 补扫、筛选查询、下载任务中心链路。
metadata:
  author: MyClaw
  version: "1.0.0"
  tags: [alphabi, browser, vision, v3, report]
---

# AlphaBI Operator

该 Skill 建立在 `browser-vision-operator` 之上，用于 AlphaBI 报表页面的可复现操作。

## 初始化流程（必做）

### A. 全屏滚动预扫

1. `browser_vision_wait_stable`
2. `browser_vision_capture_marked`
3. `browser_vision_scroll_by(dy=700)` 后重复抓图
4. 直到覆盖主要模块

### B. 大型 Tab 补扫

1. 识别主 Tab（如：经营结果/流量拆解/转化归因/过程归因）
2. 每个 Tab 执行：点击 -> 稳定等待 -> 抓标注图
3. 完成后回到目标操作 Tab

## 执行闭环

每一步都要按以下顺序：

1. 先抓（plain/marked/marks）
2. 同帧确定标签
3. 执行动作
4. 再抓验证

## 完成即停（关键）

1. 当目标是日期区间、筛选值、Tab 命中等可验证状态时，必须以 `marks JSON` 为准做后置验证。
2. 一旦在 JSON 中命中目标状态（例如 `2026-03-01` 与 `2026-03-31` 同时出现于目标日期框），立即结束操作并输出结果。
3. 禁止在“已命中目标”后继续执行额外点击、滚动、重试。
4. 同一目标最多 2 轮重试，超限则返回“未命中+原因”，不要无限循环。

## 筛选操作规则

1. 同名控件（如“查询”）必须在目标模块内定位，不做全局模糊点击。
2. 维度+值联动要先确认维度字段，再选值。
3. 选项不在可见区时，优先重抓与重映射，不盲目复用旧标签。

## 下载流程规则

1. 触发下载入口后，必须抓图确认出现下载菜单。
2. 进入任务中心后，定位列表中的“下载”动作并点击。
3. 下载完成以本地落盘为准，不能只看页面状态。

## 参考文档

- `references/alpha-bi-table-index.md`
- `references/alpha-bi-core-metrics.md`
- `references/alpha-bi-problem-location.md`
- `references/alpha-bi-attribution-v1.md`
- `references/alpha-bi-attribution-v2.md`
- `references/alpha-bi-trend-analysis.md`

