"""
Setup configuration for the web crawler package.
"""

from setuptools import setup, find_packages

setup(
    name="web_crawler",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "pydantic>=2.0.0",
        "loguru>=0.5.3",
        "aiohttp>=3.8.0",
        "beautifulsoup4>=4.9.3",
        "redis>=4.0.0",
        "psycopg2-binary>=2.9.0",
        "python-dotenv>=0.19.0",
        "psutil>=5.8.0",
        "crawl4ai>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-asyncio>=0.15.0",
            "black>=21.0.0",
            "isort>=5.9.0",
            "mypy>=0.910",
            "flake8>=3.9.0",
        ]
    },
    python_requires=">=3.8",
    author="Web Crawler Team",
    author_email="team@webcrawler.com",
    description="A high-performance web crawler with memory-adaptive features",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/web-crawler",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 