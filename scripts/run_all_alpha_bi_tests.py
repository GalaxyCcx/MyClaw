#!/usr/bin/env python3
"""
Alpha BI 全量测试脚本：按 checklist 顺序执行所有待测项。
前置：后端已启动，BROWSER_TRANSPORT=native_extension，v2 扩展已连接。
"""
from __future__ import annotations

import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
ALPHA_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
    "&dashboardId=d127af3f0bb3457287f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)

RESULTS: list[dict] = []


def post(path: str, payload: dict, timeout: int = 90) -> dict:
    r = requests.post(BASE + path, json=payload, timeout=timeout)
    return r.json() if r.status_code == 200 else {"ok": False, "error": f"HTTP {r.status_code}"}


def record(name: str, ok: bool, err: str | None = None):
    RESULTS.append({"name": name, "ok": ok, "error": err})
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" | {err}" if err else ""))


def click_tab(tab_text: str, within_text: str | None = None) -> dict:
    p = {"url": ALPHA_URL, "wait_after_navigate_ms": 10000, "tab_text": tab_text}
    if within_text:
        p["within_text"] = within_text
    return post("/api/browser/jobs/alpha-bi/click-tab", p)


def select_dropdown(within: str, index: int, target: str) -> dict:
    return post(
        "/api/browser/jobs/alpha-bi/select-dropdown",
        {
            "url": ALPHA_URL,
            "wait_after_navigate_ms": 12000,
            "trigger_locator": {"selector": ".ant-select", "within": {"text": within}, "index": index},
            "target_value": target,
        },
    )


def download_table(within_text: str | None = None, icon_index: int | None = None) -> dict:
    """下载表：优先用 within_text 按区块定位，否则用 icon_index。"""
    payload = {"wait_after_navigate_ms": 25000}
    if within_text:
        payload["within_text"] = within_text
    else:
        payload["download_icon_index"] = icon_index or 1
    return post("/api/browser/jobs/alpha-bi/download-problem-locator", payload, timeout=240)


def locate_table(keyword: str) -> dict:
    return post(
        "/api/browser/jobs/alpha-bi/locate-table",
        {"url": ALPHA_URL, "wait_after_navigate_ms": 12000, "table_keyword": keyword},
    )


def date_filter() -> dict:
    from datetime import datetime
    import calendar
    now = datetime.now()
    start = f"{now.year:04d}-{now.month:02d}-01"
    end_day = calendar.monthrange(now.year, now.month)[1]
    end = f"{now.year:04d}-{now.month:02d}-{end_day:02d}"
    prev_month = now.month - 1 if now.month > 1 else 12
    prev_year = now.year if now.month > 1 else now.year - 1
    compare_start = f"{prev_year:04d}-{prev_month:02d}-01"
    compare_end_day = calendar.monthrange(prev_year, prev_month)[1]
    compare_end = f"{prev_year:04d}-{prev_month:02d}-{compare_end_day:02d}"
    return post(
        "/api/browser/jobs/alpha-bi/date-filter",
        {"url": ALPHA_URL, "current_start": start, "current_end": end, "compare_start": compare_start, "compare_end": compare_end, "wait_after_navigate_ms": 25000},
        timeout=120,
    )


