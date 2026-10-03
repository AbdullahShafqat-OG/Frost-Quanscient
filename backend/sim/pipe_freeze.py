"""
Pipe Freeze Simulation Script

This script runs on the Allsolve cloud platform to simulate a short segment of
an air-exposed water pipe cooling down and freezing.

Governing Equation:
    ρ * Cp_eff * ∂T/∂t = ∇ · (k * ∇T) + Q_drip

Freezing (apparent heat capacity, water region only):
    ρ * Cp_eff = ρ * Cp + ρ * L * exp(-((T - Tf)/ΔT)²) / (ΔT * √π)
    ice fraction = (1 - erf((T - Tf)/ΔT)) / 2
    k_water      = k_liquid + (k_ice - k_liquid) * ice fraction
The coefficients are evaluated from the previous-step temperature (lagged),
so each step stays a linear solve.

Drip flow (no CFD), volumetric source in the water:
    Q_drip = m_dot * Cp * (T_supply - T) / (A_water * L_exposed)

Boundary Conditions:
    Outer lateral surface: q = h_out * (T_env - T)
        T_env: outside air (outdoors), unheated space (indoors), or the soil
               temperature at burial depth, falling with time (underground)
        h_out: estimated by the backend from location and outside temperature
    Segment ends:          adiabatic (no term = zero flux)

Outputs (°C / fraction, at every output interval):
    T_min_water, T_max_water, T_avg_water, ice_fraction
"""

import math

import quanscient as qs
from utils import Mesh, Variables, Fields
from expressions import expr
from parameters import par
from regions import reg

# Initialize containers
var = Variables()
mesh = Mesh()
fld = Fields()

# ============================================================================
# CONSTANTS
# ============================================================================

RHO_W = 1000.0  # kg/m³
CP_W = 4186.0  # J/(kg·K)
K_W = 0.6  # W/(m·K), liquid water (stagnant)
K_ICE = 2.2  # W/(m·K)
L_F = 334e3  # J/kg, latent heat of fusion
T_F = 273.15  # K, freezing point
DT_F = 1.0  # K, half-width of the smeared phase change

# Stop once the water is (almost) solid; the curve is flat after that
STOP_ICE_FRACTION = 0.98

# ============================================================================
# MESH LOADING
# ============================================================================

mesh.mesh = qs.mesh()
mesh.mesh.setphysicalregions(*reg.get_region_data())
mesh.skin = reg.get_next_free()
mesh.mesh.selectskin(mesh.skin)
mesh.mesh.partition()
mesh.mesh.load("gmsh:simulation.msh", mesh.skin, 1, 1)

# ============================================================================
# FIELD DEFINITIONS
# ============================================================================

# Temperature field [K]
fld.T = qs.field("h1")
fld.T.setorder(reg.all_domain, 2)

# ============================================================================
# FREEZING MODEL (water region)
# ============================================================================

# Normalised distance from the freezing point
x = (fld.T - T_F) / DT_F

# Apparent volumetric heat capacity: sensible + Gaussian latent peak
rhocp_water = RHO_W * CP_W + RHO_W * L_F * qs.exp(-x * x) / (DT_F * math.sqrt(math.pi))

# Ice fraction = (1 - erf(x)) / 2, consistent with the Gaussian above.
# The solver has no erf/tanh, so: erf(x) ≈ tanh(2/√π · (x + 11x³/123)),
# tanh(y) = 1 - 2 / (exp(2y) + 1); x is clamped to keep exp() finite.
xc = qs.min(qs.max(x, -4.0), 4.0)
y = (2.0 / math.sqrt(math.pi)) * (xc + (11.0 / 123.0) * xc * xc * xc)
erf_x = 1.0 - 2.0 / (qs.exp(2.0 * y) + 1.0)
ice = 0.5 * (1.0 - erf_x)

k_water = K_W + (K_ICE - K_W) * ice

# ============================================================================
# INITIAL CONDITION
# ============================================================================

fld.T.setvalue(reg.all_domain, expr.T_init)

# ============================================================================
# WEAK FORMULATION
# ============================================================================

form = qs.formulation()

# Pipe wall (+ insulation): plain transient diffusion with material properties
#   predefineddiffusion(dof, tf, alpha, beta): alpha = k, beta = ρCp
form += qs.integral(
    reg.solid,
    qs.predefineddiffusion(qs.dof(fld.T), qs.tf(fld.T), par.k(), par.rho() * par.cp()),
)

# Water: diffusion with the (lagged) freezing coefficients
form += qs.integral(
    reg.water,
    qs.predefineddiffusion(qs.dof(fld.T), qs.tf(fld.T), k_water, rhocp_water),
)

