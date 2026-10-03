# Frost — Water Pipe Freezing Simulator

An interactive demo for exploring cold-weather exposure of water infrastructure.
Configure an exposed pipe and compare the effect of ambient temperature, exposure
duration, pipe length and diameter, wall material, insulation and continuous flow.

The application predicts **bulk-water freezing onset**, shows temperatures along
the pipe and over time, compares up to four scenarios, and exports a temperature
history with its input parameters as CSV.

## Run locally

Use Python 3.10+ and Node.js 18+.

Backend (PowerShell, from the project root):

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Frontend (another terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API documentation is at http://localhost:8000/docs.
The frontend proxies /api to port 8000.

## Calculation engines

**Quick estimate** runs locally without Allsolve credentials. An analytical
plug-flow solution uses the same cylindrical radial resistance as the cloud model.
This is the default engine, including the initial example.

**Quanscient Allsolve** runs a reduced axial thermal FEM model in the cloud.
Install the SDK and configure your Organization API credentials:

```powershell
.\venv\Scripts\python.exe -m pip install "allsolve>=0.5.0"
```

Create backend/.env (never commit credentials):

```dotenv
ALLSOLVE_ACCESS_KEY=your_key
ALLSOLVE_SECRET_KEY=your_secret
ALLSOLVE_HOST=https://allsolve.quanscient.com/
```

The SDK also accepts the existing QS_ACCESS_KEY, QS_SECRET_KEY and QS_HOST
environment variable names. Select the Allsolve engine in the interface and run.
The backend checks compute quota, builds geometry, meshes, solves, and retrieves
water temperatures. Jobs use account compute credits. Successful cloud results
are cached by inputs and solver-script version. Each scenario has a dedicated
cache/project under backend/.allsolve_cache/pipe/. Cloud projects and results
are preserved, including on failure; existing incomplete projects require
inspection before another run. The demo supports one concurrent cloud job and
stores job status in memory, so use a single backend process.

## Model and interpretation

For inner radius ri, outer pipe radius ro and outer insulation radius rs, the
resistance per unit length is:

```text
R' = ln(ro/ri)/(2π k_pipe)
   + ln(rs/ro)/(2π k_insulation)
   + 1/(2π rs h_external)
tau = rho cp A R'
v = Q/A
```

Water starts uniformly at the inlet temperature. Ambient and inlet temperatures,
flow and material properties stay constant. In the analytical model, water
cools for the smaller of the elapsed exposure and the travel time from the inlet:

```text
T(x,t) = T_ambient + (T_inlet - T_ambient) exp(-min(t,x/v)/tau)
```

At zero flow, cooling age is simply t everywhere. Consequently, length changes
total heat loss but does not change stagnant cooling time for a uniform pipe.

For subzero ambient, the analytical time to 0 °C is:

```text
t_freeze = tau ln((T_inlet - T_ambient)/(-T_ambient))
Q_critical = A L / t_freeze
```

Flow must be **strictly above** the threshold for a positive steady outlet
temperature. This threshold is analytical even when the temperature curve comes
from Allsolve. “No onset” means no bulk freezing within the specified exposure.
A pipe may remain above zero for a short exposure and freeze later.

The Allsolve model solves the reduced axial advection–diffusion–reaction equation
on a normalized 2D strip, uniform across its transverse direction. The flow is
prescribed, and wall/insulation heat loss is a distributed sink. It includes
water axial thermal diffusion and mesh-dependent diffusion to stabilize
advection. It is not a full conjugate CFD model. The custom solver script uses
kelvin internally and implicit Euler time stepping. Temperature histories and
profiles come from the cloud output; freezing onset is interpolated between
the final positive and first nonpositive temperature samples.

Both engines end at bulk freezing onset. They exclude local wall ice, latent
heat, blockage, bursting, pressure effects, gravity-driven convection, internal
film resistance, wall/insulation thermal mass, pipe-end losses, buried soil and
heat tracing. The uniform cross-section assumption is especially limited for
stagnant water. Use the demo for comparisons; installation design requires
validation and a fuller physical model.

Cylindrical resistance reference:
[Oak Ridge National Laboratory — Thermal Resistance Formula](https://industrialresources.ornl.gov/measur/suite/docs/group__insulated__pipe__reduction__thermal__resistance__formula).
Allsolve integration follows the local [SDK skills](sdk-skills/allsolve-sdk/SKILL.md)
and [thermal guide](sdk-skills/allsolve-domain-thermal/SKILL.md).

## API

| Endpoint | Purpose |
| --- | --- |
| POST /api/pipe/estimate | Immediate analytical result |
| POST /api/pipe/start | Queue an Allsolve cloud simulation |
| GET /api/pipe/{job_id} | Status, progress and completed result |
| GET /health | Health check |

The previous beer simulation source is retained for reference; it is not
registered with the API or used by the active interface.

## Verification

```powershell
cd backend
..\venv\Scripts\python.exe -m unittest discover -s tests -v
cd ../frontend
npm run build
```

Tests cover cooling and energy-balance invariants, insulation, flow thresholds,
exposure, validation, asynchronous job states and cloud result parsing.

