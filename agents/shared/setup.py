from setuptools import setup, find_packages

setup(
    name="agent-utils",
    version="0.1.0",
    description="Shared utilities for AI agents",
    author="Your Name",
    packages=find_packages(include=["agent_utils", "agent_utils.*"]),
    install_requires=[
        "aiohttp>=3.9.0",
        "python-dateutil>=2.8.2",
        "python-dotenv>=1.0.0"  # For .env file support
    ],
    python_requires=">=3.8"
) 