# V1.0 验收通知（非MCP浏览器控制）

## 验收前提
- 后端已启动，且环境变量 `BROWSER_TRANSPORT=native_extension`。
- Chrome 已加载扩展目录：`extensions/myclaw-browser-agent/`。
- 目标业务页面已打开（可由 Agent 导航）。

## 验收步骤
1. 打开前端页面，确认顶部出现 `native_extension` 标签。
2. 发起基础任务：打开网页并读取标题。
3. 发起交互任务：点击筛选、输入文本、点击查询。
4. 发起复杂任务：翻页读取 + 下载动作（含落盘校验）。
5. 观察图面板中初始化状态：
   - `Browser Native Channel` 为 success
   - 无持续 timeout/error 风暴

## 通过标准
- 连续 10 轮基础/交互任务成功率 >= 95%
- 复杂链路（含下载）成功率 >= 90%
- 未出现“插件已连但后端不可用”的会话漂移
- 超时率显著低于 legacy MCP 基线

## 回滚开关
- 设置 `BROWSER_TRANSPORT=legacy_mcp` 后重启后端，可切回旧链路。
- 如需恢复 MCP 面板，保持 legacy 模式并启用 `BROWSER_MCP_ENABLED=true`。

## 说明
- 本版本为软清理：运行时默认使用 native_extension；legacy MCP 仍保留短期回滚能力。
- 观察窗口通过后，再进行历史 MCP/Skill 物理删除。

