# 复选框组组件（Checkbox Group）

## 适用范围

- 常见于“聚合维度”区域
- 选项示例：地区、城市、采一、采二、采三

## 对应 Job

- `POST /api/browser/jobs/alpha-bi/select-checkbox-group`
- 请求：`{ within_text: str, option_texts: list[str], url?: str, wait_after_navigate_ms?: int }`
- 逻辑：navigate → wait → 对每个 option_text，在 within_text 区块内 locate + click

## 标准操作流程

1. `browser_snapshot` 获取复选组及各项状态。
2. 按目标文本逐项检查是否已勾选。
3. 仅对未勾选项执行点击，避免反选。
4. 操作完成后再次 snapshot 校验状态。

## 定位优先级

1. 复选组标题文本（如“聚合维度”）
2. 选项标签文本（城市、采一等）
3. 勾选状态类名或无障碍状态字段

## 组件元素特征（可固定）

以下特征可作为复选组件识别信号：

- `ant-checkbox-group` / `ant-checkbox-wrapper` 样式与容器特征
- 选项标签文本与复选框同一 label 容器关系
- 勾选态 class 或 `aria-checked` 状态字段

注意：允许固定组件特征与状态字段，不要固定页面级绝对层级路径。

## 备用策略

- 先点击复选组标题附近空白区域再重新定位。
- 若单击无效，改点复选框外层标签文字区域。

## 失败信号与恢复

- 失败信号：点击后状态不变、状态来回反复。
- 恢复步骤：
  - 每次点击后立即短等待并校验
  - 若失败两次，刷新 snapshot 并换点击区域
