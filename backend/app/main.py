"""FastAPI application entry point.

Run from the repository root with:

    uvicorn app.main:app --app-dir backend --reload

or from ``backend/`` with ``uvicorn app.main:app --reload``.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config as _config
from .api.auth_routes import router as auth_router
from .api.document_routes import router as document_router
from .api.notification_routes import router as notification_router
from .api.routes import repository, router
from .services.scheme_notifications import dispatch


def refresh_and_dispatch():
    repository.reload()
    dispatch(repository)


async def notify_periodically():
    while True:
        try:
            await asyncio.to_thread(refresh_and_dispatch)
        except Exception:
            logging.getLogger(__name__).warning("Scheme notification scan did not complete.")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app):
    if os.getenv("SCHEME_NOTIFICATIONS_ENABLED") != "true":
        yield
        return
    task = asyncio.create_task(notify_periodically())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    lifespan=lifespan,
    title="Yojna Connect API",
    version="0.1.0",
    description=(
        "Browse the researched government scheme catalogue and run a deterministic "
        "pre-screening check. Results are not approvals."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(document_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
