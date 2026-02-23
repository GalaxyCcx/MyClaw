import os

import httpx
from langchain_core.tools import tool
from markdownify import markdownify


@tool
def web_fetch(url: str) -> str:
    """抓取指定 URL 的网页内容，将 HTML 转换为 Markdown 文本返回。"""
    MAX_CHARS = int(os.getenv("WEB_FETCH_MAX_CHARS", "60000"))
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "MyClaw/1.0"})
            resp.raise_for_status()
        md = markdownify(resp.text, strip=["img", "script", "style"])
        md = "\n".join(line for line in md.splitlines() if line.strip())
        if len(md) > MAX_CHARS:
            md = md[:MAX_CHARS] + f"\n\n... [内容已截断，仅显示前 {MAX_CHARS} 字符]"
        return md
    except httpx.TimeoutException:
        return f"错误：请求超时 - {url}"
    except httpx.HTTPStatusError as e:
        return f"错误：HTTP {e.response.status_code} - {url}"
    except Exception as e:
        return f"错误：网页抓取失败 - {e}"
