from fastapi import APIRouter
from research_agent.api.research import router as research_router

api_router = APIRouter()
api_router.include_router(research_router) 