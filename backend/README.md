# Pipe Freeze-Risk Analyser Backend

FastAPI backend for the pipe freeze-risk analyser.

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies (includes the Allsolve SDK):
```bash
pip install -r requirements.txt
```

3. Put credentials in `backend/.env` (or the environment):
```bash
QS_ACCESS_KEY=your_access_key_here
QS_SECRET_KEY=your_secret_key_here
QS_HOST=https://allsolve.quanscient.com
```

Optional settings (see `app/config.py`):
- `SWEEP_AMBIENTS_C` — outside temperatures swept for the critical temperature, JSON list (default `[-5,-10,-15,-20,-25]`; your outside temperature is always added)
- `SIM_MAX_RUN_TIME_MINUTES` — Allsolve job time limit (default 15, the fast-start node maximum)

## Running the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Start Analysis (Allsolve)
```http
POST /api/analysis/start
Content-Type: application/json

{
  "pipe_material": "copper",
  "inner_diameter_mm": 15,
  "wall_thickness_mm": 1,
  "insulation": "foam_wrap",
  "insulation_thickness_mm": 13,
  "location": "outdoors",
  "outside_temp_c": -10,
  "cold_snap_hours": 8,
  "initial_water_temp_c": 10,
  "drip_flow_lpm": 0
}
```

`pipe_material`: `copper | steel | pvc | pex`; `insulation`: `fiberglass | foam_wrap | mineral_wool | none`;
`insulation_thickness_mm`: 5–50 (ignored without insulation); `location`: only `outdoors` is accepted in
this version (`FIXED_LOCATION` in `app/models/pipe_params.py`; others return 422).

The external heat transfer coefficient is not an input: it is estimated from the location and outside
temperature, and each location has fixed surroundings (see `app/analysis/environment.py`).

### Get Status
```http
GET /api/analysis/{analysis_id}/status
```

### Get Results
```http
GET /api/analysis/{analysis_id}/results
```

Returns `mode`, the water `series` at your outside temperature (`t_min/avg/max_water_c`, `ice_fraction`),
`h_out` (estimated), `surroundings_c`, `assumptions`, `t_onset_hours` (first ice), `t_blockage_hours` (90 % ice), `critical_ambient_c`, the per-temperature
`sweep`, and a `verdict` (`level`, `headline`, `details`, `actions`, `caveats`).

### Abort
```http
POST /api/analysis/{analysis_id}/abort
```

### Demo Mode (No SDK Required)
```http
POST /api/analysis/{analysis_id}/demo
Content-Type: application/json

{ ...same body as /start... }
```

Same response shape as `/results`, with `mode: "demo"`.

### WebSocket Updates
```
WS /api/analysis/{analysis_id}/ws
```

## How a full analysis runs

1. `app/allsolve/project_config.py` builds the project: concentric cylinders (water / wall / insulation)
   + `fragmentAll`, named regions, materials, variables (`T_amb`, `T_env`, `h_out`, `m_dot`, `t_end`, `dt`, …) and a coarse mesh.
2. `app/allsolve/simulation_runner.py` imports the project, waits for geometry and mesh, creates a
   `VariableOverrides` sweep over `T_amb` (with `T_env` and `h_out` in lockstep), attaches `sim/pipe_freeze.py` as the main script, runs it and
   reads the outputs per sweep step. If the sweep outputs can't be parsed, it falls back to one project per
   temperature, in parallel threads. Projects are deleted afterwards.
3. `app/analysis/` turns the series into events, the critical temperature and the verdict. The analytic
   model in `reference.py` powers demo mode and the insulation / drip suggestions.
