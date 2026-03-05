# Alpha BI Jobs 状态

## 已测通

| Job | 脚本 | 说明 |
|-----|------|------|
| core-metrics-date-query | replay_alpha_bi_core_metrics_query.py | 日期选择 + 查询 |
| task-center-download | replay_alpha_bi_task_center_download.py | 任务中心下载 |
| download-problem-locator | replay_alpha_bi_problem_locator_download.py | 问题定位表下载 |

## 已有 Job（需验证）

| Job | 脚本 | 说明 |
|-----|------|------|
| snapshot | - | 提取表名/Tab |
| locate-table | replay_alpha_bi_locate_table.py | 表定位校验 |
| date-filter | replay_alpha_bi_date_filter.py | 日期范围选择 |
| select-dropdown | replay_alpha_bi_select_dropdown.py | 单选下拉 |
| select-multi-dropdown | - | 多选下拉 |
| select-checkbox-group | replay_alpha_bi_select_checkbox_group.py | 复选组 |
| full-filter-query | replay_alpha_bi_full_filter_query.py | 完整路径：日期+品类组+聚合维度+查询 |
| click-tab | replay_alpha_bi_click_tab.py | Tab 点击 |
| download | - | 单表下载 |
| download-preset | - | 预设下载 |
| locate-refresh-debug | - | 调试用 |

## 页面需要的动作（reference 定义）

| 动作类型 | reference | 对应 Job |
|----------|-----------|----------|
| 日期范围 | date-range-picker.md | date-filter ✓ |
| 单选下拉 | single-select.md | select-dropdown ✓ |
| 多选下拉 | multi-select.md | select-multi-dropdown ✓ |
| 复选组 | checkbox-group.md | select-checkbox-group ✓ |
| 完整路径 | tables_filters.md | full-filter-query ✓ |
| Tab 点击 | tabs.md | click-tab ✓ |
| 下载 | error-recovery.md | download, download-problem-locator ✓ |
