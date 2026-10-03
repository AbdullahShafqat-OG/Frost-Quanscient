# ❄️ Pipe Freeze-Risk Analyser

A web application that answers: **how cold can it get, and for how long, before the water in my pipe freezes — and what should I change to prevent it?**

A pipe has no freezing point; water does. The app simulates a water pipe — underground, indoors (in walls or building infrastructure) or outdoors — cooling down and freezing, using the Allsolve FEM platform, and reports:

- the **critical outside temperature** for your cold-snap duration (the outside temperature at which the pipe is blocked with ice by the end of it),
- **time to first ice** and **time to blockage** at your outside temperature,
- a plain-language **verdict** with a concrete fix (insulation or drip flow).

## Inputs

| Group | Inputs |
|---|---|
| Pipe | wall thickness, inner diameter, material (copper / steel / PVC / PEX), insulation (fiberglass / foam wrap / mineral wool / none), insulation thickness (5–50 mm) |
| External conditions | where the pipe is (**fixed to outdoors** in this version; shown but not selectable), outside temperature, cold snap duration |
| Water | initial water temperature, drip flow |

Outdoors is the most stable, well-defined placement: the pipe sees the outside temperature directly and constantly, with one fixed assumption (wind). Indoors and underground stay implemented (`FIXED_LOCATION` in `backend/app/models/pipe_params.py`) but are disabled.

### Fixed conditions per location (approximations)

| Location | Surroundings | External heat transfer |
|---|---|---|
| Outdoors | outside air | forced convection at a constant 3 m/s wind (or natural convection if stronger) + radiation; no sun or clear-sky cooling |
| Indoors | wall cavity / unheated space at outside + 30 % × (20 °C − outside); building heated to 20 °C | still-air natural convection + radiation |
| Underground | soil at 0.45 m depth (moist loam, initially 5 °C) cooling as the surface cold soaks in: T = T₀ + (T_out − T₀)·erfc(z / 2√(αt)) | buried-cylinder conduction resistance ln(2z/r)/(2πk); no soil freezing, no snow/turf cover |

Convection and radiation are evaluated with the pipe surface at ~0 °C, so h depends on the outside temperature. Other fixed values: the drip draws water at the initial water temperature and serves a 3 m cold run.

## Physics Model

Transient heat conduction in water, pipe wall and insulation (3D short pipe segment, adiabatic ends):

```
ρ Cₚ,eff ∂T/∂t = ∇ · (k ∇T) + Q_drip
```

The SDK has no phase-change physics, so freezing is modelled by hand with an **apparent heat capacity** in the water (coefficients lagged one step to keep each solve linear):

```
ρ Cₚ,eff = ρ Cₚ + ρ L · exp(-((T - T_f)/ΔT)²) / (ΔT √π)      L = 334 kJ/kg, T_f = 0 °C, ΔT = 1 K
```

**Outer boundary** — heat exchange with the surroundings of the chosen location (see the table above):

```
q = h (T_surroundings - T_surface)
```

**Drip flow** (no CFD) — water at the initial temperature mixed into the cold run:

```
Q_drip = ṁ Cₚ (T_initial - T) / (A_water · 3 m)
```

**Events:** *first ice* = coldest water reaches 0 °C; *blocked* = 90 % of the water is ice. The critical temperature uses blockage: first ice comes within minutes in any sub-zero air, so on its own it would always give ~0 °C.

### Materials

| Material | k (W/m·K) | ρ (kg/m³) | Cₚ (J/kg·K) |
|----------|-----------|-----------|-------------|
| Copper | 400 | 8960 | 385 |
| Steel | 50 | 7850 | 490 |
| PEX | 0.4 | 940 | 2300 |
| PVC | 0.19 | 1380 | 1000 |
| Fiberglass | 0.035 | 64 | 840 |
| Foam wrap | 0.038 | 30 | 1500 |
| Mineral wool | 0.037 | 100 | 840 |
| Water (liquid / ice) | 0.6 / 2.2 | 1000 | 4186 |

### Modes

- **Full simulation (Allsolve)** — one cloud project with a sweep over outside temperatures (default −5 … −25 °C plus yours; surroundings and h swept in lockstep); the critical temperature is interpolated from the sweep (log time vs temperature).
- **Demo (local estimate)** — lumped-capacitance model on the backend, no Allsolve calls: series thermal resistance (wall + insulation + external), the same surroundings, a latent-heat plateau at 0 °C, drip heat input. Same response shape, labelled `mode: "demo"`.

### Model limits

No supercooling, no natural convection inside the water, no axial heat flow from adjacent warm pipe.

## Project Structure

```
beer_cooling_app/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── allsolve/     # Allsolve SDK integration (project config, runner + sweep)
│   │   ├── analysis/     # Reference model, freeze events, verdict
│   │   ├── models/       # Pydantic models + material tables
│   │   ├── routers/      # API endpoints
│   │   ├── config.py     # Environment-based settings
│   │   └── main.py       # FastAPI application
│   ├── sim/
│   │   └── pipe_freeze.py  # Quanscient simulation script
│   └── requirements.txt
├── frontend/             # Vue 3 frontend
│   ├── public/           # Static assets
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # Vue components
│   │   ├── stores/       # Pinia state management
│   │   └── types/        # TypeScript type definitions
│   └── package.json
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Allsolve SDK credentials (for full simulations; demo mode works without)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (includes the allsolve SDK)
pip install -r requirements.txt

# Credentials in backend/.env
#   QS_ACCESS_KEY=your_key
#   QS_SECRET_KEY=your_secret
#   QS_HOST=https://allsolve.quanscient.com

# Run server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Access the Application

- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

## Usage

1. **Pipe**: wall thickness, inner diameter, material, insulation
2. **External conditions**: where the pipe is, outside temperature, cold snap duration
3. **Water**: initial temperature, drip flow
4. **Pick a mode**: Full simulation (Allsolve) or Demo (local estimate)
5. **Read the verdict**: critical temperature, first ice / blockage times, advice, assumed conditions and the per-temperature table

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/start` | POST | Start a full analysis on Allsolve |
| `/api/analysis/{id}/status` | GET | Get analysis status |
| `/api/analysis/{id}/results` | GET | Get analysis results |
| `/api/analysis/{id}/abort` | POST | Abort a running analysis |
| `/api/analysis/{id}/demo` | POST | Local estimate (no SDK required) |
| `/api/analysis/{id}/ws` | WS | WebSocket for real-time updates |

## Credits

Built with:
- [Quanscient Allsolve](https://quanscient.com) - FEM simulation platform
- [Vue 3](https://vuejs.org) - Frontend framework
- [Chart.js](https://www.chartjs.org) - Charts
- [FastAPI](https://fastapi.tiangolo.com) - Backend framework
- [Tailwind CSS](https://tailwindcss.com) - Styling
