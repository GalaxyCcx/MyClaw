# Alpha BI 表清单与定位路径

表名清单、所属区块、定位路径。数据来源：`docs/alpha-bi-tables.md`、`backend/memory/alpha_bi_tables.json`。

## 表名清单与所属区块

| 表名 | 所属区块 |
|------|----------|
| ✔ [贡献拆解1]-商品分类 | 二、问题定位 |
| ✔ [过程拆解2]-补充订单&用户 | 二、问题定位 |

## 定位路径

1. **snapshot 校验**：调用 `locate-table` Job，传入 `table_keyword`，校验该关键字是否出现在 snapshot.text 中。
2. **区块锚定**：若需在表区块内操作（筛选项、查询、下载），使用 `within: { text: "<区块标题>" }`，如 `within: { text: "二、问题定位" }`。
3. **Job**：`POST /api/browser/jobs/alpha-bi/locate-table`，请求 `{ table_keyword: str, url?: str }`，返回 `{ ok, found, block_hint, actions_log }`。

## 二、问题定位 筛选项路径

| 筛选项 | Job | 定位 |
|--------|-----|------|
| 日期 | date-filter | 共用，alpha_bi_set_date_ranges |
| 品类组 | select-dropdown | `within: { text: "二、问题定位" }`，`.ant-select` index 0 |
| 聚合维度 | select-dropdown | `within: { text: "二、问题定位" }`，`.ant-select` index 1 |
| 查询 | 点击 | `locate({ text: "查询", within: { text: "二、问题定位" } })` |
| 完整路径 | full-filter-query | `POST /api/browser/jobs/alpha-bi/full-filter-query` 串链 |

## 提取与刷新

运行 `python scripts/extract_alpha_bi_tables.py` 可从 live snapshot 刷新表名清单。
