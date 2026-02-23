---
name: pandas-analysis
description: >-
  数据分析与可视化引擎。使用 pandas 进行数据清洗、聚合、统计分析，
  使用 matplotlib/seaborn 生成图表。适合数据探索、趋势分析、可视化图表生成。
  处理大文件（>10MB）时，应先用 duckdb-analysis 做 SQL 预筛选，再用本 Skill 做可视化。
metadata:
  author: MyClaw (adapted from SkillMD data-analysis)
  version: "1.0.0"
  tags: [python, pandas, data-analysis, visualization, matplotlib, seaborn]
---

# Pandas 数据分析与可视化 Skill

使用 `python_executor` 执行 pandas 数据分析和 matplotlib/seaborn 可视化代码。

## 调用方式

通过 `python_executor` 执行 Python 代码。所有图表保存到 `output/` 目录。

## 分析工作流

1. **加载数据** — 用 pandas 读取 CSV/Excel 文件
2. **探索数据** — 查看结构、类型、缺失值、基本统计
3. **清洗数据** — 处理缺失值、重复值、异常值
4. **分析数据** — 分组聚合、相关性、趋势
5. **可视化** — 用 matplotlib/seaborn 生成图表
6. **输出报告** — 总结发现并给出建议

## 代码模板

### 加载数据与基本探索

```python
import pandas as pd

df = pd.read_csv('test_data/sample_sales.csv')

print(f"数据形状: {df.shape}")
print(f"列名: {list(df.columns)}")
print()
print("数据类型:")
print(df.dtypes)
print()
print("前 5 行:")
print(df.head())
print()
print("统计摘要:")
print(df.describe())
```

### 加载 Excel 文件

```python
import pandas as pd

df = pd.read_excel('data.xlsx', sheet_name='Sheet1')
print(df.head())
```

### 缺失值处理

```python
import pandas as pd

df = pd.read_csv('data.csv')

# 检查缺失值
print("缺失值统计:")
print(df.isnull().sum())

# 删除缺失行
df_clean = df.dropna()

# 或用均值填充数值列
df_filled = df.fillna(df.select_dtypes(include='number').mean())
```

### 分组聚合

```python
import pandas as pd

df = pd.read_csv('test_data/sample_sales.csv')

summary = df.groupby('product').agg(
    total_revenue=('revenue', 'sum'),
    avg_revenue=('revenue', 'mean'),
    count=('revenue', 'count')
).sort_values('total_revenue', ascending=False)

print(summary)
```

### 相关性分析

```python
import pandas as pd

df = pd.read_csv('data.csv')
correlation = df.select_dtypes(include='number').corr()
print(correlation)
```

### 透视表

```python
import pandas as pd

df = pd.read_csv('test_data/sample_sales.csv')

pivot = pd.pivot_table(
    df,
    values='revenue',
    index='region',
    columns='product',
    aggfunc='sum',
    fill_value=0
)
print(pivot)
```

## 可视化模板

### 中文字体配置（必须）

在 Windows 环境中绘图时，必须先配置中文字体：

```python
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False
```

### 柱状图

```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')

data = df.groupby('product')['revenue'].sum().sort_values(ascending=False)

plt.figure(figsize=(10, 6))
data.plot(kind='bar', color='steelblue', edgecolor='black')
plt.title('各产品销售额', fontsize=14, fontweight='bold')
plt.xlabel('产品')
plt.ylabel('总销售额')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('output/bar_chart.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/bar_chart.png")
```

### 折线图（时间序列）

```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')
df['date'] = pd.to_datetime(df['date'])
monthly = df.set_index('date').resample('M')['revenue'].sum()

plt.figure(figsize=(12, 6))
plt.plot(monthly.index, monthly.values, marker='o', linewidth=2, markersize=4)
plt.title('月度销售趋势', fontsize=14, fontweight='bold')
plt.xlabel('月份')
plt.ylabel('销售额')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('output/line_chart.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/line_chart.png")
```

### 饼图

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')
data = df.groupby('region')['revenue'].sum()

plt.figure(figsize=(8, 8))
plt.pie(data, labels=data.index, autopct='%1.1f%%', startangle=90,
        colors=sns.color_palette('pastel'))
