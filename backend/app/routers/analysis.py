"""Freeze-risk analysis API endpoints."""

import asyncio
import uuid
import logging
from typing import Dict, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)

from ..models import (
    PipeParams,
    AnalysisResponse,
    AnalysisStatus,
    AnalysisResults,
)
from ..analysis import run_demo
from ..allsolve.simulation_runner import SimulationRunner

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# In-memory storage for analysis state (use Redis/DB in production)
_analyses: Dict[str, dict] = {}
_websocket_connections: Dict[str, WebSocket] = {}


async def _notify(analysis_id: str, payload: dict) -> None:
    """Send a message to the analysis' WebSocket, if one is connected."""
    if analysis_id in _websocket_connections:
        try:
            await _websocket_connections[analysis_id].send_json(payload)
        except Exception:
            pass


@router.post("/start", response_model=AnalysisResponse)
async def start_analysis(
    params: PipeParams,
    background_tasks: BackgroundTasks,
) -> AnalysisResponse:
    """
    Start a full freeze-risk analysis on Allsolve.

    Returns immediately with an analysis ID. Use the status endpoint or
    WebSocket to monitor progress.
    """
    analysis_id = str(uuid.uuid4())

    logger.info("=" * 60)
    logger.info("❄️ NEW ANALYSIS REQUEST (ALLSOLVE)")
    logger.info("=" * 60)
    logger.info(f"   Analysis ID: {analysis_id}")
    logger.info(f"   Pipe: {params.inner_diameter_mm} mm {params.pipe_material.value}")
    logger.info(f"   Location: {params.location.value}, outside {params.outside_temp_c}°C for {params.cold_snap_hours} h")

    _analyses[analysis_id] = {
        "id": analysis_id,
        "params": params,
        "status": "pending",
        "progress": 0.0,
        "message": "Analysis queued",
        "results": None,
        "error": None,
        "runner": None,  # Will hold the SimulationRunner for abort
    }

    background_tasks.add_task(run_analysis_task, analysis_id, params)

    return AnalysisResponse(analysis_id=analysis_id, status="pending")


async def run_analysis_task(analysis_id: str, params: PipeParams) -> None:
    """Background task to run the analysis in a thread pool."""
    runner = SimulationRunner()
    state = _analyses[analysis_id]
    state["runner"] = runner

    def on_progress_sync(status: str, progress: float) -> None:
        """Synchronous progress callback (called from worker threads)."""
        logger.info(f"📈 Progress: {progress:.1f}% - {status}")
        if state["status"] in ("pending", "running"):
            state["status"] = "running"
            state["progress"] = progress
            state["message"] = status

    try:
        state["status"] = "running"

        # Run the blocking SDK calls in a thread pool to not block the event loop
        results = await asyncio.to_thread(
            runner.run_analysis_sync, analysis_id, params, on_progress_sync
        )

        if state["status"] == "aborted":
            return
        state["status"] = "completed"
        state["progress"] = 100.0
        state["results"] = results
        await _notify(analysis_id, {"type": "completed", "results": results.model_dump()})

    except Exception as e:
        if state["status"] == "aborted":
            logger.info(f"🛑 Analysis {analysis_id} stopped after abort ({e})")
            return
        logger.exception(f"❌ Analysis {analysis_id} failed: {e}")
        state["status"] = "failed"
        state["error"] = f"{type(e).__name__}: {e}"
        await _notify(analysis_id, {"type": "error", "error": str(e)})

    finally:
        await asyncio.to_thread(runner.cleanup)


@router.get("/{analysis_id}/status", response_model=AnalysisStatus)
async def get_analysis_status(analysis_id: str) -> AnalysisStatus:
    """Get the current status of an analysis."""
    if analysis_id not in _analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    state = _analyses[analysis_id]
    return AnalysisStatus(
        analysis_id=analysis_id,
        status=state["status"],
        progress=state["progress"],
        message=state["error"] if state["status"] in ("failed", "aborted") else state["message"],
    )


@router.post("/{analysis_id}/abort")
async def abort_analysis(analysis_id: str) -> dict:
    """Abort a running analysis."""
    if analysis_id not in _analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    state = _analyses[analysis_id]
    if state["status"] not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot abort analysis with status: {state['status']}",
        )

    runner = state.get("runner")
    if not runner:
        raise HTTPException(status_code=400, detail="No runner available to abort")

    state["status"] = "aborted"
    state["error"] = "Analysis aborted by user"
    await asyncio.to_thread(runner.abort)
    await _notify(analysis_id, {"type": "aborted", "message": "Analysis aborted by user"})

    logger.info(f"🛑 Analysis {analysis_id} aborted")
    return {"status": "aborted", "message": "Analysis aborted successfully"}


@router.get("/{analysis_id}/results", response_model=AnalysisResults)
async def get_analysis_results(analysis_id: str) -> AnalysisResults:
    """Get the results of a completed analysis."""
    if analysis_id not in _analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")

    state = _analyses[analysis_id]
    if state["status"] == "failed":
        raise HTTPException(status_code=500, detail=state.get("error") or "Analysis failed")
    if state["status"] != "completed":
        raise HTTPException(status_code=400, detail="Analysis not yet completed")

    return state["results"]


@router.websocket("/{analysis_id}/ws")
async def analysis_websocket(websocket: WebSocket, analysis_id: str):
    """WebSocket endpoint for real-time analysis updates."""
    await websocket.accept()

    if analysis_id not in _analyses:
        await websocket.send_json({"type": "error", "error": "Analysis not found"})
        await websocket.close()
        return

    _websocket_connections[analysis_id] = websocket

    try:
        state = _analyses[analysis_id]
        await websocket.send_json(
            {"type": "status", "status": state["status"], "progress": state["progress"]}
        )

        # Keep connection alive and wait for completion
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break

    finally:
        if analysis_id in _websocket_connections:
            del _websocket_connections[analysis_id]


@router.post("/{analysis_id}/demo", response_model=AnalysisResults)
async def run_demo_analysis(
    analysis_id: str,
    params: Optional[PipeParams] = None,
) -> AnalysisResults:
    """
    Local estimate without Allsolve (demo mode).

    Lumped-capacitance cooling with a latent-heat plateau at 0 °C. Returns the
    same shape as the full simulation results, with mode = "demo".
    """
    logger.info("⚠️ DEMO MODE - local lumped estimate, no Allsolve calls")
    return run_demo(analysis_id or str(uuid.uuid4()), params or PipeParams())
