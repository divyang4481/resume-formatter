from fastapi import APIRouter
from .templates import router as templates_router

router = APIRouter()
router.include_router(templates_router)
