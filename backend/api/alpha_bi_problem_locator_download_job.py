"""
Alpha BI「▌二、问题定位」表下载 Job - 使用 v2 原子动作实现。

流程：悬浮下载图标 -> 点击原始数据 -> 点击跳转至任务中心 -> 在任务中心点击下载。
与旧 download / download-preset job 完全隔离，不依赖 alpha_bi_download_table。
"""

from __future__ import annotations

DEFAULT_ALPHA_BI_URL = (
    "https://alpha-bi.ddxq.mobi/report?"
    "pathIds=279b4f5efc6d446886b3662773c25b3c,cc4baf96c7344900918887be30cf56de"
    "&dashboardId=d127af3f0bb3457287f5093bdea78846"
    "&externalSpaceId=fccdafe6147b461d94425137c51ffe2e"
    "&appId=36620ff9365540a2b6a36531a5dcef6b"
    "&iframeType=app&orgId=1&spaceId=fccdafe6147b461d94425137c51ffe2e"
)

# 下载图标定位：▌二、问题定位 区块的下载图标（通常为第 2 个，第 1 个在核心指标）
DOWNLOAD_ICON_INDEX = 1

# 跳转浮窗按钮文案（按优先级尝试，与弹窗实际文案一致）
GOTO_CENTER_TEXTS = [
    "前往任务中心>>",  # 弹窗主按钮实际文案
    "前往任务中心",
    "跳转至任务中心",
    "任务中心",
]
