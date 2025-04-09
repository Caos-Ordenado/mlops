from setuptools import setup, find_packages

setup(
    name="research_agent",
    version="0.1.0",
    description="AI agent for research using web crawler and LLM",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "shared",  # Our shared utilities package
        "aiohttp>=3.9.0",
        "python-dateutil>=2.8.2",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "aioredis>=2.0.1",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "duckduckgo-search>=4.1.0",  # DuckDuckGo search functionality
        "langchain>=0.1.0",
        "beautifulsoup4>=4.12.0",
        "requests>=2.31.0",
        "lxml>=4.9.0",
        "brotli>=1.1.0",  # Add Brotli compression support
    ],
    python_requires=">=3.10",
) 