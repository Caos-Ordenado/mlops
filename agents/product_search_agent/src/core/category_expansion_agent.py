from typing import List, Optional
from urllib.parse import urlparse, urljoin
import re
import json

from shared.logging import setup_logger
from shared.web_crawler_client import WebCrawlerClient
from shared.ollama_client import OllamaClient
from .batch_content_retriever import BatchContentRetriever

logger = setup_logger("category_expansion")


def _same_domain(base_url: str, link: str) -> bool:
    try:
        b = urlparse(base_url)
        l = urlparse(link)
        return l.netloc and l.netloc == b.netloc
    except Exception:
        return False


def _likely_product_url(url: str, query_terms: Optional[List[str]] = None) -> bool:
    """
    Determine if a URL is likely a product page based on structural patterns
    and dynamic query terms, not hardcoded product-specific terms.
    """
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
        "/filtros",
        "/filters",
        "/ordenar",
        "/sort",
        "javascript:",
        "mailto:",
        "#",
        "/account",
        "/login",
        "/register", 
        "/contact",
        "/about",
        "/politica",
        "/terminos",
        "/help",
        "/ayuda",
        "/cart",
        "/checkout",
        "/wishlist"
    )):
        return False
        
    # Exclude pagination and search parameters
    if any(token in u for token in ("?page=", "&page=", "?q=", "?search=", "&q=", "?sort=", "&sort=")):
        return False
    
    # Strong product URL indicators (platform-agnostic)
    strong_product_tokens = (
        "/p/", "/product/", "/producto/", "/item/", "/sku/", "/prod/",
        ".producto", "/products/", "/articulo/", "/art/",
        "/dp/", "/gp/product/", "/i/"
    )
    if any(token in u for token in strong_product_tokens):
        return True
    
    # VTEX-style product URLs ending with '/p'
    if u.rstrip('/').endswith('/p'):
        return True
    
    # Numeric product IDs (common e-commerce pattern)
    if re.search(r'/\d{6,}', u):  # 6+ digit numbers often indicate product IDs
        return True
    
    # Dynamic query-based filtering (if search terms provided)
    if query_terms:
        # Check if URL contains any search terms (indicates relevance)
        query_lower = [term.lower() for term in query_terms if len(term) > 2]
        if any(term in u for term in query_lower):
            # URL contains search terms AND has deep structure = likely product
            if len(u.split('/')) >= 4:
                return True
    
    # Deep URL structure often indicates specific items (products)
    if len(u.split('/')) >= 5:  # Deep paths often lead to specific items
        # Additional validation: should contain meaningful path segments
        path_segments = u.split('/')[3:]  # Skip protocol and domain
        meaningful_segments = [s for s in path_segments if len(s) > 2 and not s.isdigit()]
        if len(meaningful_segments) >= 2:  # At least 2 meaningful path parts
            return True
    
    return False


