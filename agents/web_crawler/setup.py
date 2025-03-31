from setuptools import setup, find_packages

setup(
    name="web_crawler",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "crawl4ai==0.5.0.post8",
        "loguru>=0.7.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "playwright>=1.41.0",  # Required by crawl4ai for browser automation
    ],
    python_requires=">=3.8",
) 