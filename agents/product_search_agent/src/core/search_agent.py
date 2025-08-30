import os
import re
import json
import hashlib
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, urlparse
from bs4 import BeautifulSoup

from shared.logging import setup_logger
from shared.web_crawler_client import WebCrawlerClient
from shared.redis_client import RedisClient
from src.api.models import BraveSearchResult

logger = setup_logger("search_agent")

class SearchAgent:
    """Enhanced SearchAgent using web crawler instead of Brave API."""
    
    def __init__(self):
        self.session = None
        self.redis_client = None
        self.web_crawler_client = None
        self.cache_prefix = "search_results:"
        self.cache_ttl = 3600  # 1 hour cache

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

    def _generate_cache_key(self, query: str) -> str:
        """Generate a cache key for the search query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{self.cache_prefix}{query_hash}"

    def _build_search_urls(self, query: str, country: str = "UY") -> List[str]:
        """Build search engine URLs for the given query."""
        # Encode query for URL safety
        encoded_query = urlencode({"q": f"{query} {country}"})
        
        search_urls = [
            # DuckDuckGo (more permissive with scraping)
            f"https://duckduckgo.com/?{encoded_query}&kl=wt-wt&ia=web",
            # Startpage (Google results without tracking)  
            f"https://www.startpage.com/sp/search?{encoded_query}&cat=web&language=english",
        ]
        
        # Optional: Add Google if needed (may be blocked more often)
        if os.getenv("ENABLE_GOOGLE_SEARCH", "false").lower() == "true":
            google_query = urlencode({"q": f"{query} {country}", "num": "20"})
            search_urls.append(f"https://www.google.com/search?{google_query}")
        
        return search_urls

    def _parse_duckduckgo_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse DuckDuckGo search results from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing DuckDuckGo results for query: {query}")
            
            # DuckDuckGo uses different selectors for results - try multiple approaches
            result_elements = (
                soup.find_all('article', {'data-testid': 'result'}) or
                soup.find_all('div', class_=re.compile(r'result')) or
                soup.find_all('div', class_=re.compile(r'web-result')) or
                soup.find_all('div', class_=re.compile(r'links_main')) or
                soup.find_all('article') or
                soup.find_all('div', attrs={'data-result': True})
            )
            
            logger.debug(f"Found {len(result_elements)} potential result elements")
            
            # If no structured results found, try parsing from main content text
            if not result_elements:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "duckduckgo")
            
            for i, element in enumerate(result_elements[:20]):  # Limit to top 20 results
                try:
                    # Multiple ways to find title and URL
                    title_elem = (
                        element.find('h2') or element.find('h3') or 
                        element.find('a', class_=re.compile(r'result_')) or
                        element.find('a', href=True)
                    )
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    # Extract URL with multiple fallbacks
                    link_elem = (
                        element.find('a', href=True) or
                        title_elem if title_elem and title_elem.get('href') else None
                    )
                    
                    url = None
                    if link_elem and link_elem.get('href'):
                        href = link_elem['href']
                        # Clean up DuckDuckGo redirect URLs
                        if 'duckduckgo.com' in href and '/l/?uddg=' in href:
                            # Extract actual URL from DuckDuckGo redirect
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            url = parsed.get('uddg', [None])[0]
                        elif href.startswith('http'):
                            url = href
                        elif href.startswith('//'):
                            url = 'https:' + href
                    
                    # Extract description/snippet with multiple fallbacks
                    desc_elem = (
                        element.find('span', class_=re.compile(r'snippet|description|result__snippet')) or
                        element.find('div', class_=re.compile(r'snippet|description|result__snippet')) or
                        element.find('p')
                    )
                    description = desc_elem.get_text(strip=True) if desc_elem else None
                    
                    if url and title and url.startswith('http'):
                        results.append({
                            'title': title,
                            'url': url,
                            'description': description,
                            'page_age': None,
                            'profile': {'name': 'web'},
                            'language': 'en'
                        })
                        logger.debug(f"Extracted result {i}: {title[:50]}... -> {url[:50]}...")
                        
                except Exception as e:
                    logger.debug(f"Error parsing DuckDuckGo result element {i}: {e}")
                    continue
            
            logger.info(f"Parsed {len(results)} results from DuckDuckGo for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing DuckDuckGo results: {e}")
            return {'web': {'results': []}, 'query': {'original': query}}

    def _parse_startpage_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """Parse Startpage search results from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            logger.debug(f"Parsing Startpage results for query: {query}")
            
            # Try multiple selectors for Startpage results
            result_elements = (
                soup.find_all('div', class_=re.compile(r'w-gl__result')) or
                soup.find_all('div', class_=re.compile(r'result')) or
                soup.find_all('section', class_=re.compile(r'w-gl__result')) or
                soup.find_all('article') or
                soup.find_all('div', attrs={'data-testid': 'result'})
            )
            
            logger.debug(f"Found {len(result_elements)} potential result elements")
            
            # If no structured results found, try parsing from main content text
            if not result_elements:
                logger.debug("No structured elements found, trying text-based parsing")
                return self._parse_text_based_results(html_content, query, "startpage")
            
            for i, element in enumerate(result_elements[:20]):
                try:
                    # Multiple ways to find title and URL
                    title_link = (
                        element.find('a', class_=re.compile(r'result-link|w-gl__result-title|title')) or
                        element.find('h3').find_parent('a') if element.find('h3') else None or
                        element.find('a', href=True)
                    )
                    
                    if not title_link:
                        logger.debug(f"No title link found in element {i}")
                        continue
                        
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href')
                    
                    # Extract description from multiple possible locations
                    desc_elem = (
                        element.find('p', class_=re.compile(r'w-gl__description|result-desc|description|snippet')) or
                        element.find('span', class_=re.compile(r'description|snippet')) or
                        element.find('div', class_=re.compile(r'description|snippet'))
                    )
                    description = desc_elem.get_text(strip=True) if desc_elem else None
                    
                    if url and title and url.startswith('http'):
                        results.append({
                            'title': title,
                            'url': url,
                            'description': description,
                            'page_age': None,
                            'profile': {'name': 'web'},
                            'language': 'en'
                        })
                        logger.debug(f"Extracted result {i}: {title[:50]}... -> {url[:50]}...")
                        
                except Exception as e:
                    logger.debug(f"Error parsing Startpage result element {i}: {e}")
                    continue
            
            logger.info(f"Parsed {len(results)} results from Startpage for query: {query}")
            return {
                'web': {'results': results},
                'query': {'original': query}
            }
            
        except Exception as e:
            logger.error(f"Error parsing Startpage results: {e}")
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
                        
                        # Skip if we already processed this URL
                        if url in processed_urls:
                            continue
                        processed_urls.add(url)
                        
                        if url.startswith('http') and len(title) >= 3:
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
                    processed_urls.add(url)
                    
                    # Clean URL
                    url = re.sub(r'[&?]srsltid=[^&]*', '', url)
                    url = re.sub(r'[&?]utm_[^&]*', '', url)
                    
                    # Extract domain as title
                    from urllib.parse import urlparse
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
                    
                    if url and title and url.startswith('http'):
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

    async def _get_cached_results(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached search results for a query."""
        try:
            cache_key = self._generate_cache_key(query)
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Using cached search results for query: {query}")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached results for '{query}': {e}")
        return None

    async def _cache_results(self, query: str, results: Dict[str, Any]) -> None:
        """Cache search results for a query."""
        try:
            cache_key = self._generate_cache_key(query)
            await self.redis_client.set(cache_key, json.dumps(results), ex=self.cache_ttl)
            logger.debug(f"Cached search results for query: {query}")
        except Exception as e:
            logger.warning(f"Failed to cache results for '{query}': {e}")

    async def web_crawler_search(self, query: str, country: str = "UY") -> Optional[Dict[str, Any]]:
        """
        Perform web search using the web crawler instead of Brave API.
        Returns results in Brave API compatible format.
        """
        # Check cache first
        cached_results = await self._get_cached_results(query)
        if cached_results:
            return cached_results

        search_urls = self._build_search_urls(query, country)
        all_results = []
        
        for search_url in search_urls:
            try:
                logger.info(f"Crawling search results from: {urlparse(search_url).netloc}")
                
                # Use the web crawler to fetch search results
                response = await self.web_crawler_client.crawl_single(
                    url=search_url,
                    timeout=30000  # 30 seconds
                )
                
                if not response.success or not response.result:
                    logger.warning(f"Failed to crawl search URL: {search_url}")
                    continue
                
                # Parse results based on search engine
                domain = urlparse(search_url).netloc
                if 'duckduckgo.com' in domain:
                    parsed_results = self._parse_duckduckgo_results(response.result.text, query)
                elif 'startpage.com' in domain:
                    parsed_results = self._parse_startpage_results(response.result.text, query)
                elif 'google.com' in domain:
                    parsed_results = self._parse_google_results(response.result.text, query)
                else:
                    logger.warning(f"Unknown search engine domain: {domain}")
                    continue
                
                # Merge results
                if parsed_results and 'web' in parsed_results and 'results' in parsed_results['web']:
                    all_results.extend(parsed_results['web']['results'])
                    
                # Add delay between search engines to be respectful
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error crawling search URL {search_url}: {e}")
                continue
        
        # Format results in Brave API compatible format
        final_results = {
            'web': {
                'results': all_results[:20]  # Limit to top 20 results
            },
            'query': {
                'original': query,
                'country': country
            }
        }
        
        # Cache the results
        if all_results:
            await self._cache_results(query, final_results)
            logger.info(f"Found {len(all_results)} search results for query: {query}")
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