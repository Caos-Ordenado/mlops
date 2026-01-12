import os
import re
import json
import hashlib
import asyncio
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, urlparse
from bs4 import BeautifulSoup

from shared.logging import setup_logger
from shared.web_crawler_client import WebCrawlerClient
from shared.redis_client import RedisClient
from shared.renderer_client import RendererClient
from src.api.models import BraveSearchResult
from src.core.utils import sanitize_ecommerce_url

logger = setup_logger("search_agent")

class SearchAgent:
    """Enhanced SearchAgent using web crawler instead of Brave API."""
    
    def __init__(self):
        self.session = None
        self.redis_client = None
        self.web_crawler_client = None
        self.cache_prefix = "search_results:"
        self.cache_ttl = 3600  # 1 hour cache
        # Cache/schema versioning: bump when changing result format/parsing behavior.
        self.cache_schema_version = os.getenv("SEARCH_CACHE_SCHEMA_VERSION", "v2")
        # Circuit breaker TTL for engines we detect as blocked.
        self.engine_breaker_ttl_seconds = int(os.getenv("SEARCH_ENGINE_BREAKER_TTL_SECONDS", "1800"))
        # Candidate budget per query (post-dedupe).
        self.max_results_per_query = int(os.getenv("SEARCH_MAX_RESULTS_PER_QUERY", "40"))

    async def __aenter__(self):
        """Initialize all clients."""
        self.redis_client = RedisClient()
        await self.redis_client.__aenter__()
        self.web_crawler_client = WebCrawlerClient()
        await self.web_crawler_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup all clients."""
        if self.redis_client:
            await self.redis_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.web_crawler_client:
            await self.web_crawler_client.__aexit__(exc_type, exc_val, exc_tb)

    def _generate_cache_key(self, query: str, engine_signature: str) -> str:
        """Generate a cache key for the search query.
        
        Includes schema version and enabled engine signature so cache entries stay correct
        when engine configuration/parsers change (country intentionally excluded).
        """
        # Engine signature is part of the key; keep it stable/deterministic.
        payload = f"{self.cache_schema_version}:{engine_signature}:{query}"
        query_hash = hashlib.md5(payload.encode()).hexdigest()
        return f"{self.cache_prefix}{query_hash}"

    def _engine_name_from_domain(self, domain: str) -> str:
        d = (domain or "").lower()
        if "duckduckgo" in d:
            return "duckduckgo"
        if "startpage" in d:
            return "startpage"
        if "ecosia" in d:
            return "ecosia"
        if "qwant" in d:
            return "qwant"
        if "google" in d:
            return "google"
        return d or "unknown"

    def _engine_breaker_key(self, engine: str) -> str:
        return f"search_engine_health:{engine}"

    def _looks_blocked(self, html_content: str) -> tuple[bool, str]:
        """Best-effort detection of block/consent/captcha pages."""
        if not html_content:
            return True, "empty_html"

        reasons: List[str] = []
        size = len(html_content)
        if size < 2000:
            reasons.append(f"tiny_html:{size}")

        hay = html_content.lower()
        markers = (
            "captcha",
            "verify you are",
            "unusual traffic",
            "enable javascript",
            "robot check",
            "access denied",
        )
        for m in markers:
            if m in hay:
                reasons.append(f"marker:{m}")
                break

        return (len(reasons) > 0), ",".join(reasons) if reasons else "ok"

    async def _is_engine_breaker_open(self, engine: str) -> bool:
        try:
            v = await self.redis_client.get(self._engine_breaker_key(engine))
            return bool(v)
        except Exception as e:
            # Fail open (don’t block engines) if Redis is unavailable.
            logger.warning(f"Failed to read engine breaker for {engine}: {e}")
            return False

    async def _open_engine_breaker(self, engine: str, reason: str) -> None:
        try:
            await self.redis_client.set(
                self._engine_breaker_key(engine),
                reason or "blocked",
                ex=self.engine_breaker_ttl_seconds,
            )
            logger.info(f"Opened search engine breaker for {engine} ({reason}), ttl={self.engine_breaker_ttl_seconds}s")
        except Exception as e:
            logger.warning(f"Failed to open engine breaker for {engine}: {e}")

    async def _close_engine_breaker(self, engine: str) -> None:
        """Close breaker early when an engine is producing results again."""
        try:
            await self.redis_client.delete(self._engine_breaker_key(engine))
            logger.info(f"Closed search engine breaker for {engine} (engine recovered)")
        except Exception as e:
            logger.warning(f"Failed to close engine breaker for {engine}: {e}")

    async def _filter_urls_by_breaker(self, search_urls: List[str]) -> tuple[List[str], str]:
        """Filter search URLs based on circuit breaker state and return engine signature."""
        enabled_urls: List[str] = []
        engines: List[str] = []
        skipped: List[tuple[str, str, str]] = []  # (engine, url, domain)

        for url in search_urls:
            domain = urlparse(url).netloc
            engine = self._engine_name_from_domain(domain)
            if engine != "unknown" and await self._is_engine_breaker_open(engine):
                logger.info(f"Skipping search engine due to open breaker: {engine} ({domain})")
                skipped.append((engine, url, domain))
                continue
            enabled_urls.append(url)
            engines.append(engine)

        # Keep deterministic order for signature.
        if enabled_urls:
            # If we ended up with only 1 enabled engine but others are blocked, add a single probe
            # engine to allow automatic recovery (breaker closes on successful results).
            if len(enabled_urls) == 1 and skipped:
                preferred_probe = ("qwant", "ecosia", "startpage", "duckduckgo", "google")
                enabled_set = set(engines)
                probe_url = None
                probe_engine = None
                probe_domain = None
                for p in preferred_probe:
                    if p in enabled_set:
                        continue
                    for eng, u, d in skipped:
                        if eng == p:
                            probe_engine, probe_url, probe_domain = eng, u, d
                            break
                    if probe_url:
                        break
                if probe_url:
                    logger.info(f"Probing blocked engine for recovery: {probe_engine} ({probe_domain})")
                    enabled_urls.append(probe_url)
                    engines.append(f"probe:{probe_engine}")

            engine_signature = ",".join(engines)
            return enabled_urls, engine_signature

        # If all breakers are open, do a minimal "probe" to avoid hammering every engine.
        # Prefer engines that are historically productive for this agent.
        preferred = ("ecosia", "qwant", "startpage", "duckduckgo", "google")
        for p in preferred:
            for url in search_urls:
                domain = urlparse(url).netloc
                engine = self._engine_name_from_domain(domain)
                if engine == p:
                    logger.info(f"All engine breakers open; probing with {engine} ({domain})")
                    return [url], f"probe:{engine}"

        # Fallback: probe first URL.
        if search_urls:
            domain = urlparse(search_urls[0]).netloc
            engine = self._engine_name_from_domain(domain)
            logger.info(f"All engine breakers open; probing with first URL ({domain})")
            return [search_urls[0]], f"probe:{engine}"

        return [], "none"

    def _dedupe_results_by_url(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out: List[Dict[str, Any]] = []
        for r in results:
            u = (r or {}).get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(r)
        return out

    def _build_search_urls(self, query: str, country: str = "UY") -> List[str]:
        """Build search engine URLs for the given query."""
        # Encode query for URL safety
        encoded_query = urlencode({"q": f"{query} {country}"})
        
        search_urls = [
            # DuckDuckGo HTML endpoint - use html.duckduckgo.com directly (avoids redirect)
            f"https://html.duckduckgo.com/html/?{encoded_query}",
            # Startpage (Google results without tracking)  
            f"https://www.startpage.com/sp/search?{encoded_query}&cat=web&language=english",
            # Ecosia - Bing-powered, privacy-focused, less aggressive blocking
            f"https://www.ecosia.org/search?{encoded_query}",
            # Qwant - European search engine with independent index
            f"https://www.qwant.com/?{encoded_query}&t=web",
        ]
        
        # Optional: Add Google if needed (may be blocked more often)
        if os.getenv("ENABLE_GOOGLE_SEARCH", "false").lower() == "true":
            google_query = urlencode({"q": f"{query} {country}", "num": "20"})
            search_urls.append(f"https://www.google.com/search?{google_query}")
        
        return search_urls

    def _parse_duckduckgo_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse DuckDuckGo search results from HTML.
        
        DuckDuckGo HTML endpoint structure (when rendered with JS):
        - Results are in divs with class containing 'result'
        - Title links have class 'result__a'
        - Snippets have class 'result__snippet'
        - URLs are DuckDuckGo redirects: //duckduckgo.com/l/?uddg=<encoded_url>
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing DuckDuckGo results for query: {query} (HTML length: {len(html_content)})")
            
            # Primary approach: Find title links with class 'result__a' (DDG HTML endpoint)
            title_links = soup.find_all('a', class_='result__a')
            
            if title_links:
                logger.debug(f"Found {len(title_links)} DDG result__a title links")
                
                for i, title_link in enumerate(title_links[:20]):
                    try:
                        title = title_link.get_text(strip=True)
                        href = title_link.get('href', '')
                        
                        # Extract actual URL from DuckDuckGo redirect
                        url = None
                        if '/l/?uddg=' in href or 'uddg=' in href:
                            import urllib.parse
                            # Handle both //duckduckgo.com/l/?uddg= and relative /l/?uddg= formats
                            if href.startswith('//'):
                                href = 'https:' + href
                            elif href.startswith('/'):
                                href = 'https://duckduckgo.com' + href
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            url = parsed.get('uddg', [None])[0]
                            if url:
                                url = urllib.parse.unquote(url)
                        elif href.startswith('http'):
                            url = href
                        elif href.startswith('//'):
                            url = 'https:' + href
                        
                        # Find the snippet - look for sibling or nearby element with result__snippet
                        parent = title_link.find_parent()
                        description = None
                        if parent:
                            # Look in parent's siblings or children
                            snippet_elem = parent.find_next('a', class_='result__snippet')
                            if not snippet_elem:
                                snippet_elem = parent.find_next(class_=re.compile(r'result__snippet'))
                            if snippet_elem:
                                description = snippet_elem.get_text(strip=True)
                        
                        # Sanitize URL before adding
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': description,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"DDG result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing DDG result__a element {i}: {e}")
                        continue
            
            # Fallback: Try h2 headings with links (JS-rendered version)
            if not results:
                logger.debug("No result__a links found, trying h2 headings")
                h2_elements = soup.find_all('h2')
                
                for i, h2 in enumerate(h2_elements[:20]):
                    try:
                        link = h2.find('a', href=True)
                        if not link:
                            continue
                        
                        title = link.get_text(strip=True)
                        href = link.get('href', '')
                        
                        # Extract URL from DDG redirect
                        url = None
                        if '/l/?uddg=' in href or 'uddg=' in href:
                            import urllib.parse
                            if href.startswith('//'):
                                href = 'https:' + href
                            elif href.startswith('/'):
                                href = 'https://duckduckgo.com' + href
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            url = parsed.get('uddg', [None])[0]
                            if url:
                                url = urllib.parse.unquote(url)
                        elif href.startswith('http'):
                            url = href
                        
                        # Sanitize URL
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': None,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"DDG h2 result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing DDG h2 element {i}: {e}")
                        continue
            
            # Final fallback: text-based parsing
            if not results:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "duckduckgo")
            
            logger.info(f"Parsed {len(results)} results from DuckDuckGo for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing DuckDuckGo results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_startpage_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse Startpage search results from HTML.
        
        Startpage structure (when rendered with JS):
        - Results are in sections/divs with class 'w-gl__result'
        - Title links have class 'w-gl__result-title' or are in h3 elements
        - Descriptions have class 'w-gl__description'
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing Startpage results for query: {query} (HTML length: {len(html_content)})")
            
            # Primary approach: Find result containers with 'w-gl__result' class
            result_containers = soup.find_all('div', class_=re.compile(r'w-gl__result'))
            if not result_containers:
                result_containers = soup.find_all('section', class_=re.compile(r'w-gl__result'))
            
            if result_containers:
                logger.debug(f"Found {len(result_containers)} Startpage w-gl__result containers")
                
                for i, container in enumerate(result_containers[:20]):
                    try:
                        # Find title link - try multiple selectors
                        title_link = (
                            container.find('a', class_=re.compile(r'w-gl__result-title')) or
                            container.find('h3', class_=re.compile(r'w-gl__result-title')) or
                            container.find('a', class_=re.compile(r'result-link|title'))
                        )
                        
                        # If title is in h3, find the parent link
                        if title_link and title_link.name == 'h3':
                            parent_link = title_link.find_parent('a')
                            if parent_link:
                                title = title_link.get_text(strip=True)
                                url = parent_link.get('href')
                            else:
                                title = title_link.get_text(strip=True)
                                url = container.find('a', href=True)
                                url = url.get('href') if url else None
                        elif title_link:
                            title = title_link.get_text(strip=True)
                            url = title_link.get('href')
                        else:
                            # Fallback: find any link with href
                            any_link = container.find('a', href=True)
                            if any_link:
                                title = any_link.get_text(strip=True)
                                url = any_link.get('href')
                            else:
                                continue
                        
                        # Find description
                        desc_elem = container.find('p', class_=re.compile(r'w-gl__description'))
                        if not desc_elem:
                            desc_elem = container.find(class_=re.compile(r'description|snippet'))
                        description = desc_elem.get_text(strip=True) if desc_elem else None
                        
                        # Sanitize URL
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': description,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"Startpage result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing Startpage container {i}: {e}")
                        continue
            
            # Fallback: Try to find h3 elements with links (common pattern)
            if not results:
                logger.debug("No w-gl__result containers found, trying h3 fallback")
                h3_elements = soup.find_all('h3')
                
                for i, h3 in enumerate(h3_elements[:20]):
                    try:
                        link = h3.find('a', href=True) or h3.find_parent('a')
                        if not link:
                            continue
                        
                        title = h3.get_text(strip=True) or link.get_text(strip=True)
                        url = link.get('href')
                        
                        # Skip internal Startpage links
                        if url and 'startpage.com' in url:
                            continue
                        
                        # Sanitize URL
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': None,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"Startpage h3 result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing Startpage h3 {i}: {e}")
                        continue
            
            # Final fallback: text-based parsing
            if not results:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "startpage")
            
            logger.info(f"Parsed {len(results)} results from Startpage for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing Startpage results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_ecosia_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse Ecosia search results from HTML.
        
        Ecosia is Bing-powered and has a relatively clean structure:
        - Results are in divs with data-test-id='mainline-result-web' or similar
        - Title links are in h2/h3 elements with class containing 'result__title'
        - URLs are in the href of the title link
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing Ecosia results for query: {query} (HTML length: {len(html_content)})")
            
            # Primary: Find result containers by data-test-id or class patterns
            result_containers = (
                soup.find_all(attrs={'data-test-id': re.compile(r'mainline-result|web-result')}) or
                soup.find_all('div', class_=re.compile(r'result__body|result-card|web-result')) or
                soup.find_all('article', class_=re.compile(r'result'))
            )
            
            if result_containers:
                logger.debug(f"Found {len(result_containers)} Ecosia result containers")
                
                for i, container in enumerate(result_containers[:20]):
                    try:
                        # Find title link
                        title_link = (
                            container.find('a', class_=re.compile(r'result__title|result-title')) or
                            container.find('h2') or container.find('h3')
                        )
                        
                        if title_link:
                            if title_link.name in ['h2', 'h3']:
                                # Find the link inside or parent
                                link_elem = title_link.find('a', href=True) or title_link.find_parent('a')
                                if link_elem:
                                    title = title_link.get_text(strip=True)
                                    url = link_elem.get('href')
                                else:
                                    continue
                            else:
                                title = title_link.get_text(strip=True)
                                url = title_link.get('href')
                        else:
                            # Fallback: find any link with href
                            any_link = container.find('a', href=True)
                            if any_link:
                                title = any_link.get_text(strip=True)
                                url = any_link.get('href')
                            else:
                                continue
                        
                        # Skip Ecosia internal links
                        if url and ('ecosia.org' in url or url.startswith('/')):
                            continue
                        
                        # Find description
                        desc_elem = container.find(class_=re.compile(r'result__snippet|result-snippet|description'))
                        if not desc_elem:
                            desc_elem = container.find('p')
                        description = desc_elem.get_text(strip=True) if desc_elem else None
                        
                        # Sanitize URL
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': description,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"Ecosia result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing Ecosia container {i}: {e}")
                        continue
            
            # Fallback: Look for links with external URLs
            if not results:
                logger.debug("No Ecosia result containers found, trying link fallback")
                all_links = soup.find_all('a', href=True)
                
                for i, link in enumerate(all_links[:50]):
                    try:
                        url = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # Only include external links with proper URLs
                        if (url.startswith('http') and 
                            'ecosia.org' not in url and 
                            title and len(title) > 5 and len(title) < 200):
                            
                            url = sanitize_ecommerce_url(url)
                            if url:
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'description': None,
                                    'page_age': None,
                                    'profile': {'name': 'web'},
                                    'language': 'en'
                                })
                                if len(results) >= 20:
                                    break
                    except Exception:
                        continue
            
            # Final fallback: text-based parsing
            if not results:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "ecosia")
            
            logger.info(f"Parsed {len(results)} results from Ecosia for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing Ecosia results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_qwant_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse Qwant search results from HTML.
        
        Qwant structure:
        - Results are in divs/articles with data-testid='webResult' or class 'result'
        - Title links contain the URL in href
        - URLs are direct (not redirects)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing Qwant results for query: {query} (HTML length: {len(html_content)})")
            
            # Primary: Find result containers
            result_containers = (
                soup.find_all(attrs={'data-testid': re.compile(r'webResult|result')}) or
                soup.find_all('div', class_=re.compile(r'result(?!-page)|web-result')) or
                soup.find_all('article')
            )
            
            if result_containers:
                logger.debug(f"Found {len(result_containers)} Qwant result containers")
                
                for i, container in enumerate(result_containers[:20]):
                    try:
                        # Find title link - try multiple approaches
                        title_link = (
                            container.find('a', attrs={'data-testid': 'serTitle'}) or
                            container.find('h2') or container.find('h3') or
                            container.find('a', class_=re.compile(r'title|heading'))
                        )
                        
                        if title_link:
                            if title_link.name in ['h2', 'h3']:
                                link_elem = title_link.find('a', href=True) or title_link.find_parent('a')
                                if link_elem:
                                    title = title_link.get_text(strip=True)
                                    url = link_elem.get('href')
                                else:
                                    continue
                            else:
                                title = title_link.get_text(strip=True)
                                url = title_link.get('href')
                        else:
                            any_link = container.find('a', href=True)
                            if any_link:
                                title = any_link.get_text(strip=True)
                                url = any_link.get('href')
                            else:
                                continue
                        
                        # Skip Qwant internal links
                        if url and ('qwant.com' in url or url.startswith('/')):
                            continue
                        
                        # Find description
                        desc_elem = container.find(attrs={'data-testid': 'serDescription'})
                        if not desc_elem:
                            desc_elem = container.find(class_=re.compile(r'description|snippet|abstract'))
                        if not desc_elem:
                            desc_elem = container.find('p')
                        description = desc_elem.get_text(strip=True) if desc_elem else None
                        
                        # Sanitize URL
                        if url:
                            url = sanitize_ecommerce_url(url)
                        
                        if url and title and len(title) > 2:
                            results.append({
                                'title': title,
                                'url': url,
                                'description': description,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            logger.debug(f"Qwant result {i}: {title[:50]}... -> {url[:60]}...")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing Qwant container {i}: {e}")
                        continue
            
            # Fallback: Look for external links
            if not results:
                logger.debug("No Qwant result containers found, trying link fallback")
                all_links = soup.find_all('a', href=True)
                
                for link in all_links[:50]:
                    try:
                        url = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        if (url.startswith('http') and 
                            'qwant.com' not in url and
                            title and len(title) > 5 and len(title) < 200):
                            
                            url = sanitize_ecommerce_url(url)
                            if url:
                                results.append({
                                    'title': title,
                                    'url': url,
                                    'description': None,
                                    'page_age': None,
                                    'profile': {'name': 'web'},
                                    'language': 'en'
                                })
                                if len(results) >= 20:
                                    break
                    except Exception:
                        continue
            
            # Final fallback: text-based parsing
            if not results:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "qwant")
            
            logger.info(f"Parsed {len(results)} results from Qwant for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing Qwant results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_text_based_results(self, html_content: str, query: str, source: str) -> Dict[str, Any]:
        """Fallback text-based parsing when structured HTML parsing fails."""
        try:
            results = []
            logger.debug(f"Attempting text-based parsing for {source}")
            
            # Extract main content area first
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            
            # Look for URL patterns with context
            import re
            
            # More comprehensive URL pattern for Uruguay sites
            url_pattern = r'(https?://[^\s]+(?:\.com\.uy|\.uy|\.com|\.org)[^\s]*)'
            
            # Find all URLs first
            urls = re.findall(url_pattern, text)
            logger.debug(f"Found {len(urls)} URLs in text content")
            
            # Look for patterns where title comes before URL
            # This pattern captures text before URLs more liberally 
            patterns = [
                # Pattern 1: Title followed by URL on same or next line
                r'([A-Za-z][^\n]*?[a-zA-Z])\s*\n?\s*(https?://[^\s]+(?:\.com\.uy|\.uy|\.com)[^\s]*)',
                # Pattern 2: URL with title nearby in any order
                r'(https?://[^\s]+(?:\.com\.uy|\.uy|\.com)[^\s]*)[^\n]*?([A-Za-z][^\n]*?[a-zA-Z])',
                # Pattern 3: Look for domain names followed by URLs
                r'([a-zA-Z][^\n]*?(?:\.com\.uy|\.uy|\.com)[^\n]*?)\s*(https?://[^\s]+)'
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                all_matches.extend(matches)
            
            logger.debug(f"Found {len(all_matches)} title-URL patterns")
            
            # Also try to extract from visible domain names in text
            domain_pattern = r'([A-Za-z][^\n]*?)((?:www\.)?[a-zA-Z0-9-]+\.(?:com\.uy|uy|com))'
            domain_matches = re.findall(domain_pattern, text)
            
            # Process all matches
            processed_urls = set()
            
            for match in all_matches:
                try:
                    if len(match) == 2:
                        title_candidate, url_candidate = match
                        
                        # Ensure we have both title and URL
                        if 'http' in url_candidate:
                            title, url = title_candidate, url_candidate
                        else:
                            title, url = url_candidate, title_candidate
                            
                        # Skip if URL doesn't start with http
                        if not url.startswith('http'):
                            continue
                            
                        # Clean up title
                        title = title.strip()
                        title = re.sub(r'^.*?(?:Web results|Results)', '', title, flags=re.IGNORECASE)
                        title = re.sub(r'^[•\-\*\|\s]+', '', title)
                        title = re.sub(r'[•\-\*\|\s]+$', '', title)
                        title = title.strip()
                        
                        # More lenient title filtering
                        skip_words = ['next', 'previous', 'page', 'anonymous view', 'visit in anonymous']
                        if len(title) < 3 or any(word in title.lower() for word in skip_words):
                            continue
                        
                        # Clean up URL (remove tracking parameters)
                        url = re.sub(r'[&?]srsltid=[^&]*', '', url)
                        url = re.sub(r'[&?]utm_[^&]*', '', url)
                        
                        # Sanitize URL to fix malformed patterns
                        url = sanitize_ecommerce_url(url)
                        if not url:
                            continue
                        
                        # Skip if we already processed this URL
                        if url in processed_urls:
                            continue
                        processed_urls.add(url)
                        
                        if len(title) >= 3:
                            # Try to extract a description from surrounding text
                            description = None
                            try:
                                # Look for text around the URL
                                url_pos = text.find(url)
                                if url_pos > 0:
                                    context_start = max(0, url_pos - 200)
                                    context_end = min(len(text), url_pos + len(url) + 200)
                                    context = text[context_start:context_end]
                                    
                                    # Extract description after URL or title
                                    desc_match = re.search(r'(?:' + re.escape(url) + r'|' + re.escape(title) + r')\s*([A-Za-z][^\n]{10,100})', context, re.IGNORECASE)
                                    if desc_match:
                                        description = desc_match.group(1).strip()
                            except:
                                pass
                            
                            results.append({
                                'title': title[:100],  # Limit title length
                                'url': url,
                                'description': description[:200] if description else None,
                                'page_age': None,
                                'profile': {'name': 'web'},
                                'language': 'en'
                            })
                            
                            logger.debug(f"Extracted: {title[:50]}... -> {url[:50]}...")
                            
                            if len(results) >= 15:  # Limit results
                                break
                                
                except Exception as e:
                    logger.debug(f"Error processing match: {e}")
                    continue
            
            # If still no results, try a simpler approach with just URLs
            if not results:
                logger.debug("No title-URL matches found, trying URL-only extraction")
                unique_urls = list(set(urls))[:10]  # Limit to 10 unique URLs
                
                for url in unique_urls:
                    if url in processed_urls:
                        continue
                    
                    # Clean URL
                    url = re.sub(r'[&?]srsltid=[^&]*', '', url)
                    url = re.sub(r'[&?]utm_[^&]*', '', url)
                    
                    # Sanitize URL to fix malformed patterns
                    url = sanitize_ecommerce_url(url)
                    if not url:
                        continue
                        
                    processed_urls.add(url)
                    
                    # Extract domain as title
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace('www.', '')
                    title = domain.split('.')[0].title() if domain else "Search Result"
                    
                    results.append({
                        'title': title,
                        'url': url,
                        'description': f"Product search result from {domain}",
                        'page_age': None,
                        'profile': {'name': 'web'},
                        'language': 'en'
                    })
            
            logger.info(f"Text-based parsing found {len(results)} results for {source}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error in text-based parsing for {source}: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_google_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse Google search results from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # Google result selectors (these may change frequently)
            result_elements = soup.find_all('div', class_=re.compile(r'g\b|yuRUbf')) or \
                            soup.find_all('div', {'data-ved': True})
            
            for element in result_elements[:20]:
                try:
                    # Extract title and URL
                    title_link = element.find('h3')
                    if title_link:
                        title_link = title_link.find_parent('a')
                    else:
                        title_link = element.find('a', href=True)
                    
                    if not title_link:
                        continue
                        
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href')
                    
                    # Clean up Google redirect URLs
                    if url and url.startswith('/url?'):
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                        url = parsed.get('url', [None])[0]
                    
                    # Extract description
                    desc_elem = element.find('span', class_=re.compile(r'st|s3v9rd'))
                    description = desc_elem.get_text(strip=True) if desc_elem else None
                    
                    # Sanitize URL before adding
                    if url:
                        url = sanitize_ecommerce_url(url)
                    
                    if url and title:
                        results.append({
                            'title': title,
                            'url': url,
                            'description': description,
                            'page_age': None,
                            'profile': {'name': 'web'},
                            'language': 'en'
                        })
                        
                except Exception as e:
                    logger.debug(f"Error parsing Google result: {e}")
                    continue
            
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing Google results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    async def _get_cached_results(self, query: str, engine_signature: str) -> Optional[Dict[str, Any]]:
        """Get cached search results for a query."""
        try:
            cache_key = self._generate_cache_key(query, engine_signature)
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Using cached search results for query: {query} (engines={engine_signature})")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached results for '{query}': {e}")
        return None

    async def _cache_results(self, query: str, engine_signature: str, results: Dict[str, Any]) -> None:
        """Cache search results for a query."""
        try:
            cache_key = self._generate_cache_key(query, engine_signature)
            await self.redis_client.set(cache_key, json.dumps(results), ex=self.cache_ttl)
            logger.debug(f"Cached search results for query: {query} (engines={engine_signature})")
        except Exception as e:
            logger.warning(f"Failed to cache results for '{query}': {e}")

    async def _fetch_search_with_renderer(self, search_urls: List[str], query: str) -> List[Dict[str, Any]]:
        """
        Fetch search engine pages using the Renderer service (Playwright with anti-bot).
        Uses parallel execution with semaphore limiting, similar to price_extractor.py.
        
        Args:
            search_urls: List of search engine URLs to fetch
            query: The search query for parsing
            
        Returns:
            List of parsed search results
        """
        all_results = []
        
        CONCURRENT_RENDERER_LIMIT = 2  # Limit concurrent search engine requests
        semaphore = asyncio.Semaphore(CONCURRENT_RENDERER_LIMIT)
        
        async def render_single_search(renderer: RendererClient, url: str) -> tuple:
            """Render a single search URL with semaphore-limited concurrency."""
            async with semaphore:
                try:
                    domain = urlparse(url).netloc
                    engine = self._engine_name_from_domain(domain)
                    logger.info(f"Fetching search results with renderer from: {domain}")
                    
                    # Use appropriate wait selector based on search engine
                    if 'duckduckgo' in domain:
                        # DDG: wait for result links to appear
                        wait_selector = ".result__a, h2 a"
                    elif 'startpage' in domain:
                        # Startpage: wait for result containers
                        wait_selector = ".w-gl__result, h3"
                    elif 'ecosia' in domain:
                        # Ecosia: wait for result links
                        wait_selector = "[data-test-id='mainline-result-web'], .result__link, a[href]"
                    elif 'qwant' in domain:
                        # Qwant: wait for result containers
                        wait_selector = "[data-testid='webResult'], .result, article"
                    else:
                        wait_selector = "body"
                    
                    t0 = time.perf_counter()
                    result = await renderer.render_html(
                        url=url, 
                        timeout_ms=30000, 
                        viewport_randomize=True,
                        wait_for_selector=wait_selector
                    )
                    dt_ms = int((time.perf_counter() - t0) * 1000)
                    html_content = result.get("html", "")
                    if html_content:
                        blocked, reason = self._looks_blocked(html_content)
                        logger.info(
                            f"Search engine render: engine={engine} domain={domain} ms={dt_ms} html_bytes={len(html_content)} blocked={blocked}"
                        )
                        return (url, html_content, blocked, reason, engine, domain)
                    else:
                        logger.warning(f"Renderer returned no HTML for {url}")
                        return (url, None, True, "empty_html", engine, domain)
                except Exception as e:
                    logger.warning(f"Renderer failed for search URL {url}: {e}")
                    domain = urlparse(url).netloc
                    engine = self._engine_name_from_domain(domain)
                    return (url, None, True, f"exception:{type(e).__name__}", engine, domain)
        
        try:
            renderer_url = os.getenv("RENDERER_URL", "http://home.server:30080/renderer")
            async with RendererClient(base_url=renderer_url) as renderer:
                # Run all renders concurrently with semaphore limiting
                results = await asyncio.gather(
                    *[render_single_search(renderer, url) for url in search_urls],
                    return_exceptions=True
                )
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Renderer task exception: {result}")
                        continue
                    
                    url, html_content, blocked, block_reason, engine, domain = result
                    if not html_content:
                        # Consider opening breaker on hard failures.
                        if engine != "unknown":
                            await self._open_engine_breaker(engine, block_reason)
                        continue
                    
                    # Only skip parsing on extremely small responses (almost certainly a block/redirect page).
                    if blocked and "tiny_html:" in (block_reason or "") and engine != "unknown":
                        await self._open_engine_breaker(engine, block_reason)
                        continue
                    
                    # Parse results based on search engine domain
                    if 'duckduckgo.com' in domain:
                        parsed_results = self._parse_duckduckgo_results(html_content, query)
                    elif 'startpage.com' in domain:
                        parsed_results = self._parse_startpage_results(html_content, query)
                    elif 'ecosia.org' in domain:
                        parsed_results = self._parse_ecosia_results(html_content, query)
                    elif 'qwant.com' in domain:
                        parsed_results = self._parse_qwant_results(html_content, query)
                    elif 'google.com' in domain:
                        parsed_results = self._parse_google_results(html_content, query)
                    else:
                        logger.warning(f"Unknown search engine domain: {domain}")
                        continue
                    
                    # Collect results
                    if parsed_results and 'web' in parsed_results and 'results' in parsed_results['web']:
                        result_count = len(parsed_results['web']['results'])
                        logger.info(f"Parsed {result_count} results from {domain}")
                        # If parsing yields 0 and page looks blocked, open breaker.
                        if result_count == 0:
                            blocked2, reason2 = self._looks_blocked(html_content)
                            if blocked2 and engine != "unknown":
                                await self._open_engine_breaker(engine, f"parse0:{reason2}")
                        else:
                            # Engine is producing results; close breaker if it was open.
                            if engine != "unknown" and await self._is_engine_breaker_open(engine):
                                await self._close_engine_breaker(engine)
                        all_results.extend(parsed_results['web']['results'])
                        
        except Exception as e:
            logger.error(f"Renderer client initialization failed: {e}")
        
        return all_results

    async def web_crawler_search(self, query: str, country: str = "UY") -> Optional[Dict[str, Any]]:
        """
        Perform web search using the Renderer service (Playwright with anti-bot).
        Returns results in Brave API compatible format.
        
        Uses the Renderer instead of plain HTTP because search engines like DuckDuckGo
        and Startpage require JavaScript rendering and anti-bot measures to return
        proper results.
        """
        search_urls = self._build_search_urls(query, country)
        enabled_urls, engine_signature = await self._filter_urls_by_breaker(search_urls)
        if not enabled_urls:
            logger.warning("No search URLs available after breaker filtering; returning empty result set.")
            return {
                "web": {"results": []},
                "query": {"original": query, "country": country},
            }

        # Check cache (signature-aware)
        cached_results = await self._get_cached_results(query, engine_signature)
        if cached_results:
            return cached_results
        
        # Use Renderer service for search engines (Playwright with anti-bot)
        t0 = time.perf_counter()
        all_results = await self._fetch_search_with_renderer(enabled_urls, query)
        dt_ms = int((time.perf_counter() - t0) * 1000)

        # Dedupe and apply budget
        raw_count = len(all_results)
        all_results = self._dedupe_results_by_url(all_results)
        deduped_count = len(all_results)
        all_results = all_results[: self.max_results_per_query]
        
        # Format results in Brave API compatible format
        final_results = {
            'web': {
                'results': all_results
            },
            'query': {
                'original': query,
                'country': country
            }
        }
        
        # Cache the results
        if all_results:
            await self._cache_results(query, engine_signature, final_results)
            logger.info(
                f"Found {len(all_results)} search results for query: {query} "
                f"(raw={raw_count} deduped={deduped_count} engines={engine_signature} ms={dt_ms})"
            )
        else:
            logger.warning(f"No search results found for query: {query}")
        
        return final_results

    async def brave_search(self, query: str):
        """
        Legacy method name for backward compatibility.
        Now uses web crawler instead of Brave API.
        """
        return await self.web_crawler_search(query)

    async def aggregate_search(self, queries):
        """Perform searches for multiple queries using web crawler."""
        results = []
        for q in queries:
            search_data = await self.web_crawler_search(q)
            results.append(BraveSearchResult(query=q, results=search_data))
            # Add delay between queries to be respectful to search engines
            await asyncio.sleep(3)
        return results 