# Surroundings temperature seen by the outer surface.
# Outdoors / indoors: constant T_env (outside air / unheated space).
# Underground: soil at the burial depth z cools as the surface cold soaks in
# (semi-infinite solid, surface stepped to T_env at t = 0):
#     T_soil(t) = T_ground0 + (T_env - T_ground0) * erfc(z / (2 sqrt(alpha t)))
# erfc via Abramowitz & Stegun 7.1.26 (solver has no erfc); +1 s avoids t = 0.
underground = int(round(float(expr.underground))) == 1
if underground:
    xs = float(expr.z_burial) / (2.0 * qs.sqrt(float(expr.alpha_soil) * (qs.t() + 1.0)))
    ts = 1.0 / (1.0 + 0.3275911 * xs)
    poly = ts * (0.254829592 + ts * (-0.284496736 + ts * (1.421413741 + ts * (-1.453152027 + ts * 1.061405429))))
    erfc_x = poly * qs.exp(-xs * xs)
    t_surroundings = expr.T_ground0 + (expr.T_env - expr.T_ground0) * erfc_x
else:
    t_surroundings = expr.T_env

# Heat exchange with the surroundings on the lateral outer surface. h_out is
# estimated by the backend from location and outside temperature; underground
# it is the soil conduction resistance expressed per unit outer surface.
# Sign: (T_env - T) means heat LEAVES when T > T_env -> cooling effect
form += qs.integral(
    reg.outer_surface,
    expr.h_out * (t_surroundings - qs.dof(fld.T)) * qs.tf(fld.T),
)

# Drip flow: warm supply water mixed into the exposed run
m_dot = float(expr.m_dot)
if m_dot > 0:
    drip_coeff = m_dot * CP_W / (float(expr.A_water) * float(expr.L_exposed))  # W/(m³·K)
    form += qs.integral(
        reg.water,
        drip_coeff * (expr.T_supply - qs.dof(fld.T)) * qs.tf(fld.T),
    )

# ============================================================================
# TIME STEPPING
# ============================================================================

# Implicit Euler; the matrices depend on the field so they are rebuilt each
# step from the previous-step temperature (lagged coefficients). RHS, K and C
# are flagged non-constant explicitly (the RHS is time-dependent underground).
# That 4-argument form is in the docstring but not the typed stubs, so fall
# back to auto-detection if this solver build rejects it.
try:
    timestepper = qs.impliciteuler(form, qs.vec(form), 1, [False, False, False])
except TypeError as e:
    if qs.getrank() == 0:
        print(f"  impliciteuler(isrhskcconstant) not supported ({e}); using auto-detection")
    timestepper = qs.impliciteuler(form, qs.vec(form))
timestepper.settolerance(1e-5)
timestepper.setverbosity(1)

dt = float(expr.dt)  # Time step [s]
t_end = float(expr.t_end)  # End time [s]
output_interval = float(expr.dt_out)  # [s]


def write_outputs(t):
    """Water statistics at time t; returns the ice fraction."""
    v_water = qs.allintegrate(reg.water, 1, 4)
    t_avg = qs.allintegrate(reg.water, fld.T, 4) / v_water
    ice_frac = qs.allintegrate(reg.water, ice, 4) / v_water

    # min/max with refinement 4, returns [value, x, y, z]
    t_min = fld.T.allmin(reg.water, 4)[0]
    t_max = fld.T.allmax(reg.water, 4)[0]

    if qs.getrank() == 0:
        print(
            f"  t={t:.0f}s: T_min={t_min - 273.15:.2f}°C T_avg={t_avg - 273.15:.2f}°C "
            f"ice={ice_frac * 100:.1f}%"
        )

    qs.setoutputvalue("T_min_water", t_min - 273.15, t)
    qs.setoutputvalue("T_max_water", t_max - 273.15, t)
    qs.setoutputvalue("T_avg_water", t_avg - 273.15, t)
    qs.setoutputvalue("ice_fraction", ice_frac, t)
    return ice_frac


# ============================================================================
# TIME LOOP
# ============================================================================

if qs.getrank() == 0:
    print("Starting pipe freeze simulation")
    print(f"  Outside temperature: {float(expr.T_amb) - 273.15:.1f}°C")
    print(f"  Surroundings: {float(expr.T_env) - 273.15:.1f}°C{' (ground surface)' if underground else ''}")
    print(f"  Initial water temperature: {float(expr.T_init) - 273.15:.1f}°C")
    print(f"  h_out: {float(expr.h_out):.1f} W/(m²·K), drip: {m_dot * 60:.3f} kg/min")
    print(f"  Duration: {t_end:.0f}s, time step: {dt:.1f}s")

write_outputs(0.0)
next_output_time = output_interval

while qs.gettime() < t_end - 1e-8 * dt:
    timestepper.allnext(relrestol=1e-6, maxnumit=100, timestep=dt)
    current_time = qs.gettime()

    if current_time >= next_output_time - 1e-8:
        ice_frac = write_outputs(current_time)
        next_output_time += output_interval

        if ice_frac >= STOP_ICE_FRACTION:
            if qs.getrank() == 0:
                print(f"  Water frozen solid at t={current_time:.0f}s, stopping early")
            break

if qs.getrank() == 0:
    print("Analysis point complete")
