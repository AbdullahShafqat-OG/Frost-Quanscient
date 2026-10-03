"""Local estimates and asynchronous Allsolve pipe jobs (single-process demo)."""
import logging
import threading
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from .pipe_model import PipeParams, simulate

router = APIRouter(prefix="/api/pipe", tags=["Pipe freezing"])
jobs = {}
cloud_lock = threading.Lock()
logger = logging.getLogger("frost.simulation")


@router.post("/estimate")
def estimate(params: PipeParams):
    logger.debug("Local estimate parameters: %s", params.model_dump())
    return simulate(params)


def run_job(job_id, params):
    from .pipe_cloud import run_cloud, CloudRunError
    job = jobs[job_id]
    def progress(message, value):
        logger.info("Allsolve job %s: %.0f%% %s", job_id, value, message)
        job.update(message=message, progress=value)
    try:
        job.update(status="running")
        result = run_cloud(params, progress)
        job.update(status="completed", progress=100, result=result, message="Complete")
        logger.info("Allsolve job %s completed", job_id)
    except CloudRunError as exc:
        logger.warning("Allsolve job %s: %s", job_id, exc)
        job.update(status="failed", message=str(exc))
    except Exception:
        logging.exception("Pipe cloud job failed")
        job.update(status="failed", message="Allsolve could not complete this run. Check backend logs, credentials and cloud quota. Existing cloud results are preserved.")
    finally:
        cloud_lock.release()


@router.post("/start")
def start(params: PipeParams, background_tasks: BackgroundTasks):
    if not cloud_lock.acquire(blocking=False):
        raise HTTPException(409, "An Allsolve pipe run is already active. Wait for it to finish.")
    job_id = str(uuid.uuid4())
    logger.debug("Allsolve job %s queued; parameters: %s", job_id, params.model_dump())
    jobs[job_id] = {"id": job_id, "status": "pending", "progress": 0, "message": "Connecting to Allsolve"}
    background_tasks.add_task(run_job, job_id, params)
    return jobs[job_id]


@router.get("/{job_id}")
def status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Simulation not found; the backend may have restarted.")
    return jobs[job_id]

