from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.logging import setup_logger
from .routes import router

logger = setup_logger("product_search_api")

app = FastAPI(
    title="Product Search Agent API",
    description="Agent for searching product information.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)