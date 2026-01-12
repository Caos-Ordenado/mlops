import os
from dotenv import load_dotenv
from shared.logging import setup_logger
from src.api.app import app

if __name__ == "__main__":
    import uvicorn
    load_dotenv(override=True)
    logger = setup_logger("product_search_main")
    logger.add(
        "server.log",
        rotation="100 MB",
        retention="5 days",
        compression="zip",
        level=os.getenv("LOG_LEVEL", "DEBUG"),
        enqueue=True
    )
    uvicorn.run(app, host="0.0.0.0", port=8000) 