# Web Crawler Agent

A Python-based web crawler agent using the Crawl4AI library for efficient web data extraction.

## Features

- Asynchronous web crawling
- Configurable crawling settings
- Respects robots.txt
- Extracts text and links from HTML content
- Logging support
- Error handling and recovery

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Then edit `.env` with your specific settings.

## Environment Variables

The crawler can be configured through environment variables. Copy `.env.example` to `.env` and adjust the values:

### Crawler Settings
- `CRAWLER_MAX_PAGES`: Maximum number of pages to crawl (default: 100)
- `CRAWLER_MAX_DEPTH`: Maximum crawl depth (default: 3)
- `CRAWLER_TIMEOUT`: Timeout in seconds (default: 30)
- `CRAWLER_USER_AGENT`: Custom user agent string

### Proxy Settings (Optional)
- `CRAWLER_PROXY_URL`: Proxy server URL
- `CRAWLER_PROXY_USERNAME`: Proxy authentication username
- `CRAWLER_PROXY_PASSWORD`: Proxy authentication password

### Browser Settings
- `CRAWLER_HEADLESS`: Run browser in headless mode (default: true)
- `CRAWLER_VIEWPORT_WIDTH`: Browser viewport width (default: 1920)
- `CRAWLER_VIEWPORT_HEIGHT`: Browser viewport height (default: 1080)

### Logging
- `CRAWLER_LOG_LEVEL`: Logging level (default: INFO)
- `CRAWLER_LOG_FILE`: Log file path (default: crawler.log)

## Usage

### Basic Usage

```python
from crawler import WebCrawlerAgent, CrawlerSettings

# Configure crawler settings
settings = CrawlerSettings(
    max_pages=10,
    max_depth=2,
    timeout=20
)

# Initialize crawler
crawler = WebCrawlerAgent(settings)

# Crawl a single URL
result = await crawler.crawl_url("https://example.com")

# Crawl multiple URLs
results = await crawler.crawl_urls([
    "https://example.com",
    "https://example.org"
])
```

### Configuration Options

The `CrawlerSettings` class supports the following options:

- `max_pages`: Maximum number of pages to crawl (default: 100)
- `max_depth`: Maximum crawl depth (default: 3)
- `respect_robots`: Whether to respect robots.txt (default: True)
- `user_agent`: Custom user agent string (default: "Crawl4AI Agent/1.0")
- `timeout`: Request timeout in seconds (default: 30)
- `allowed_domains`: List of allowed domains to crawl (default: None)
  - Include both with and without "www" prefix (e.g., ["example.com", "www.example.com"])
  - Don't include protocols (http:// or https://)
  - Don't include paths or query parameters
  - Examples:
    - Single website: `["example.com", "www.example.com"]`
    - Multiple related sites: `["example.com", "www.example.com", "subdomain.example.com"]`
    - Brand's sites: `["brand.com", "www.brand.com", "shop.brand.com"]`
  - If not set, crawler will follow any links found
- `exclude_patterns`: List of URL patterns to exclude (default: None)

### Example Script

Run the example script to see the crawler in action:

```bash
python src/example.py
```

### Output and Logging

The crawler provides detailed output in two ways:

1. Console Output:
   - Shows real-time progress of the crawl
   - Displays basic information about crawled pages
   - Shows any errors or issues during crawling

2. Log File (`crawler.log`):
   - Contains detailed logging information
   - Includes timestamps for each operation
   - Shows full crawl results including:
     - URL of the crawled page
     - Page title
     - Text content length
     - Number of links found
     - Preview of the text content
   - Log file rotates at 500MB to prevent disk space issues

Example log output:
```
2025-03-31 17:38:36.652 | INFO     | crawler:crawl_url:62 - Completed crawl of https://www.python.org/
2025-03-31 17:38:36.652 | INFO     | __main__:main:29 - Crawled URL: https://www.python.org/
2025-03-31 17:38:36.652 | INFO     | __main__:main:30 - Title: Welcome to Python.org
2025-03-31 17:38:36.652 | INFO     | __main__:main:31 - Text length: 17684
2025-03-31 17:38:36.652 | INFO     | __main__:main:32 - Links found: 2
```

## Integration with Agentic System

To integrate this crawler with your agentic system:

1. Import the `WebCrawlerAgent` class
2. Configure the settings according to your needs
3. Use the crawler's methods to extract data from web pages
4. Process the results in your agent's logic

Example integration:

```python
from crawler import WebCrawlerAgent, CrawlerSettings

class YourAgent:
    def __init__(self):
        self.crawler = WebCrawlerAgent()
    
    async def process_url(self, url: str):
        # Crawl the URL
        result = await self.crawler.crawl_url(url)
        
        # Extract text content
        text = result.get('text', '')
        
        # Extract links
        links = result.get('links', [])
        
        # Process the extracted data
        # Add your agent's logic here
```

## Browser Configuration

The crawler uses Playwright with Chromium by default. Browser settings can be customized:

```python
browser_config = BrowserConfig(
    browser_type="chromium",
    headless=True,
    java_script_enabled=True,
    ignore_https_errors=True,
    viewport_width=1920,
    viewport_height=1080
)
```

## Development

The project structure is:
```
web_crawler/
├── src/
│   ├── crawler.py      # Main crawler implementation
│   └── example.py      # Example usage
├── requirements.txt    # Project dependencies
└── setup.py           # Package configuration
```

## License

MIT License 