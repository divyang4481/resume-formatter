from fastapi import APIRouter
from .resumes import router as resumes_router

router = APIRouter()
router.include_router(resumes_router)