def _extract_links_from_html(html_content: str, base_url: str) -> List[str]:
    """
    Extract additional links from HTML content that might have been missed
    by the web crawler's link extraction.
    """
    if not html_content:
        return []
    
    links = []
    try:
        # Extract href attributes from anchor tags
        href_pattern = r'href=["\']([^"\']+)["\']'
        href_matches = re.findall(href_pattern, html_content, re.IGNORECASE)
        
        # Extract data-href and data-url attributes (common in JS-heavy sites)
        data_href_pattern = r'data-href=["\']([^"\']+)["\']'
        data_url_pattern = r'data-url=["\']([^"\']+)["\']'
        
        data_href_matches = re.findall(data_href_pattern, html_content, re.IGNORECASE)
        data_url_matches = re.findall(data_url_pattern, html_content, re.IGNORECASE)
        
        # Extract URLs from onclick handlers and other JS patterns
        onclick_pattern = r'onclick=["\'][^"\']*["\']([^"\']+)["\'][^"\']*["\']'
        js_url_pattern = r'(?:window\.location|location\.href)\s*=\s*["\']([^"\']+)["\']'
        
        onclick_matches = re.findall(onclick_pattern, html_content, re.IGNORECASE)
        js_url_matches = re.findall(js_url_pattern, html_content, re.IGNORECASE)
        
        # Combine all extracted URLs
        all_matches = href_matches + data_href_matches + data_url_matches + onclick_matches + js_url_matches
        
        # Convert relative URLs to absolute
        for match in all_matches:
            if match.startswith('http'):
                links.append(match)
            elif match.startswith('/'):
                links.append(urljoin(base_url, match))
            elif not match.startswith('#') and not match.startswith('javascript:'):
                links.append(urljoin(base_url, match))
        
        logger.debug(f"Extracted {len(links)} additional links from HTML content")
        
    except Exception as e:
        logger.debug(f"Error extracting links from HTML: {e}")
    
    return links


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
        self.batch_retriever = BatchContentRetriever()
        logger.info(f"CategoryExpansionAgent initialized with batch retrieval enabled")
    
    async def _llm_classify_urls(self, urls: List[str], query: str) -> List[str]:
        """
        Use LLM to classify URLs as product-related based on the search query.
        This is a fallback when structural patterns aren't sufficient.
        """
        if not urls or not query:
            return []
        
        try:
            # Batch URLs for efficiency (limit to reasonable batch size)
            batch_size = 20
            classified_product_urls = []
            
            for i in range(0, len(urls), batch_size):
                batch_urls = urls[i:i + batch_size]
                
                prompt = f"""Given the search query "{query}", classify which of these URLs are likely product pages (not categories, search results, or navigation pages).

URLs to classify:
{chr(10).join(f"{idx+1}. {url}" for idx, url in enumerate(batch_urls))}

Return ONLY a JSON array of the URL numbers (1-{len(batch_urls)}) that are likely product pages.
Example: [1, 3, 5] means URLs 1, 3, and 5 are product pages.
Return empty array [] if none are product pages."""

                try:
                    async with OllamaClient() as llm:
                        response = await llm.generate(
                            prompt=prompt,
                            model="qwen2.5:7b",
                            temperature=0.0,
                            format="json"
                        )
                        
                        # Parse the response
                        indices = json.loads(response.strip())
                        if isinstance(indices, list):
                            for idx in indices:
                                if isinstance(idx, int) and 1 <= idx <= len(batch_urls):
                                    classified_product_urls.append(batch_urls[idx - 1])
                        
                        logger.debug(f"LLM classified {len(indices)}/{len(batch_urls)} URLs as products")
                        
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"LLM classification failed for batch: {e}")
                    continue
            
            logger.info(f"LLM classification: {len(classified_product_urls)}/{len(urls)} URLs identified as products")
            return classified_product_urls
            
        except Exception as e:
            logger.warning(f"LLM URL classification failed: {e}")
            return []

    async def expand(self, category_urls: List[str], query_terms: Optional[List[str]] = None, timeout_ms: int = 30000) -> List[str]:
        if not category_urls:
            return []
        
        logger.info(f"🚀 OPTIMIZATION: Batch expanding {len(category_urls)} category URLs")
        product_links: List[str] = []
        
        try:
            # Use bulk crawl with link extraction for better performance
            async with WebCrawlerClient() as crawler:
                response = await crawler.crawl(
                    urls=category_urls,
                    max_pages=1,  # Only crawl the category pages themselves
                    max_depth=1,  # No link following
                    timeout=timeout_ms,
                    max_total_time=120,  # 2 minute total timeout
                    max_concurrent_pages=3  # Reasonable concurrency for category pages
                )
                
                if response.success and response.results:
                    for result in response.results:
                        domain = urlparse(result.url).netloc
                        count_domain = sum(1 for l in product_links if urlparse(l).netloc == domain)
                        
                        # Collect all links from multiple sources
                        all_links = []
                        
                        # 1. Use web crawler's extracted links
                        if result.links:
                            crawler_links = [l for l in result.links if _same_domain(result.url, l)]
                            all_links.extend(crawler_links)
                            logger.debug(f"Web crawler found {len(crawler_links)} same-domain links for {domain}")
                        
                        # 2. Extract additional links from HTML content
                        if hasattr(result, 'text') and result.text:
                            html_links = _extract_links_from_html(result.text, result.url)
                            html_same_domain = [l for l in html_links if _same_domain(result.url, l)]
                            all_links.extend(html_same_domain)
                            logger.debug(f"HTML parsing found {len(html_same_domain)} additional same-domain links for {domain}")
                        
                        # 3. Deduplicate and filter for product URLs
                        unique_links = _dedupe_preserve_order(all_links)
                        filtered = [l for l in unique_links if _likely_product_url(l, query_terms)]
                        
                        logger.info(f"Domain {domain}: {len(all_links)} total links → {len(unique_links)} unique → {len(filtered)} product URLs")
                        
                        # Apply per-domain cap
                        for l in filtered:
                            if count_domain >= self.per_domain_cap:
                                logger.debug(f"Reached per-domain cap ({self.per_domain_cap}) for {domain}")
                                break
                            product_links.append(l)
                            count_domain += 1
                            
                            if len(product_links) >= self.global_cap:
                                logger.debug(f"Reached global cap ({self.global_cap})")
                                break
                        
                        if len(product_links) >= self.global_cap:
                            break
                            
                    logger.info(f"Category expansion found {len(product_links)} product URLs from {len(category_urls)} categories")
                else:
                    logger.warning(f"Bulk category expansion failed: {response.error if hasattr(response, 'error') else 'Unknown error'}")
                    
        except Exception as e:
            logger.error(f"Category expansion batch request failed: {e}")
            
        # If we got very few results, try individual crawls as fallback
        if len(product_links) < 5 and len(category_urls) <= 3:
            logger.info("Low results from bulk crawl, trying individual page crawls as fallback")
            try:
                async with WebCrawlerClient() as crawler:
                    for category_url in category_urls:
                        if len(product_links) >= self.global_cap:
                            break
                            
                        try:
                            single_response = await crawler.crawl_single(
                                url=category_url,
                                timeout=timeout_ms
                            )
                            
                            if single_response.success and single_response.result:
                                result = single_response.result
                                domain = urlparse(result.url).netloc
                                count_domain = sum(1 for l in product_links if urlparse(l).netloc == domain)
                                
                                # Extract links using same logic as bulk crawl
                                all_links = []
                                
                                if result.links:
                                    crawler_links = [l for l in result.links if _same_domain(result.url, l)]
                                    all_links.extend(crawler_links)
                                
                                if hasattr(result, 'text') and result.text:
                                    html_links = _extract_links_from_html(result.text, result.url)
                                    html_same_domain = [l for l in html_links if _same_domain(result.url, l)]
                                    all_links.extend(html_same_domain)
                                
                                unique_links = _dedupe_preserve_order(all_links)
                                filtered = [l for l in unique_links if _likely_product_url(l, query_terms)]
                                
                                logger.info(f"Individual crawl {domain}: {len(filtered)} product URLs found")
                                
                                for l in filtered:
                                    if count_domain >= self.per_domain_cap or len(product_links) >= self.global_cap:
                                        break
                                    product_links.append(l)
                                    count_domain += 1
                            
                        except Exception as e:
                            logger.warning(f"Individual crawl failed for {category_url}: {e}")
                            
            except Exception as e:
                logger.error(f"Fallback individual crawls failed: {e}")
        
        # Final LLM fallback if we still have very few results and query terms available
        if len(product_links) < 3 and query_terms:
            logger.info("Very low results, trying LLM classification as final fallback")
            try:
                # Collect all unique URLs from previous crawls for LLM analysis
                all_collected_urls = []
                
                async with WebCrawlerClient() as crawler:
                    for category_url in category_urls:
                        try:
                            single_response = await crawler.crawl_single(
                                url=category_url,
                                timeout=15000  # Shorter timeout for fallback
                            )
                            
                            if single_response.success and single_response.result:
                                result = single_response.result
                                if result.links:
                                    same_domain_links = [l for l in result.links if _same_domain(result.url, l)]
                                    all_collected_urls.extend(same_domain_links)
                                    
                        except Exception as e:
                            logger.debug(f"LLM fallback crawl failed for {category_url}: {e}")
                            continue
                
                if all_collected_urls:
                    # Remove duplicates and filter out obvious non-products
                    unique_urls = _dedupe_preserve_order(all_collected_urls)
                    # Basic filtering to reduce LLM load
                    candidate_urls = [
                        u for u in unique_urls 
                        if not any(bad in u.lower() for bad in ("/search", "/category", "?page=", "#"))
                    ]
                    
                    if candidate_urls:
                        query_string = " ".join(query_terms) if query_terms else ""
                        llm_classified = await self._llm_classify_urls(candidate_urls[:50], query_string)  # Limit for performance
                        
                        # Add LLM results to our product links
                        for url in llm_classified:
                            if len(product_links) >= self.global_cap:
                                break
                            if url not in product_links:  # Avoid duplicates
                                product_links.append(url)
                        
                        logger.info(f"LLM fallback added {len(llm_classified)} additional product URLs")
                        
            except Exception as e:
                logger.warning(f"LLM fallback classification failed: {e}")
            
        logger.info(f"Final category expansion result: {len(product_links)} product URLs")
        return _dedupe_preserve_order(product_links)[: self.global_cap]


