import os
import httpx
from langchain_core.tools import tool

TAVILY_URL = "https://api.tavily.com/search"


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网获取最新信息。返回搜索结果列表，每条包含标题、URL 和摘要。
    当需要查询实时信息、最新新闻、技术文档、产品资料等内容时使用此工具。
    拿到结果后，如需深入了解某条结果的完整内容，可继续使用 web_fetch 抓取对应 URL。"""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return "错误：未配置 TAVILY_API_KEY，无法执行搜索"

    try:
        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": min(max_results, 10),
            "include_answer": False,
            "include_raw_content": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(TAVILY_URL, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"未找到与 '{query}' 相关的搜索结果"

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            content = r.get("content", "无摘要")
            score = r.get("score", 0)
            lines.append(
                f"{i}. **{title}**\n"
                f"   URL: {url}\n"
                f"   摘要: {content}\n"
                f"   相关度: {score:.2f}"
            )
        return "\n\n".join(lines)

    except httpx.TimeoutException:
        return "错误：搜索请求超时，请稍后重试"
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            return "错误：Tavily API Key 无效"
        elif status == 429:
            return "错误：搜索请求过于频繁，请稍后重试"
        elif status == 432:
            return "错误：本月搜索额度已用完"
        return f"错误：搜索服务返回 HTTP {status}"
    except Exception as e:
        return f"错误：搜索失败 - {e}"
