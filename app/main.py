"""Main FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import v1_router
from app.core.config import settings
from app.core.exceptions import TempChatException
from app.workers.expiration_worker import run_expiration_worker
from app.workers.storage_cleanup_worker import run_storage_cleanup_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background workers
    stop_event = asyncio.Event()
    app.state.stop_event = stop_event

    expiration_task = asyncio.create_task(run_expiration_worker(stop_event))
    cleanup_task = asyncio.create_task(run_storage_cleanup_worker(stop_event))

    yield

    # Shutdown: gracefully terminate workers
    stop_event.set()
    await asyncio.gather(expiration_task, cleanup_task, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Temporary-only, anonymous real-time messaging platform backend.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(TempChatException)
    async def domain_exception_handler(request: Request, exc: TempChatException):
        return exc.to_json_response()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload structure.",
                    "details": exc.errors(),
                },
            },
        )

    # Health probes at root level
    app.include_router(health_router)

    # API v1 routes
    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
