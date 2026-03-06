---
name: browser-vision-operator
description: 基于 MyClaw Browser Agent V3 的通用视觉操作规范。用于截图标注、按标签点击/输入、滚动扫描与稳定性恢复。
metadata:
  author: MyClaw
  version: "1.0.0"
  tags: [browser, vision, v3, som, automation]
---

# Browser Vision Operator

面向 V3 扩展的通用浏览器操作 Skill。核心是三件证据联合决策：

1. 无标注截图（plain）
2. 标注截图（marked）
3. marks JSON

## 强制规则

1. 每一步操作前必须先抓当前帧新证据，禁止复用旧标签。
2. 所有点击/输入必须使用同一帧 marks 的标签编号。
3. 任何点击后都要再次抓图校验结果，不可仅凭 `ok=true` 判断成功。
4. 页面有加载/动画时，优先 `browser_vision_wait_stable` 再操作。
5. 复杂流程优先小步闭环：抓图 -> 判断 -> 执行 -> 再抓图。

## 标准循环

1. `browser_vision_wait_stable`
2. `browser_vision_capture_marked`
3. 从 `marks` 选择目标标签
4. 执行 `browser_vision_click_label` 或 `browser_vision_type_label`
5. 再次 `browser_vision_capture_marked` 验证

## 滚动预扫

用于首屏看不全的页面：

1. 从当前位置开始抓图。
2. 用 `browser_vision_scroll_by(dy=600~900)` 向下滚动。
3. 每次滚动后抓一份 `marked`。
4. 到达目标模块后停止。

## 失败恢复

1. 标签失效：立即重抓 marks，重新映射标签。
2. 点击后弹层消失：先等待稳定，再重开组件并重抓。
3. 页面卡顿：增加 `timeout_ms` 与 `min_wait_ms`。

