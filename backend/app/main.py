"""Frost water infrastructure simulation API."""
import logging
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .pipe_api import router

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("allsolve").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)
logger = logging.getLogger("frost.api")

app = FastAPI(title="Frost — Water Pipe Freezing", version="2.0.0",
              description="Pipe cooling and bulk freezing onset: local estimates and Allsolve cloud simulations.")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.middleware("http")
async def log_requests(request, call_next):
    started = time.perf_counter()
    logger.debug("Request: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request failed: %s %s", request.method, request.url.path)
        raise
    logger.debug("Response: %s %s -> %s (%.1f ms)", request.method,
                 request.url.path, response.status_code,
                 (time.perf_counter() - started) * 1000)
    return response


@app.get("/")
def root():
    return {"name": "Frost", "docs": "/docs", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
