"""Health and readiness probe endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health():
    return {
        "status": "healthy",
        "service": "tempchat-backend",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready", summary="Readiness probe")
async def readiness(session: AsyncSession = Depends(get_db_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unready",
                "database": "disconnected",
                "error": str(e),
            },
        )
