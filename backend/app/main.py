"""
Pipe Freeze-Risk API

A FastAPI application that estimates how cold it can get, and for how long,
before water in an exposed pipe freezes, using the Allsolve SDK.
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import analysis_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("allsolve").setLevel(logging.DEBUG)  # SDK internals (API calls, retries)
logger = logging.getLogger(__name__)

settings = get_settings()

logger.info("=" * 60)
logger.info("❄️ PIPE FREEZE-RISK ANALYSER BACKEND STARTING")
logger.info("=" * 60)
logger.info(f"   Allsolve Host: {settings.qs_host}")
logger.info(f"   API Key configured: {'✅ Yes' if settings.qs_access_key else '❌ No'}")
logger.info(f"   Debug mode: {settings.debug}")

app = FastAPI(
    title="Pipe Freeze-Risk Analyser API",
    description="""
    ❄️ How cold can it get, and for how long, before your water pipe freezes?

    This API provides endpoints to:
    - Start a freeze-risk analysis on Allsolve (or a local demo estimate)
    - Monitor progress in real-time
    - Retrieve water temperature / ice fraction curves, the critical ambient
      temperature and a plain-language verdict

    ## Physics Model

    Transient heat conduction in water, pipe wall and insulation:

    **ρ Cₚ,eff ∂T/∂t = ∇ · (k ∇T)**

    Freezing via an apparent heat capacity in the water:

    **ρ Cₚ,eff = ρ Cₚ + ρ L · exp(-((T-T_f)/ΔT)²) / (ΔT √π)**

    Convection + radiation on the outer surface, h = 5.7 + 3.8·v W/(m²·K):

    **q = h (T_ambient - T_surface)**
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "Pipe Freeze-Risk Analysis API",
        "docs": "/docs",
        "endpoints": {
            "start_analysis": "POST /api/analysis/start",
            "get_status": "GET /api/analysis/{id}/status",
            "get_results": "GET /api/analysis/{id}/results",
            "abort": "POST /api/analysis/{id}/abort",
            "demo": "POST /api/analysis/{id}/demo",
            "websocket": "WS /api/analysis/{id}/ws",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