plt.title('各区域销售占比', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('output/pie_chart.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/pie_chart.png")
```

### 直方图

```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')

plt.figure(figsize=(10, 6))
plt.hist(df['revenue'], bins=20, color='steelblue', edgecolor='black', alpha=0.7)
plt.title('销售额分布', fontsize=14, fontweight='bold')
plt.xlabel('销售额')
plt.ylabel('频次')
mean_val = df['revenue'].mean()
plt.axvline(mean_val, color='red', linestyle='--', label=f'均值: {mean_val:,.0f}')
plt.legend()
plt.tight_layout()
plt.savefig('output/histogram.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/histogram.png")
```

### 热力图（相关性矩阵）

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('data.csv')
correlation = df.select_dtypes(include='number').corr()

plt.figure(figsize=(10, 8))
sns.heatmap(correlation, annot=True, cmap='coolwarm', center=0,
            fmt='.2f', square=True, linewidths=0.5)
plt.title('相关性矩阵', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('output/heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/heatmap.png")
```

### 散点图

```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')

plt.figure(figsize=(10, 6))
plt.scatter(df['quantity'], df['revenue'], alpha=0.6, c='steelblue')
plt.title('数量与销售额关系', fontsize=14, fontweight='bold')
plt.xlabel('数量')
plt.ylabel('销售额')
plt.tight_layout()
plt.savefig('output/scatter.png', dpi=150, bbox_inches='tight')
plt.close()
print("图表已保存: output/scatter.png")
```

### 组合仪表盘（多子图）

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('test_data/sample_sales.csv')
df['date'] = pd.to_datetime(df['date'])

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 柱状图
df.groupby('product')['revenue'].sum().sort_values(ascending=False).plot(
    kind='bar', ax=axes[0, 0], color='steelblue')
axes[0, 0].set_title('各产品销售额')
axes[0, 0].tick_params(axis='x', rotation=45)

# 折线图
df.set_index('date').resample('M')['revenue'].sum().plot(ax=axes[0, 1], marker='o')
axes[0, 1].set_title('月度销售趋势')

# 直方图
axes[1, 0].hist(df['revenue'], bins=15, color='green', alpha=0.7, edgecolor='black')
axes[1, 0].set_title('销售额分布')

# 箱线图
df.boxplot(column='revenue', by='region', ax=axes[1, 1])
axes[1, 1].set_title('各区域销售额')
plt.suptitle('')

plt.tight_layout()
plt.savefig('output/dashboard.png', dpi=150, bbox_inches='tight')
plt.close()
print("仪表盘已保存: output/dashboard.png")
```

## 数据导出

### 导出为 Excel（多 Sheet）

```python
import pandas as pd

df = pd.read_csv('data.csv')

with pd.ExcelWriter('output/analysis_report.xlsx') as writer:
    df.to_excel(writer, sheet_name='原始数据', index=False)
    df.describe().to_excel(writer, sheet_name='统计摘要')
    df.groupby('category')['value'].sum().to_excel(writer, sheet_name='分类汇总')

print("Excel 报告已保存: output/analysis_report.xlsx")
```

### 导出为 CSV

```python
import pandas as pd

df = pd.read_csv('data.csv')
result = df.groupby('category').agg({'value': 'sum'}).reset_index()
result.to_csv('output/summary.csv', index=False, encoding='utf-8-sig')
print("CSV 已保存: output/summary.csv")
```

## 大文件处理技巧

**重要：数据文件 >10MB 时，必须先用 `duckdb-analysis` Skill 做 SQL 预筛选/聚合，将结果导出为小文件后再用 pandas 处理。** DuckDB 使用列存引擎，无需将全部数据加载到内存，是大数据的最佳入口。

小文件的优化技巧：
- 用 `nrows` 参数预览：`pd.read_csv('data.csv', nrows=100)`
- 用 `usecols` 只加载需要的列：`pd.read_csv('data.csv', usecols=['col1', 'col2'])`
- 用 `chunksize` 分块处理：

```python
import pandas as pd

chunks = pd.read_csv('data.csv', chunksize=10000)
total = 0
for chunk in chunks:
    total += chunk['value'].sum()
print(f"Total: {total}")
```

## 环境说明

- pandas、matplotlib、seaborn、openpyxl 已安装在虚拟环境中
- 文件路径相对于 backend 工作目录（`e:\myclaw\backend`）
- 图表和报告保存到 `output/` 目录
- Windows 环境下绘图必须设置中文字体（见上方模板）
