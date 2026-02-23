---
name: report-export
description: >-
  生成专业的数据分析报告，支持 HTML 网页格式输出。将数据转化为包含 KPI 卡片、
  图表、表格和洞察分析的精美报告。适用于：数据报告、销售分析、KPI 仪表板、
  分析报告导出、报告交付。
metadata:
  author: MyClaw (adapted from ClawHub openclaw/report-generator)
  version: "1.0.0"
  tags: [report, visualization, charts, data, html, export, dashboard]
---

# Report Generator 报告生成器

生成专业的数据分析报告，输出为自包含的 HTML 网页文件（图表以 base64 内嵌，无外部依赖）。

## 调用方式

使用 `python_executor` 执行 Python 代码。**一次调用完成全部操作**。

## 报告结构

一份完整的报告应包含以下部分：

1. **标题和元信息**（报告名称、日期、数据周期）
2. **执行摘要 / KPI 卡片**（核心指标一目了然）
3. **详细分析章节**（每个章节包含文字分析 + 对应图表）
4. **数据表格**（关键数据的结构化展示）
5. **结论与建议**

## 核心原则：图文混排

**每个分析章节的图表必须紧跟其文字描述**，不要将所有图表集中到末尾。
图表通过 matplotlib 生成后，以 base64 编码直接嵌入 HTML，确保报告文件独立可查看。

## HTML 报告模板

以下是完整的报告生成代码模板，请根据实际数据调整：

```python
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import base64
import io
import os
from datetime import datetime

# ── 中文字体配置 ──
for font_name in ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']:
    if any(font_name in f.name for f in fm.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [font_name]
        break
plt.rcParams['axes.unicode_minus'] = False

# ── 工具函数 ──
def fig_to_base64(fig):
    """将 matplotlib figure 转为 base64 字符串"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return f'data:image/png;base64,{b64}'

def kpi_card(label, value, sub="", color="#2563eb"):
    """生成单个 KPI 卡片 HTML"""
    return f'''
    <div class="kpi-card">
      <div class="kpi-value" style="color:{color}">{value}</div>
      <div class="kpi-label">{label}</div>
      {"<div class='kpi-sub'>" + sub + "</div>" if sub else ""}
    </div>'''

def section(title, text="", chart_b64="", table_html=""):
    """生成一个分析章节 HTML（文字 + 图表 + 表格混排）"""
    html = f'<div class="section"><h2>{title}</h2>'
    if text:
        html += f'<div class="section-text">{text}</div>'
    if chart_b64:
        html += f'<div class="chart-container"><img src="{chart_b64}" alt="{title}"></div>'
    if table_html:
        html += f'<div class="table-container">{table_html}</div>'
    html += '</div>'
    return html

# ══════════════════════════════════════
# 以下根据实际数据修改
# ══════════════════════════════════════

# ── 1. 加载数据 ──
df = pd.read_csv("YOUR_DATA_FILE.csv")  # 替换为实际数据路径

# ── 2. 计算核心 KPI（根据数据字段调整） ──
# 根据实际数据的列名和业务含义，计算 3-5 个关键指标
kpi_html = '<div class="kpi-row">'
# kpi_html += kpi_card("指标名称", "指标值")
# kpi_html += kpi_card("指标名称", "指标值", color="#10b981")
kpi_html += '</div>'

# ── 3. 各分析章节（图文混排） ──
sections_html = ""

# 每个章节：文字洞察 + 对应图表，根据数据特点自行设计
# fig, ax = plt.subplots(figsize=(10, 5))
# ... 绘图代码 ...
# chart = fig_to_base64(fig)
# sections_html += section("章节标题", "<p>分析文字</p>", chart)

# ── 4. 组装完整 HTML ──
CSS = """
:root { --primary: #1e40af; --accent: #3b82f6; --text: #1f2937; --bg: #f8fafc;
        --surface: #ffffff; --border: #e2e8f0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', -apple-system, sans-serif; background: var(--bg);
       color: var(--text); line-height: 1.6; }
.container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
h1 { font-size: 2em; color: var(--primary); margin-bottom: 4px; }
.subtitle { color: #64748b; font-size: 0.95em; margin-bottom: 24px; }
h2 { font-size: 1.4em; color: var(--primary); margin: 32px 0 12px;
     padding-left: 12px; border-left: 4px solid var(--accent); }
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           gap: 16px; margin: 24px 0; }
.kpi-card { background: var(--surface); border-radius: 12px; padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid var(--border); }
.kpi-value { font-size: 1.8em; font-weight: 700; }
.kpi-label { color: #64748b; font-size: 0.9em; margin-top: 4px; }
.kpi-sub { color: #94a3b8; font-size: 0.8em; }
.section { background: var(--surface); border-radius: 12px; padding: 24px;
           margin: 20px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
           border: 1px solid var(--border); }
.section-text { margin: 8px 0 16px; }
.section-text p { margin: 6px 0; }
.chart-container { text-align: center; margin: 16px 0; }
.chart-container img { max-width: 100%; border-radius: 8px; }
.table-container { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; width: 100%; font-size: 0.92em; }
th { background: linear-gradient(135deg, #eff6ff, #dbeafe); color: var(--primary);
     font-weight: 600; padding: 10px 14px; text-align: left; border: 1px solid var(--border); }
td { padding: 10px 14px; border: 1px solid var(--border); }
tr:nth-child(even) { background: #f8fafc; }
tr:hover { background: #eff6ff; }
footer { text-align: center; color: #94a3b8; font-size: 0.85em;
         margin-top: 40px; padding: 20px; border-top: 1px solid var(--border); }
"""

report_title = "数据分析报告"  # 替换为实际报告标题
today = datetime.now().strftime("%Y-%m-%d")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{report_title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <h1>{report_title}</h1>
  <div class="subtitle">生成日期: {today} | MyClaw Agent 自动生成</div>
  {kpi_html}
  {sections_html}
</div>
<footer>Generated by MyClaw Agent &middot; Powered by AI</footer>
</body>
</html>"""

# ── 5. 保存 ──
output_path = "output/report.html"
os.makedirs("output", exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✓ 报告已生成: {os.path.abspath(output_path)}")
```

## 关键设计要点

### 图文混排
每个 `section()` 调用将文字分析、图表、表格组合在一起，确保内容与可视化紧密关联，不会出现"文字在上面、图表全在下面"的问题。

### 图表 base64 内嵌
使用 `fig_to_base64()` 将 matplotlib 图表转为 base64 PNG，直接嵌入 HTML `<img>` 标签。报告文件完全独立，无需任何外部图片文件。

### KPI 卡片
使用 CSS Grid 布局的响应式 KPI 卡片行，一目了然展示核心指标。

### 自适应中文字体
自动检测系统可用的中文字体（Microsoft YaHei → SimHei → WenQuanYi），确保图表中文正确显示。

## 使用指引

1. Agent 分析完数据后，根据分析结果使用此模板生成报告
2. 根据数据特点添加/删除章节（产品分析、区域分析、趋势分析、渠道分析等）
3. 每个章节都应包含：文字洞察 + 对应图表
4. 所有代码作为一次 `python_executor` 调用执行
5. 最终输出：`output/report.html`

## 可选：清理中间产物

如果之前已生成了独立的 .md 和 .png 文件，可在报告生成后添加清理代码：

```python
import glob
for f in glob.glob("output/*.md") + glob.glob("output/*.png"):
    os.remove(f)
    print(f"  已清理: {f}")
```
