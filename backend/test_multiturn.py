"""Test multi-turn conversation to verify AIMessage serialization fix."""
import asyncio
import json
import websockets


async def test():
    async with websockets.connect("ws://127.0.0.1:8000/ws/chat") as ws:
        r = await asyncio.wait_for(ws.recv(), timeout=10)
        e = json.loads(r)
        print(f"1. Received: {e['type']}")

        await ws.send(json.dumps({"type": "user_input", "data": {"content": "hi"}}))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=30)
            e = json.loads(r)
            if e["type"] == "final_answer":
                print("2. First answer OK")
                break

        await ws.send(json.dumps({"type": "user_input", "data": {"content": "what time is it now?"}}))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=60)
            e = json.loads(r)
            if e["type"] == "final_answer":
                print("3. Second answer OK (multi-turn works!)")
                break
            if e["type"] == "error":
                print(f"3. ERROR: {e['data']['message']}")
                print(f"   {e['data'].get('detail', '')[:300]}")
                break

asyncio.run(test())
