# PRD v5 — 报告导出与 Skill 匹配优化

## 1. 背景

### 1.1 报告产物散落，无法直接交付

当前数据分析流程产出的是一个 Markdown 文件和多张独立 PNG 图片，存放于 `backend/output/` 目录。用户无法将这些散落文件直接发送给他人或用于汇报，需要手动整合。

### 1.2 Deep Research Skill 匹配率低

`deep-research` skill 的 description 使用了 "多源深度研究 agent"、"交叉验证" 等偏实现细节的表述，与用户自然语言（"帮我调研一下"、"写份报告"）匹配度不高，导致 Agent 跳过该 skill 直接即兴使用内置工具。

## 2. 功能需求

### 2.1 报告导出 Skill（report-export）

| 项目 | 说明 |
|------|------|
| 输入 | `output/` 目录下的 `.md` 报告文件 + `.png` 图表文件 |
| 输出 | `output/report.html`（网页版）+ `output/report.pptx`（演示文稿） |
| 后处理 | 导出完成后删除中间产物（`.md` 和 `.png` 文件），仅保留最终交付物 |

详细要求：

1. **HTML 网页版**：自带样式，浏览器直接打开即可查看，图表内嵌
2. **PPTX 演示文稿**：PowerPoint 可直接打开，包含报告内容和图表
3. **中间产物清理**：导出成功后，自动删除 `output/` 中的 `.md` 文件和 `.png` 文件
4. **图片嵌入**：在导出前，将独立的 PNG 图片以 Markdown 图片语法插入报告内容中

### 2.2 Deep Research Skill 描述优化

将 description 改为用户视角的自然语言，覆盖更多常见请求表述（"调研"、"报告"、"对比"、"评估"等），提高 Agent 的语义匹配命中率。

## 3. 技术方案

### 3.1 report-export Skill

- **类型**：纯文档 Skill（无自定义脚本）
- **执行器**：`python_executor`
- **核心依赖**：`markdown`（MD→HTML）+ `python-pptx`（生成 PPTX）+ `pygments`（代码高亮）
- **工作流**：

```
扫描 output/ 目录
  → 找到 .md 报告 + .png/.jpg 图片
  → HTML 导出：markdown 库渲染 + 图片 base64 内嵌 + CSS 样式
  → PPTX 导出：python-pptx 逐章节生成幻灯片 + 嵌入图片
  → 删除 .md 和 .png 中间产物
```

注：原计划使用 `convert-markdown` 库，但其依赖 `weasyprint`（需要系统级 GTK/Pango），Windows 上不可用。
改用 `markdown` + `python-pptx` 直接实现，无系统依赖，跨平台兼容。

### 3.2 依赖管理

在 `backend/requirements-skills.txt` 中包含 `markdown`、`python-pptx`、`pygments`，通过虚拟环境安装。

### 3.3 deep-research 描述优化

仅修改 `SKILL.md` 的 YAML frontmatter description 字段，不改变文档正文的方法论内容。

## 4. 验收标准

### 用例 1：Deep Research 匹配

- 发送"帮我调研一下 AI Agent 框架的现状"
- 预期：Agent 调用 `read_skill_doc("deep-research")` 后再执行搜索

### 用例 2：报告导出

- 前置条件：`output/` 中存在 `.md` 报告和 `.png` 图片
- 发送"把分析报告导出成网页和PPT"
- 预期：
  - Agent 匹配到 `report-export` skill
  - 生成 `output/report.html` 和 `output/report.pptx`
  - 中间产物（`.md` + `.png`）被删除
  - HTML 浏览器可正常查看
  - PPTX PowerPoint 可正常打开
