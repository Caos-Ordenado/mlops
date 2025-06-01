import os
import aiohttp
import asyncio
from shared.logging import setup_logger
from src.api.models import BraveSearchResult

logger = setup_logger("search_agent")

class SearchAgent:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def brave_search(self, query: str):
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            logger.error("BRAVE_SEARCH_API_KEY not set in environment")
            return None
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }

        query = f"{query}&country=UY"
        params = {"q": query, "count": 20}
        try:
            async with self.session.get(url, headers=headers, params=params, timeout=15) as resp:
                if resp.status != 200:
                    logger.error(f"Brave API error {resp.status}: {await resp.text()}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Brave API call failed for query '{query}': {e}")
            return None

    async def aggregate_search(self, queries):
        results = []
        for q in queries:
            brave_data = await self.brave_search(q)
            results.append(BraveSearchResult(query=q, results=brave_data))
            await asyncio.sleep(1)
        return results 