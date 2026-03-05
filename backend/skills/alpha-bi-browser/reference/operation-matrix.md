# 全元素操作矩阵（执行器模板）

## 使用方式

1. 先在 `page-element-map.md` 判定当前控件类型。
2. 选取对应模板执行。
3. 每个模板必须包含“动作后校验”；未通过即失败。
4. 当模板步骤可提前确定时，优先将步骤组装为一次 `browser_run_plan` 调用执行。

## 模板矩阵

### A. 日期范围模板

- 输入：当期开始/结束、对比期开始/结束
- 序列：snapshot -> 锚定区块 -> click(start input) -> click(start day) -> click(end day) -> wait -> snapshot
- 验收：四个值全部命中目标；输出填前/填后对照

### B. 单选下拉模板

- 输入：字段名、目标值
- 序列：snapshot -> 锚定区块 -> click(select) -> snapshot -> click(option ref) -> wait
- 验收：字段展示值 == 目标值

### C. 多选下拉模板

- 输入：字段名、目标值集合
- 序列：snapshot -> click(multi-select) -> 逐项 click(option ref) -> esc/点空白关闭 -> snapshot
- 验收：已选集合与目标集合一致

### D. 复选组模板

- 输入：目标勾选集合
- 序列：snapshot -> 比较当前状态 -> 仅点击差异项 -> wait -> snapshot
- 验收：`aria-checked` 或样式状态全部匹配

### E. 查询按钮模板

- 输入：目标区块锚点
- 序列：snapshot -> 区块内取查询按钮 ref -> click(ref) -> wait(1~2s) -> snapshot
- 验收：结果区至少出现一个变化信号

### F. 表格读取模板

- 输入：目标表名或区块锚点
- 序列：snapshot -> 定位表头 -> 读取行 -> 结构化输出
- 验收：列头完整、行结构完整、无空读

### G. 分页采集模板

- 输入：最大页数/停止条件
- 序列：读取当前页 -> click(next) -> wait -> snapshot -> 读取下一页（循环）
- 验收：页码递增；连续两页内容相同则停止并上报

### H. 下载落盘模板

- 输入：下载入口、文件关键字、下载目录
- 序列：触发下载 -> 记录 t0 -> 轮询本地目录 -> 命中目标文件
- 验收：`mtime >= t0` 且 `size > 0`

## Token 控制约束

- 普通路径：每阶段默认 1 次 snapshot。
- 失败诊断：允许补 1 次 snapshot 或 1 次 screenshot。
- 禁止把 screenshot base64 写入模型上下文。

## 返回格式（建议）

- `step`: 当前步骤名
- `target`: 控件/区块标识
- `before`: 操作前关键值
- `after`: 操作后关键值
- `verified`: `true/false`
- `evidence`: 最小必要证据（值、计数、页码、时间戳）
