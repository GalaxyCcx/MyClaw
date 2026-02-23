---
name: duckdb-analysis
description: >-
  大数据 SQL 查询与预处理引擎。当数据文件较大（>10MB）、涉及多文件联合查询、
  Parquet 格式处理、或需要复杂 SQL（窗口函数/CTE/子查询）时，优先使用此 Skill。
  常与 pandas-analysis 配合：先用 DuckDB 做 SQL 预筛选和聚合，再交给 pandas 做可视化。
metadata:
  author: MyClaw (adapted from ClawHub openclaw/skills/duckdb-cli-ai-skills)
  version: "1.0.0"
  tags: [sql, data-analysis, duckdb, csv, parquet, json]
---

# DuckDB SQL 数据分析

通过 `python_executor` 使用 DuckDB Python API 执行 SQL 查询，可直接分析 CSV、Parquet、JSON 文件，无需预先加载到数据库中。

## 调用方式

使用 `python_executor` 执行 DuckDB Python 代码。基本模板：

```python
import duckdb

result = duckdb.sql("YOUR SQL HERE")
print(result)
```

## Quick Start

### 直接读取数据文件

```python
import duckdb

# CSV 文件
print(duckdb.sql("SELECT * FROM 'data.csv' LIMIT 10"))

# Parquet 文件
print(duckdb.sql("SELECT * FROM 'data.parquet'"))

# 多文件通配符
print(duckdb.sql("SELECT * FROM read_parquet('logs/*.parquet')"))

# JSON 文件
print(duckdb.sql("SELECT * FROM read_json_auto('data.json')"))
```

### 查看数据结构

```python
import duckdb

# 查看列名和类型
print(duckdb.sql("DESCRIBE SELECT * FROM 'data.csv'"))

# 查看前几行
print(duckdb.sql("SELECT * FROM 'data.csv' LIMIT 5"))

# 统计行数
print(duckdb.sql("SELECT COUNT(*) as total_rows FROM 'data.csv'"))
```

## 数据分析

### 快速统计

```python
import duckdb

print(duckdb.sql("""
    SELECT
        COUNT(*) as count,
        AVG(amount) as average,
        MIN(amount) as min_val,
        MAX(amount) as max_val,
        SUM(amount) as total
    FROM 'transactions.csv'
"""))
```

### 分组聚合

```python
import duckdb

print(duckdb.sql("""
    SELECT
        category,
        COUNT(*) as count,
        SUM(amount) as total,
        AVG(amount) as avg_amount
    FROM 'data.csv'
    GROUP BY category
    ORDER BY total DESC
"""))
```

### 多文件联合查询

```python
import duckdb

print(duckdb.sql("""
    SELECT a.*, b.name
    FROM 'orders.csv' a
    JOIN 'customers.csv' b ON a.customer_id = b.id
"""))
```

### 日期分析

```python
import duckdb

print(duckdb.sql("""
    SELECT
        strftime(date, '%Y-%m') as month,
        SUM(revenue) as monthly_revenue
    FROM 'sales.csv'
    GROUP BY month
    ORDER BY month
"""))
```

### 窗口函数

```python
import duckdb

print(duckdb.sql("""
    SELECT *,
        SUM(amount) OVER (PARTITION BY category ORDER BY date) as running_total,
        ROW_NUMBER() OVER (PARTITION BY category ORDER BY amount DESC) as rank
    FROM 'data.csv'
"""))
```

## 数据转换与导出

### CSV 转 Parquet

```python
import duckdb

duckdb.sql("COPY (SELECT * FROM 'input.csv') TO 'output/output.parquet' (FORMAT PARQUET)")
print("转换完成: output/output.parquet")
```

### Parquet 转 CSV

```python
import duckdb

duckdb.sql("COPY (SELECT * FROM 'input.parquet') TO 'output/output.csv' (HEADER, DELIMITER ',')")
print("转换完成: output/output.csv")
```

### 带过滤的导出

```python
import duckdb

duckdb.sql("""
    COPY (
        SELECT * FROM 'data.csv' WHERE amount > 1000
    ) TO 'output/filtered.parquet' (FORMAT PARQUET)
""")
print("带过滤导出完成")
```

### 导出为 JSON

```python
import duckdb

duckdb.sql("COPY (SELECT * FROM 'data.csv') TO 'output/output.json' (FORMAT JSON, ARRAY true)")
print("导出 JSON 完成")
```

## 输出格式控制

DuckDB 的 `print()` 默认输出 ASCII 表格。也可以通过 `fetchdf()` 转为 pandas DataFrame：

```python
import duckdb

# 默认表格输出
print(duckdb.sql("SELECT * FROM 'data.csv' LIMIT 10"))

# 转为 pandas DataFrame（更多格式控制）
df = duckdb.sql("SELECT * FROM 'data.csv'").fetchdf()
print(df.to_string())

# 输出为 Markdown 表格
print(df.to_markdown())
```

## 持久化数据库

```python
import duckdb

# 创建/打开数据库文件
conn = duckdb.connect('output/my_analysis.duckdb')

# 从 CSV 创建表
conn.sql("CREATE TABLE IF NOT EXISTS sales AS SELECT * FROM 'sales.csv'")

# 后续查询
print(conn.sql("SELECT COUNT(*) FROM sales"))

# 追加数据
conn.sql("INSERT INTO sales SELECT * FROM 'sales_2025.csv'")

conn.close()
```

## 大文件处理技巧

- 对大文件先用 `LIMIT` 预览：`SELECT * FROM 'big.csv' LIMIT 10`
- 用 `DESCRIBE` 查看结构而非读取全部数据
- 优先使用 Parquet 格式，比 CSV 快且占用更少 I/O
- 用 `read_csv_auto` / `read_json_auto` 自动推断列类型
- 导出分析结果到小文件，避免大结果集输出到 stdout

## 环境说明

- DuckDB 已安装在虚拟环境中，可直接 `import duckdb` 使用
- 文件路径相对于 backend 工作目录（`e:\myclaw\backend`）
- 导出文件建议放到 `output/` 目录
