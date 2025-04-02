from setuptools import setup, find_packages

setup(
    name="web-research-agent",
    version="0.1.0",
    description="AI agent for web research using web crawler and LLM",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "agent-utils",  # Our shared utilities package
        "aiohttp>=3.9.0",
        "python-dateutil>=2.8.2",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "aioredis>=2.0.1",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "web-research-agent=web_research_agent.cli:main",
            "web-research-server=web_research_agent.server:main",
        ]
    },
    python_requires=">=3.8"
) 