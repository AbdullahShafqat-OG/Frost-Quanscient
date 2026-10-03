"""Allsolve two-node pipe model: axial water transport + stationary wall heat capacity."""
import quanscient as qs
from utils import Mesh, Fields
from expressions import expr
from regions import reg

mesh = Mesh()
mesh.mesh = qs.mesh()
mesh.mesh.setphysicalregions(*reg.get_region_data())
mesh.skin = reg.get_next_free()
mesh.mesh.selectskin(mesh.skin)
mesh.mesh.partition()
mesh.mesh.load("gmsh:simulation.msh", mesh.skin, 1, 1)
fld = Fields()
fld.T = qs.field("h1")
fld.W = qs.field("h1")
fld.T.setorder(reg.water, 1)
fld.W.setorder(reg.water, 1)
fld.T.setvalue(reg.water, expr.T_initial)
fld.W.setvalue(reg.water, expr.T_initial)
speed = float(expr.velocity) / float(expr.length)
if speed > 0:
    fld.T.setconstraint(reg.inlet, expr.T_initial)

form = qs.formulation()
# Normalized coordinate x = distance / length. Mesh-dependent streamline
# diffusion stabilizes advection; validate mesh convergence for design work.
diffusivity = 0.6 / (1000 * 4184 * float(expr.length)**2) + speed / 240
form += qs.integral(reg.water,
    qs.dt(qs.dof(fld.T)) * qs.tf(fld.T)
    + diffusivity * qs.grad(qs.dof(fld.T)) * qs.grad(qs.tf(fld.T))
    + speed * qs.dx(qs.dof(fld.T)) * qs.tf(fld.T)
    + expr.rate_water * (qs.dof(fld.T) - qs.dof(fld.W)) * qs.tf(fld.T))
form += qs.integral(reg.water,
    qs.dt(qs.dof(fld.W)) * qs.tf(fld.W)
    + expr.rate_wall * (qs.dof(fld.W) - qs.dof(fld.T)) * qs.tf(fld.W)
    + expr.rate_environment * (qs.dof(fld.W) - expr.T_ambient) * qs.tf(fld.W))
stepper = qs.impliciteuler(form, qs.vec(form))
stepper.settolerance(1e-6)
stepper.setverbosity(0)
end = float(expr.t_end)
dt = float(expr.dt)

def output():
    now = qs.gettime()
    minimum = fld.T.allmin(reg.water, 2)[0] - 273.15
    wall_minimum = fld.W.allmin(reg.water, 2)[0] - 273.15
    interface = fld.T - expr.film_fraction * (fld.T - fld.W)
    interface_minimum = interface.allmin(reg.water, 2)[0] - 273.15
    qs.setoutputvalue("T_min_water", minimum, now)
    qs.setoutputvalue("T_min_wall", wall_minimum, now)
    qs.setoutputvalue("T_min_interface", interface_minimum, now)
    for i in range(41):
        x = max(1e-8, min(1 - 1e-8, i / 40))
        value = fld.T.allinterpolate(reg.water, [x, 0.01, 0])[0] - 273.15
        qs.setoutputvalue("profile_" + str(i), value, now)
    if qs.getrank() == 0:
        print(f"t={now:.3f}s: water={minimum:.3f} C, inner wall={interface_minimum:.3f} C")
    return interface_minimum, minimum, wall_minimum

temperatures = output()
steps = 0
while qs.gettime() < end - 1e-8 and temperatures[0] > 0:
    step_dt = min(dt, end - qs.gettime())
    stepper.allnext(relrestol=1e-6, maxnumit=100, timestep=step_dt)
    previous = temperatures
    temperatures = output()
    if max(abs(new - old) for new, old in zip(temperatures, previous)) / step_dt < 1e-8:
        dt = float(expr.dt_steady)
    steps += 1
    if steps > 20000:
        raise RuntimeError("Time-step limit exceeded; shorten the cold snap or refine the model.")
qs.setoutputvalue("total_time", qs.gettime())

