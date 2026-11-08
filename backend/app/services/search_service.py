import logging
from typing import List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet


class SearchService:
    @staticmethod
    async def search(query: str, max_results: int = 5) -> List[SearchResult]:
        """Search the web for query context."""
        results: List[SearchResult] = []

        # 1. Try Tavily API if configured
        if settings.TAVILY_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.TAVILY_API_KEY,
                            "query": query,
                            "max_results": max_results,
                            "search_depth": "basic"
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            results.append(
                                SearchResult(
                                    title=item.get("title", ""),
                                    url=item.get("url", ""),
                                    snippet=item.get("content", "")
                                )
                            )
                        return results
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        # 2. Try DuckDuckGo Instant Answer API as free fallback
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText")
                    url = data.get("AbstractURL")
                    source = data.get("AbstractSource", "Web")
                    if abstract:
                        results.append(SearchResult(title=source, url=url, snippet=abstract))
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if "Text" in topic:
                            results.append(
                                SearchResult(
                                    title=topic.get("FirstURL", "Link"),
                                    url=topic.get("FirstURL", ""),
                                    snippet=topic.get("Text", "")
                                )
                            )
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")

        return results

    @staticmethod
    def format_search_context(results: List[SearchResult]) -> str:
        if not results:
            return ""
        context_parts = ["[Web Search Results]:"]
        for idx, r in enumerate(results, 1):
            context_parts.append(f"{idx}. {r.title} ({r.url}):\n{r.snippet}")
        return "\n\n".join(context_parts)


search_service = SearchService()

