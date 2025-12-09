"""Routes module for Conversational Analytics."""
from fastapi import APIRouter

from .chat import router as chat_router
from .skills import router as skills_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(skills_router)

__all__ = ["router"]
