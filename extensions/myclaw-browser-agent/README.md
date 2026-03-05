# MyClaw Browser Agent Extension

用于替代 Browser MCP 的原生浏览器控制通道（WebSocket 直连后端）。

## 加载方式
1. 打开 Chrome 扩展页：`chrome://extensions/`
2. 打开开发者模式
3. 选择“加载已解压的扩展程序”
4. 选择目录：`extensions/myclaw-browser-agent/`

## 连接方式
- 扩展会自动连接：`ws://127.0.0.1:8000/ws/browser-gateway`
- 后端环境变量需设置：`BROWSER_TRANSPORT=native_extension`

## 支持动作
- navigate/click/type/wait/press_key/snapshot
- hover/select_option/go_back/go_forward/screenshot
- download_status

## 注意
- 扩展必须与后端同机运行（本地回环地址）。
- 若后端重启，扩展会自动重连。

