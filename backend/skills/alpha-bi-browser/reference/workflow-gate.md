# Alpha BI 执行门控流程（Workflow Gate）

## 目标

防止“直接点按钮”“未读 reference 就执行”导致的 click 失败、误点和假成功。

## 强制流程

1. **页面识别**
   - `browser_navigate` 后执行 `browser_snapshot(summary)`。
   - 确认页面锚点命中（报表标题、筛选区、查询按钮区域）。

2. **先出计划（必须）**
   - 在执行任何点击/输入前，先列出本次操作步骤。
   - 计划格式建议：`步骤编号 | 动作目标 | 预期结果 | 验收信号`。

3. **按步骤读 reference（必须）**
   - 日期相关步骤 -> `date-range-picker.md`
   - 查询步骤 -> `query-button.md`
   - 单选/多选/复选步骤 -> 对应组件文档
   - 任何步骤执行前都要参考：`page-element-map.md` + `operation-matrix.md`

4. **执行闭环**
   - 每一步按 `snapshot -> 锚定 -> ref -> 操作 -> 校验` 执行。
   - 禁止 `text="查询"` 直接点击；必须区块锚定后使用 `ref`。

5. **步骤回执（必须）**
   - 每步结束输出：
     - `before`
     - `after`
     - `verified`（true/false）
     - `evidence`（值变化/页码变化/行数变化/更新时间）

6. **异常分流**
   - 任一步失败，立即读取 `error-recovery.md`。
   - 同策略最多重试 2 次，超过即切换策略或终止上报。

## 违规判定（需立即纠正）

- 未产出计划就开始点击/输入
- 未读取对应 reference 就执行该步骤
- 点击返回成功但无可观测变化仍继续下一步
- 对同名“查询”使用文本模糊点击
