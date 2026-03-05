#!/usr/bin/env python3
"""
从 Alpha BI 页面 snapshot 提取表名清单。

前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
流程：调用 snapshot API → 解析 snapshot_text → 输出 tables.json 和 docs/alpha-bi-tables.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

DEFAULT_BASE = "http://127.0.0.1:8000"
SNAPSHOT_URL = "/api/browser/jobs/alpha-bi/snapshot"

# 表名模式：✔ [xxx]-yyy、图N：xxx、[xxx]-yyy
TABLE_PATTERNS = [
    re.compile(r"✔\s*\[([^\]]+)\]-([^\s\n]+)"),  # ✔ [贡献拆解1]-商品分类
    re.compile(r"图\s*\d+\s*[：:]\s*([^\s\n]+)"),  # 图1：xxx
    re.compile(r"\[([^\]]+)\]-([^\s\n]+)"),       # [贡献拆解1]-商品分类（无✔）
]

# 区块标题模式
BLOCK_PATTERNS = [
    re.compile(r"[一二三四五六七八九十]+、([^\s\n]+)"),  # 一、核心指标 二、问题定位
    re.compile(r"▌\s*([^\s\n]+)"),  # ▌二、问题定位
]

KNOWN_BLOCKS = [
    "一、核心指标",
    "二、问题定位",
    "三、归因分析V1",
    "归因分析V2",
    "毛利趋势",
]

# Tab 文案模式（Ant Design Tabs 常见形态）
TAB_PATTERNS = [
    re.compile(r"经营结果\s*\(主站\)"),
    re.compile(r"过程表现\s*\(主站\)"),
    re.compile(r"三方判断"),
    re.compile(r"([^\s]+)\s*\(主站\)"),  # 通用 (主站) 后缀
]


def extract_tabs_from_text(text: str) -> list[str]:
    """从 snapshot 文本提取 Tab 文案列表。"""
    seen: set[str] = set()
    tabs: list[str] = []
    for pat in TAB_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(0).strip()
            norm = re.sub(r"\s+", "", raw)
            if norm in seen:
                continue
            seen.add(norm)
            tabs.append(raw)
    return tabs


def fetch_snapshot(base: str = DEFAULT_BASE, wait_ms: int = 25000) -> dict:
    """调用 snapshot API，返回 snapshot_text 和 elements。"""
    url = f"{base}{SNAPSHOT_URL}"
    payload = {"wait_after_navigate_ms": wait_ms, "mode": "full"}
    resp = requests.post(url, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"snapshot API failed: HTTP {resp.status_code}\n{resp.text}")
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"snapshot failed: {data.get('message', 'unknown')}")
    return data


def extract_tables_from_text(text: str) -> list[dict]:
    """
    从 snapshot 文本提取表名及所属区块。
    返回 [{"name": str, "block": str | None, "raw": str}, ...]
    """
    tables: list[dict] = []
    seen: set[str] = set()

    # 先找区块边界，粗略按顺序划分
    block_ranges: list[tuple[int, int, str]] = []
    for m in re.finditer(r"[一二三四五六七八九十]+、[^\s\n]+|▌\s*[^\s\n]+", text):
        block_ranges.append((m.start(), m.end(), m.group(0).strip()))
    block_ranges.sort(key=lambda x: x[0])

    def block_at(pos: int) -> str | None:
        for i, (start, end, name) in enumerate(block_ranges):
            if start <= pos < end:
                return name
            if i + 1 < len(block_ranges) and end <= pos < block_ranges[i + 1][0]:
                return name
        if block_ranges:
            return block_ranges[-1][2]
        return None

    for pattern in TABLE_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0).strip()
            if raw in seen:
                continue
            seen.add(raw)
            if pattern == TABLE_PATTERNS[0]:
                name = f"✔ [{m.group(1)}]-{m.group(2)}"
            elif pattern == TABLE_PATTERNS[1]:
                name = f"图：{m.group(1)}"
            else:
                name = f"[{m.group(1)}]-{m.group(2)}"
            block = block_at(m.start())
            tables.append({"name": name, "block": block, "raw": raw})

    return tables


def main() -> int:
    base = DEFAULT_BASE
    snapshot_file: str | None = None
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for a in sys.argv[1:]:
        if a.startswith("--snapshot-file="):
            snapshot_file = a.split("=", 1)[1].strip()
        elif a.startswith("--base="):
            base = a.split("=", 1)[1].rstrip("/")

    if args:
        base = args[0].rstrip("/")

    if snapshot_file:
        with open(snapshot_file, encoding="utf-8") as f:
            data = json.load(f)
        text = data.get("snapshot_text") or data.get("text") or ""
        if not text and isinstance(data, dict):
            payload = data.get("payload") or {}
            snap = payload.get("snapshot") or {}
            text = str(snap.get("text", ""))
    else:
        try:
            data = fetch_snapshot(base=base)
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1
        text = data.get("snapshot_text") or ""
    if not text:
        print("[WARN] snapshot_text is empty", file=sys.stderr)

    tables = extract_tables_from_text(text)
    tabs = extract_tabs_from_text(text)
    if not tabs:
        tabs = ["经营结果(主站)", "过程表现(主站)"]  # 默认占位

    # 输出 tables.json
    project_root = Path(__file__).resolve().parent.parent
    tables_json_path = project_root / "backend" / "memory" / "alpha_bi_tables.json"
    tables_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tables_json_path, "w", encoding="utf-8") as f:
        json.dump({"tables": tables, "tabs": tabs, "snapshot_preview_len": len(text)}, f, ensure_ascii=False, indent=2)
    print(f"[OK] wrote {tables_json_path} ({len(tables)} tables, {len(tabs)} tabs)")

    # 输出 backend/skills/alpha-bi-browser/reference/tabs.md
    skill_ref = project_root / "backend" / "skills" / "alpha-bi-browser" / "reference"
    skill_ref.mkdir(parents=True, exist_ok=True)
    tabs_md_path = skill_ref / "tabs.md"
    tabs_lines = [
        "# Alpha BI Tab 区块",
        "",
        "从 snapshot 提取，供 click-tab Job 使用。",
        "",
        "## Tab 文案列表",
        "",
        "| Tab 文案 | 说明 |",
        "|----------|------|",
    ]
    for t in tabs:
        tabs_lines.append(f"| {t} | 待补充 |")
    tabs_lines.extend([
        "",
        "## 提取说明",
        "",
        "- 运行 `python scripts/extract_alpha_bi_tables.py` 可刷新",
        "",
    ])
    with open(tabs_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tabs_lines))
    print(f"[OK] wrote {tabs_md_path}")

    # 输出 docs/alpha-bi-tables.md
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    md_path = docs_dir / "alpha-bi-tables.md"
    lines = [
        "# Alpha BI 表名清单",
        "",
        "从 snapshot 提取，供 locate-table、测试清单等使用。",
        "",
        "## 表名及所属区块",
        "",
        "| 表名 | 所属区块 |",
        "|------|----------|",
    ]
    for t in tables:
        block = t.get("block") or "-"
        lines.append(f"| {t['name']} | {block} |")
    lines.extend(["", "## 提取说明", "", "- 模式：`✔ [xxx]-yyy`、`图N：xxx`、`[xxx]-yyy`", ""])
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] wrote {md_path}")

    # 生成逐表逐组件测试清单 alpha-bi-test-checklist.md
    checklist_path = docs_dir / "alpha-bi-test-checklist.md"
    checklist_lines = [
        "# Alpha BI 逐表逐组件测试清单",
        "",
        "snapshot 获取成功后生成，严格按此清单执行测试。",
        "",
        "| 表名 | 组件类型 | 测试项 | 状态 |",
        "|------|----------|--------|------|",
    ]
    for t in tables:
        name = t["name"]
        for row in [
            (name, "定位", "locate-table 能找到", "待测"),
            (name, "筛选项-日期", "date-filter 填写", "待测"),
            (name, "筛选项-品类组", "select-dropdown 填写", "待测"),
            (name, "筛选项-聚合维度", "select-dropdown 填写", "待测"),
            (name, "查询", "点击查询按钮", "待测"),
            (name, "完整路径", "full-filter-query（日期+品类组+聚合维度+查询）", "待测"),
            (name, "下载", "悬浮-原始数据-任务中心-下载", "待测"),
        ]:
            checklist_lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    checklist_lines.extend([
        "",
        "## Tab 区块",
        "",
        "| 表名 | 组件类型 | 测试项 | 状态 |",
        "|------|----------|--------|------|",
    ])
    for tab_text in tabs:
        checklist_lines.append(f"| Tab 区块 | Tab 点击 | {tab_text} | 待测 |")
    checklist_lines.extend([
        "",
        "## 说明",
        "",
        "- 每项测完更新状态为「通过」或「失败」",
        "- 多表共用的筛选项组只列一次（标注「共用」）",
        "",
    ])
    with open(checklist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checklist_lines))
    print(f"[OK] wrote {checklist_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
