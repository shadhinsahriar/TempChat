"""Aggregated API v1 router."""

from fastapi import APIRouter

from app.api.v1.attachments import router as attachments_router
from app.api.v1.messages import router as messages_router
from app.api.v1.rooms import router as rooms_router
from app.websocket.endpoint import ws_router

v1_router = APIRouter()

# Core REST endpoints
v1_router.include_router(rooms_router)
v1_router.include_router(messages_router)
v1_router.include_router(attachments_router)

# WebSocket endpoint
v1_router.include_router(ws_router, prefix="/ws")
