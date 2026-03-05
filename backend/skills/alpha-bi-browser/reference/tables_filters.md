# Alpha BI 表-筛选项映射

表 → 其筛选项列表。多表共用的选项组标注「共用」。数据来源：snapshot 分析，运行 `extract_alpha_bi_tables.py` 可刷新表名后补充。

## 二、问题定位 区块

| 表名 | 筛选项 | 类型 | 共用 |
|------|--------|------|------|
| ✔ [贡献拆解1]-商品分类 | 日期（当期/对比期） | date-range-picker | 是 |
| ✔ [贡献拆解1]-商品分类 | 品类组 | single-select | 是 |
| ✔ [贡献拆解1]-商品分类 | 聚合维度 | single-select | 是 |
| ✔ [过程拆解2]-补充订单&用户 | 日期（当期/对比期） | date-range-picker | 是 |
| ✔ [过程拆解2]-补充订单&用户 | 品类组 | single-select | 是 |
| ✔ [过程拆解2]-补充订单&用户 | 聚合维度 | single-select | 是 |

## 填写顺序建议

1. 日期（当期/对比期）→ date-filter Job
2. 品类组 → select-dropdown Job，`within: { text: "二、问题定位" }`，index 0
3. 聚合维度 → select-dropdown Job，`within: { text: "二、问题定位" }`，index 1
4. 点击查询 → 区块内查询按钮

## 完整路径 Job

- `POST /api/browser/jobs/alpha-bi/full-filter-query`
- 请求：`{ url?, wait_after_navigate_ms?, category_value?, dimension_value?, post_query_wait_ms? }`
- 逻辑：date-filter → select-dropdown 品类组 → select-dropdown 聚合维度 → click 查询

## 多选/复选（若存在）

- 大区、城市：multi-select（若存在）
- 采一/采二/采三：checkbox-group（若存在）

待 snapshot 解析后补充。
