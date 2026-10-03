"""Pipe freeze-risk input parameters, property tables and result models."""

from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class PipeMaterial(str, Enum):
    """Pipe wall materials."""

    COPPER = "copper"
    STEEL = "steel"
    PVC = "pvc"
    PEX = "pex"


class InsulationType(str, Enum):
    """Pipe insulation options."""

    NONE = "none"
    FIBERGLASS = "fiberglass"
    FOAM_WRAP = "foam_wrap"
    MINERAL_WOOL = "mineral_wool"


class Location(str, Enum):
    """Where the pipe runs; each location has fixed surroundings (see analysis/environment.py)."""

    UNDERGROUND = "underground"
    INDOORS = "indoors"  # Inside walls or building infrastructure
    OUTDOORS = "outdoors"  # Any exposed pipe


# Pipe wall properties: k [W/(m·K)], rho [kg/m³], cp [J/(kg·K)]
PIPE_MATERIALS = {
    PipeMaterial.COPPER: {"label": "Copper", "k": 400.0, "rho": 8960.0, "cp": 385.0},
    PipeMaterial.STEEL: {"label": "Steel", "k": 50.0, "rho": 7850.0, "cp": 490.0},
    PipeMaterial.PVC: {"label": "PVC", "k": 0.19, "rho": 1380.0, "cp": 1000.0},
    PipeMaterial.PEX: {"label": "PEX", "k": 0.4, "rho": 940.0, "cp": 2300.0},
}

# Insulation properties: k [W/(m·K)], rho [kg/m³], cp [J/(kg·K)]
INSULATION_MATERIALS = {
    InsulationType.FIBERGLASS: {"label": "Fiberglass", "k": 0.035, "rho": 64.0, "cp": 840.0},
    InsulationType.FOAM_WRAP: {"label": "Foam wrap", "k": 0.038, "rho": 30.0, "cp": 1500.0},
    InsulationType.MINERAL_WOOL: {"label": "Mineral wool", "k": 0.037, "rho": 100.0, "cp": 840.0},
}

# Where the pipe is: frozen to the most stable, well-defined placement.
# Outdoors the pipe sees the outside temperature directly and constantly, with
# a single fixed assumption (wind); indoors and underground depend on assumed
# building heating / soil properties and time-varying soil temperature. The
# other locations stay implemented; change this to allow them again.
FIXED_LOCATION: Optional[Location] = Location.OUTDOORS

# Drip flow is assumed to serve this length of cold pipe run
DRIP_RUN_LENGTH_M = 3.0

# Water / ice properties
WATER_RHO = 1000.0  # kg/m³
WATER_CP = 4186.0  # J/(kg·K)
WATER_K = 0.6  # W/(m·K), stagnant (no internal convection)
ICE_K = 2.2  # W/(m·K)
LATENT_HEAT = 334e3  # J/kg
FREEZE_TEMP_C = 0.0

# Ice fraction at which the pipe is considered blocked
BLOCKAGE_ICE_FRACTION = 0.9


class PipeParams(BaseModel):
    """User inputs for a freeze-risk analysis."""

    # Pipe
    pipe_material: PipeMaterial = Field(default=PipeMaterial.COPPER)
    inner_diameter_mm: float = Field(default=15.0, ge=6.0, le=100.0)
    wall_thickness_mm: float = Field(default=1.0, ge=0.5, le=10.0)
    insulation: InsulationType = Field(default=InsulationType.NONE)
    insulation_thickness_mm: float = Field(
        default=13.0, ge=5.0, le=50.0, description="Ignored when insulation is 'none'"
    )

    # External conditions
    location: Location = Field(
        default=Location.OUTDOORS,
        description="Fixed to 'outdoors' in this version (see FIXED_LOCATION)",
    )
    outside_temp_c: float = Field(default=-10.0, ge=-40.0, le=-1.0)
    cold_snap_hours: float = Field(default=8.0, ge=1.0, le=48.0)

    # Water
    initial_water_temp_c: float = Field(
        default=10.0,
        ge=1.0,
        le=25.0,
        description="Water temperature when the cold snap starts; also the drip supply temperature",
    )
    drip_flow_lpm: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Drip flow in L/min (0 = stagnant)"
    )

    @field_validator("location")
    @classmethod
    def _location_is_fixed(cls, value: Location) -> Location:
        if FIXED_LOCATION is not None and value != FIXED_LOCATION:
            raise ValueError(f"location is fixed to '{FIXED_LOCATION.value}' in this version")
        return value

    # ---- Derived geometry (SI) ----
    @property
    def r_inner(self) -> float:
        return self.inner_diameter_mm / 2000.0

    @property
    def r_wall(self) -> float:
        return self.r_inner + self.wall_thickness_mm / 1000.0

    @property
    def has_insulation(self) -> bool:
        return self.insulation != InsulationType.NONE

    @property
    def r_outer(self) -> float:
        """Outermost radius (insulation surface if insulated)."""
        if self.has_insulation:
            return self.r_wall + self.insulation_thickness_mm / 1000.0
        return self.r_wall

    @property
    def m_dot(self) -> float:
        """Drip mass flow [kg/s]."""
        return self.drip_flow_lpm / 60.0 * WATER_RHO / 1000.0

    @property
    def window_hours(self) -> float:
        """Simulated duration: comfortably past the cold snap, capped at 48 h."""
        return min(max(1.5 * self.cold_snap_hours, 4.0), 48.0)

    def pipe_props(self) -> dict:
        return PIPE_MATERIALS[self.pipe_material]

    def insulation_props(self) -> Optional[dict]:
        return INSULATION_MATERIALS.get(self.insulation)


class AnalysisResponse(BaseModel):
    """Response when starting an analysis."""

    analysis_id: str
    status: str = "pending"
    message: str = "Analysis queued"


class AnalysisStatus(BaseModel):
    """Current status of a running analysis."""

    analysis_id: str
    status: str  # "pending", "running", "completed", "failed", "aborted"
    progress: float = Field(ge=0.0, le=100.0)
    message: Optional[str] = None


class SeriesPoint(BaseModel):
    """Water state at one point in time (at the given outside temperature)."""

    time_hours: float
    t_min_water_c: float
    t_avg_water_c: float
    t_max_water_c: float
    ice_fraction: float


class SweepPoint(BaseModel):
    """Freeze events for one outside temperature."""

    ambient_c: float
    t_onset_hours: Optional[float] = None
    t_blockage_hours: Optional[float] = None


class Verdict(BaseModel):
    """Plain-language outcome and advice."""

    level: Literal["safe", "at_risk", "freezes"]
    headline: str
    details: List[str] = []
    actions: List[str] = []
    caveats: List[str] = []


class AnalysisResults(BaseModel):
    """Complete results of an analysis (simulation or demo)."""

    analysis_id: str
    mode: Literal["simulation", "demo"]
    status: str = "completed"
    parameters: PipeParams
    h_out: float  # Estimated external heat transfer coefficient [W/(m²·K)]
    surroundings_c: float  # What the pipe sees at the end of the cold snap [°C]
    assumptions: List[str]  # Fixed conditions for the chosen location
    window_hours: float
    series: List[SeriesPoint]
    t_onset_hours: Optional[float] = None
    t_blockage_hours: Optional[float] = None
    critical_ambient_c: Optional[float] = None
    critical_note: Optional[str] = None
    sweep: List[SweepPoint] = []
    verdict: Verdict
