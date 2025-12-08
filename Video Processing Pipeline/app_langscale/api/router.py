# app_langscale/api/router.py

from fastapi import APIRouter
from .endpoints import router as detection_router

api_router = APIRouter()
api_router.include_router(detection_router, prefix="/api", tags=["Language Detection"])



