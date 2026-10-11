"""FastAPI application entry point.

Run from the repository root with:

    uvicorn app.main:app --app-dir backend --reload

or from ``backend/`` with ``uvicorn app.main:app --reload``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router


app = FastAPI(
    title="Scheme Seva Prototype API",
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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
