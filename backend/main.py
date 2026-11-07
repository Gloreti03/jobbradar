"""App FastAPI. Run (from backend/):  uv run uvicorn main:app --reload --port 8000
Interactive docs: http://localhost:8000/docs
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import FRONTEND_ORIGIN
from db import init_db
from llm import LLMError
from routers import applications, imports, interview, jobs, profile, radar, tracking, voice
from services.profile_extract import warm_up_ocr


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # load the OCR engine in the background: the first scanned upload would otherwise wait ~1 min
    threading.Thread(target=warm_up_ocr, name="ocr-warm-up", daemon=True).start()
    yield


app = FastAPI(title="RADAR API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    # any port on localhost (Vite may use 5174...) + Opera/Chrome extension
    allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://.*)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Errors always shaped as {"error": "message"} ---


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []))
    return JSONResponse(status_code=422, content={"error": f"Invalid request: {where} {first.get('msg', '')}".strip()})


@app.exception_handler(LLMError)
async def llm_error(request: Request, exc: LLMError):
    return JSONResponse(status_code=502, content={"error": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": f"Internal error: {exc}"})


# --- Routers (imports BEFORE jobs: /jobs/import vs /jobs/{job_id}) ---

app.include_router(profile.router)
app.include_router(applications.router)
app.include_router(tracking.router)
app.include_router(radar.router)
app.include_router(imports.router)
app.include_router(jobs.router)
app.include_router(interview.router)
app.include_router(voice.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