def main() -> int:
    print("=== Alpha BI 全量测试 ===\n")

    # --- 一、核心指标 date-filter ---
    print("--- 一、核心指标 date-filter ---")
    d = date_filter()
    record("date-filter 当期~对比期", bool(d.get("ok")), d.get("error"))
    time.sleep(2)

    # --- 二、问题定位：贡献拆解1 全部筛选项 ---
    print("\n--- 贡献拆解1 地区/城市/采一/二/三/品牌/品种/SPU/经营状态/价值层级/价格带 ---")
    within = "二、问题定位"
    for name, idx, val in [
        ("贡献拆解1 地区", 1, "无限制"),
        ("贡献拆解1 城市", 2, "无限制"),
        ("贡献拆解1 采一", 4, "无限制"),
        ("贡献拆解1 采二", 5, "无限制"),
        ("贡献拆解1 采三", 6, "无限制"),
        ("贡献拆解1 品牌", 7, "无限制"),
        ("贡献拆解1 品种", 8, "无限制"),
        ("贡献拆解1 SPU", 9, "无限制"),
        ("贡献拆解1 经营状态", 10, "无限制"),
        ("贡献拆解1 价值层级", 11, "无限制"),
        ("贡献拆解1 价格带", 12, "无限制"),
    ]:
        d = select_dropdown(within, idx, val)
        record(name, bool(d.get("ok")), d.get("error"))
        time.sleep(1)

    # --- 三、归因分析V1 子 Tab ---
    print("\n--- 归因分析V1 子 Tab ---")
    d = click_tab("转化归因", within_text="归因分析V1")
    if not d.get("ok"):
        d = click_tab("经营结果→ 流量拆解→ 转化归因", within_text="归因分析V1")
    record("归因V1 Tab 经营结果→转化归因", bool(d.get("ok")), d.get("error"))
    time.sleep(1)
    d = click_tab("过程归因(自选指标)", within_text="归因分析V1")
    record("归因V1 Tab 过程归因(自选指标)", bool(d.get("ok")), d.get("error"))
    time.sleep(2)

    # 归因V1 经营结果→ 筛选项（在对应 Tab 区块内）
    print("\n--- 归因V1 经营结果→ 筛选项 ---")
    d = click_tab("转化归因", within_text="归因分析V1")
    if not d.get("ok"):
        d = click_tab("经营结果→ 流量拆解→ 转化归因", within_text="归因分析V1")
    if d.get("ok"):
        for name, idx, val in [
            ("归因V1 经营结果 聚合维度", 0, "品类组"),
            ("归因V1 经营结果 品类组", 1, "无限制"),
            ("归因V1 经营结果 采一", 2, "无限制"),
        ]:
            dd = select_dropdown("经营结果→", idx, val)
            record(name, bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)

    # --- 四、归因分析V2 子 Tab ---
    print("\n--- 归因分析V2 子 Tab ---")
    d = click_tab("转化归因", within_text="归因分析V2")
    if not d.get("ok"):
        d = click_tab("经营结果→ 流量拆解→ 转化归因", within_text="归因分析V2")
    record("归因V2 Tab 经营结果→转化归因", bool(d.get("ok")), d.get("error"))
    time.sleep(1)
    d = click_tab("过程归因(自选指标)", within_text="归因分析V2")
    record("归因V2 Tab 过程归因(自选指标)", bool(d.get("ok")), d.get("error"))
    time.sleep(2)

    # 归因V2 筛选项（经营结果→、过程归因）
    print("\n--- 归因V2 筛选项 ---")
    d = click_tab("转化归因", within_text="归因分析V2")
    if d.get("ok"):
        for name, idx, val in [
            ("归因V2 经营结果 聚合维度", 0, "品类组"),
            ("归因V2 经营结果 品类组", 1, "无限制"),
        ]:
            dd = select_dropdown("经营结果→", idx, val)
            record(name, bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)
    d = click_tab("过程归因(自选指标)", within_text="归因分析V2")
    if d.get("ok"):
        dd = select_dropdown("过程归因", 0, "无限制")
        record("归因V2 过程 地区", bool(dd.get("ok")), dd.get("error"))
        time.sleep(1)

    # 归因V1 过程归因 筛选项
    print("\n--- 归因V1 过程归因 筛选项 ---")
    d = click_tab("过程归因(自选指标)", within_text="归因分析V1")
    if d.get("ok"):
        for name, idx, val in [
            ("归因V1 过程 地区", 0, "无限制"),
            ("归因V1 过程 城市", 1, "无限制"),
            ("归因V1 过程 聚合维度", 2, "品类组"),
            ("归因V1 过程 品类组", 3, "无限制"),
        ]:
            dd = select_dropdown("过程归因", idx, val)
            record(name, bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)

    # --- 五、趋势分析 子 Tab + 各 Tab 筛选项 ---
    print("\n--- 趋势分析 4 子 Tab ---")
    for tab in ["经营结果", "流量拆解", "转化归因", "毛利趋势"]:
        d = click_tab(tab, within_text="四、趋势分析")
        record(f"趋势 Tab {tab}", bool(d.get("ok")), d.get("error"))
        time.sleep(2)

    # 趋势 毛利趋势 图1-4 聚合维度 日/周/月
    print("\n--- 趋势 图1-4 聚合维度 ---")
    d = click_tab("毛利趋势", within_text="四、趋势分析")
    if d.get("ok"):
        for name, within_block, idx, val in [
            ("图1 GMV 日", "图1：GMV", 0, "日"),
            ("图2 GMV拆解 周", "图2：GMV拆解", 0, "周"),
            ("图3 笔单价 月", "图3：品类笔单价", 0, "月"),
            ("图4 日用户 日", "图4：日用户", 0, "日"),
        ]:
            dd = select_dropdown(within_block, idx, val)
            record(name, bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)
        # 趋势 毛利趋势 筛选项（大区、城市、聚合维度、品类组）
        print("\n--- 趋势 毛利趋势 筛选项 ---")
        for name, idx, val in [
            ("趋势 大区", 0, "无限制"),
            ("趋势 城市", 1, "无限制"),
            ("趋势 聚合维度", 2, "品类组"),
            ("趋势 品类组", 3, "无限制"),
        ]:
            dd = select_dropdown("日期范围", idx, val)
            if not dd.get("ok"):
                dd = select_dropdown("图4", idx, val)
            record(name, bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)

    # 趋势 经营结果/流量拆解/转化归因 筛选项（各 Tab 下，within 用四、趋势分析或日期范围）
    print("\n--- 趋势 经营结果/流量拆解/转化归因 筛选项 ---")
    for tab in ["经营结果", "流量拆解", "转化归因"]:
        d = click_tab(tab, within_text="四、趋势分析")
        if d.get("ok"):
            dd = select_dropdown("四、趋势分析", 0, "无限制")
            if not dd.get("ok"):
                dd = select_dropdown("日期范围", 0, "无限制")
            record(f"趋势 {tab} 大区", bool(dd.get("ok")), dd.get("error"))
            time.sleep(1)

    # --- 六、明细数据 ---
    print("\n--- 明细数据 筛选项 ---")
    for name, idx, val in [
        ("明细 聚合维度", 0, "月"),
        ("明细 大区", 1, "无限制"),
        ("明细 城市", 2, "无限制"),
    ]:
        dd = select_dropdown("五、明细数据", idx, val)
        record(name, bool(dd.get("ok")), dd.get("error"))
        time.sleep(1)

    # 明细 定位
    print("\n--- 明细数据 定位 ---")
    d = locate_table("共")
    record("明细 定位", bool(d.get("ok") and d.get("found")), d.get("error"))

    # 明细 date-filter（复用核心指标 date-filter，页面可能共用）
    print("\n--- 明细数据 date-filter ---")
    d = date_filter()
    record("明细 date-filter", bool(d.get("ok")), d.get("error"))
    time.sleep(2)

    # 归因/趋势 各表 定位
    print("\n--- 归因V1 过程归因 定位 ---")
    d = click_tab("过程归因(自选指标)", within_text="归因分析V1")
    if d.get("ok"):
        dd = locate_table("共")
        record("归因V1 过程归因 定位", bool(dd.get("ok") and dd.get("found")), dd.get("error"))
        time.sleep(1)
    print("\n--- 趋势 经营结果 定位 ---")
    d = click_tab("经营结果", within_text="四、趋势分析")
    if d.get("ok"):
        dd = locate_table("共")
        record("趋势 经营结果 定位", bool(dd.get("ok") and dd.get("found")), dd.get("error"))
        time.sleep(1)

    # --- 下载（按 within_text 区块定位，避免全命中贡献拆解1）---
    print("\n--- 下载 各表（按区块）---")
    for name, within in [
        ("下载 贡献拆解1", "贡献拆解1"),
        ("下载 过程拆解2", "过程拆解2"),
        ("下载 归因分析V1", "归因分析V1"),
        ("下载 归因分析V2", "归因分析V2"),
        ("下载 趋势分析", "四、趋势分析"),
        ("下载 明细数据", "五、明细数据"),
    ]:
        d = download_table(within_text=within)
        record(name, bool(d.get("ok")), d.get("message") or d.get("error"))
        time.sleep(3)

    # --- 汇总 ---
    ok_count = sum(1 for r in RESULTS if r["ok"])
    fail_count = len(RESULTS) - ok_count
    print(f"\n=== 汇总: {ok_count}/{len(RESULTS)} 通过, {fail_count} 失败 ===")
    if fail_count:
        print("失败项:")
        for r in RESULTS:
            if not r["ok"]:
                print(f"  - {r['name']}: {r.get('error', '')}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
