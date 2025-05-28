from setuptools import setup, find_packages

setup(
    name="product_search_agent",
    version="0.1.0",
    description="A FastAPI agent for product search queries.",
    author="Your Name",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-dotenv"
    ],
    entry_points={
        "console_scripts": [
            "product_search_agent=src.api.app:app"
        ]
    },
    include_package_data=True,
    zip_safe=False,
) 