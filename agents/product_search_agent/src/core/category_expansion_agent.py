from typing import List, Optional
from urllib.parse import urlparse

from shared.logging import setup_logger
from shared.web_crawler_client import WebCrawlerClient

logger = setup_logger("category_expansion")


def _same_domain(base_url: str, link: str) -> bool:
    try:
        b = urlparse(base_url)
        l = urlparse(link)
        return l.netloc and l.netloc == b.netloc
    except Exception:
        return False


def _likely_product_url(url: str) -> bool:
    u = url.lower()
    # Exclude obvious non-product/content/link-hubs
    if any(bad in u for bad in (
        "wikipedia.org",
        "evisos.com.uy",
        "foodbevg.com",
        "acg.com.uy",
        "/search",
        "/busca",
        "/resultados",
        "/results",
        "/category/",
        "/categories/",
        "/collections/",
        "/collection/",
        "/list/",
    )):
        return False
    if any(token in u for token in ("?page=", "&page=", "?q=", "?search=", "&q=")):
        return False
    # Require common product URL patterns
    product_tokens = ("/p/", "/product/", "/producto/", "/item/", "/sku/", "/prod/")
    if any(token in u for token in product_tokens):
        return True
    # Also accept VTEX-style product URLs ending with '/p'
    if u.rstrip('/').endswith('/p'):
        return True
    return False


def _dedupe_preserve_order(urls: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


class CategoryExpansionAgent:
    def __init__(self, per_domain_cap: int = 8, global_cap: int = 50):
        self.per_domain_cap = per_domain_cap
        self.global_cap = global_cap

    async def expand(self, category_urls: List[str], timeout_ms: int = 30000) -> List[str]:
        if not category_urls:
            return []
        product_links: List[str] = []
        async with WebCrawlerClient() as crawler:
            for url in category_urls:
                try:
                    resp = await crawler.crawl_single(url=url, extract_links=True, timeout=timeout_ms)
                    if not resp.success or not resp.result:
                        continue
                    links = [l for l in resp.result.links if _same_domain(url, l)]
                    filtered = [l for l in links if _likely_product_url(l)]
                    # per-domain cap
                    domain = urlparse(url).netloc
                    count_domain = sum(1 for l in product_links if urlparse(l).netloc == domain)
                    for l in filtered:
                        if count_domain >= self.per_domain_cap:
                            break
                        product_links.append(l)
                        count_domain += 1
                    if len(product_links) >= self.global_cap:
                        break
                except Exception as e:
                    logger.warning(f"Category expansion failed for {url}: {e}")
                    continue
        return _dedupe_preserve_order(product_links)[: self.global_cap]


