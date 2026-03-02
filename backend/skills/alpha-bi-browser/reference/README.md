# Alpha BI 组件参考索引

本目录用于沉淀 Alpha BI 页面常见组件的可复用操作策略。  
主流程请参考上级 `SKILL.md`，组件细节按需读取对应文档。

## 组件清单

- 日期范围选择器：`date-range-picker.md`
- 单选下拉组件：`single-select.md`
- 多选下拉组件：`multi-select.md`
- 复选框组组件：`checkbox-group.md`
- 查询按钮组件：`query-button.md`
- 表格与分页组件：`table-pagination.md`
- 通用异常恢复：`error-recovery.md`

## 使用顺序建议

1. 先读 `date-range-picker.md`（最容易失败的环节）
2. 再读 `single-select.md`（多同名字段时最易串位）
3. 根据筛选需求读取多选/复选文档
3. 查询后读取 `table-pagination.md`
4. 任何异常统一回看 `error-recovery.md`

## 速度优化清单

- 每个阶段先定义“目标状态”，未达成不进入下一阶段。
- 单阶段默认 1 次 snapshot，校验失败才补第 2 次。
- 优先短链路操作：定位 -> 点击 -> 校验，避免重复开关组件。
- 二级页面优先“提取 URL + browser_navigate”，避免点击触发新开 tab。
- 对同名字段先做区块锚定（尤其“品类组”“查询”）。
- 单步最多失败 2 次，超过就切换策略或终止上报。

## 键盘兜底何时启用

- 单选下拉点击后展示值不匹配目标值
- option ref 多次变化导致点击结果不稳定
- 虚拟列表滚动时相邻项误选频繁

启用后按 `single-select.md` 的“键盘兜底模板（固定序列）”执行。

## 维护约定

- 新组件新增一个独立 markdown 文件，不在本文件堆叠细节。
- 组件文档统一包含：识别特征、标准步骤、备用策略、失败信号。
- 仅保留稳定策略，删除临时页面特化选择器。
