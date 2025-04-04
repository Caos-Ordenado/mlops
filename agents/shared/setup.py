from setuptools import setup, find_packages

setup(
    name="agent_utils",
    version="0.1.0",
    description="Shared utilities for AI agents",
    author="Your Name",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "aiohttp>=3.9.0",
        "python-dateutil>=2.8.2",
        "python-dotenv>=1.0.0",
        "sqlalchemy>=2.0.0",  # For database operations
        "alembic>=1.13.0",   # For database migrations
        "asyncpg>=0.29.0",   # Async PostgreSQL driver
        "redis>=5.0.0",      # For Redis operations
        "loguru>=0.7.0",     # For enhanced logging
        "beautifulsoup4>=4.12.0",  # Added for web crawler
        "pydantic>=2.0.0",   # Added for data validation
    ],
    python_requires=">=3.8",
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.23.0",
            "black>=24.0.0",
            "isort>=5.13.0",
        ]
    }
) 