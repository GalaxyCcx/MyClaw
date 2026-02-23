"""
WebSocket 测试客户端 — 用于验收 Phase 1 & Phase 4
用法：python test_ws_client.py "你想说的话"
示例：python test_ws_client.py "用python计算 3*7"
"""
import asyncio
import json
import sys

import websockets


async def main(message: str):
    uri = "ws://127.0.0.1:8000/ws/chat"
    print(f"连接到 {uri} ...")
    async with websockets.connect(uri) as ws:
        got_init = False
        while not got_init:
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            event = json.loads(resp)
            if event["type"] == "init_status":
                data = event["data"]
                print(f"[初始化] 收到 init_status，{len(data['jobs'])} 个 Job, {len(data['tools'])} 个工具")
                for j in data["jobs"]:
                    status_icon = "OK" if j["status"] == "success" else "FAIL"
                    print(f"  [{status_icon}] {j['name']}: {j['status']} ({j['duration_ms']}ms) - {j['detail'][:60]}")
                got_init = True

        payload = json.dumps({"type": "user_input", "data": {"content": message}})
        await ws.send(payload)
        print(f"\n已发送: {message}")
        print("=" * 50)

        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=60)
                event = json.loads(resp)
                etype = event["type"]
                data = event["data"]

                if etype == "user_input":
                    print(f"[用户消息] {data['content']}")
                elif etype == "graph_reset":
                    print("[图重置] graph_reset")
                elif etype == "node_enter":
                    nt = data.get("node_type", "?")
                    nid = data.get("node_id", "?")
                    extra = ""
                    if nt == "llm":
                        snap = data.get("messages_snapshot", [])
                        extra = f" (messages_snapshot: {len(snap)} msgs)"
                    elif nt == "tool":
                        extra = f" (tool: {data.get('tool_name', '?')})"
                    print(f"[进入节点] {nt} / {nid}{extra}")
                elif etype == "node_exit":
                    nt = data.get("node_type", "?")
                    nid = data.get("node_id", "?")
                    dur = data.get("duration_ms", 0)
                    extra_parts = [f"{dur}ms"]
                    if nt == "llm":
                        extra_parts.append(f"has_tool_calls={data.get('has_tool_calls')}")
                    elif nt == "tool":
                        extra_parts.append(f"status={data.get('status')}")
                    print(f"[退出节点] {nt} / {nid} ({', '.join(extra_parts)})")
                elif etype == "tool_call":
                    print(f"[工具调用] {data['name']}")
                    print(f"  参数: {json.dumps(data['arguments'], ensure_ascii=False)}")
                elif etype == "tool_result":
                    status = "成功" if data["status"] == "success" else "失败"
                    print(f"[工具结果] {data['name']} - {status}")
                    print(f"  输出: {data['content'][:300]}")
                elif etype == "final_answer":
                    print(f"[最终回答] {data['content']}")
                    break
                elif etype == "error":
                    print(f"[错误] {data['message']}")
                    print(f"  详情: {data.get('detail', '')[:200]}")
                    break
                elif etype == "llm_token":
                    pass
                else:
                    print(f"[{etype}] {json.dumps(data, ensure_ascii=False)[:100]}")

                if etype not in ("llm_token",):
                    print("-" * 50)
            except asyncio.TimeoutError:
                print("等待超时（60秒）")
                break

    print("=" * 50)
    print("测试完成!")


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "用python计算 3*7"
    asyncio.run(main(msg))
