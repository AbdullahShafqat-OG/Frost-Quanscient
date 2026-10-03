# Frost pipe simulation backend

FastAPI backend for local pipe-freezing estimates and asynchronous Allsolve FEM jobs.
See [the root README](../README.md) for setup, inputs, model assumptions and credentials.

From the project root:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

API docs: http://localhost:8000/docs.

- POST /api/pipe/estimate returns an immediate analytical result.
- POST /api/pipe/start starts a cloud job.
- GET /api/pipe/{job_id} returns its status and results.
- GET /health checks the service.

The Allsolve SDK reads backend/.env or environment variables. Configure
ALLSOLVE_ACCESS_KEY and ALLSOLVE_SECRET_KEY for cloud runs. The existing QS_ names
are also supported. Quick estimates need no credentials.

Successful cloud simulations are reused by parameter/script fingerprint.
Existing cloud projects and results are preserved; incomplete projects require
inspection in Allsolve. Use one backend worker for this demo's in-memory jobs.

Run tests from backend with:

```powershell
..\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The former beer simulation modules are inactive reference code.

