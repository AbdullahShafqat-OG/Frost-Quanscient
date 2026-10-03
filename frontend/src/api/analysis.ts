/**
 * Bridge between the yo frontend (PipeParams / PipeResult) and the as backend
 * (/api/analysis/* endpoints with different field names and response shape).
 *
 * Physical coefficients are computed client-side so the UI can show critical
 * flow, environment details and residence time without needing a new backend
 * endpoint.
 */

import type { PipeParams, PipeResult } from '@/types/pipe'

// ── Material constants (mirrors pipe_model.py from yo branch) ────────────────

const PIPE_K: Record<string, number> = {
  copper: 385, steel: 45, pvc: 0.19, pex: 0.40,
}

const INSULATION_K: Record<string, number | null> = {
  fiberglass: 0.040, foam_wrap: 0.036, mineral_wool: 0.039, none: null,
}
const WIND_SPEED = 3.0

// ── Churchill-Bernstein crossflow + linearised radiation ─────────────────────

function airCoefficient(surfaceC: number, ambientC: number, diameterM: number): number {
  const ts = surfaceC + 273.15
  const ta = ambientC + 273.15
  const film = (ts + ta) / 2
  const rho = 101325 / (287.05 * film)
  const mu = 1.716e-5 * Math.pow(film / 273.15, 1.5) * (273.15 + 111) / (film + 111)
  const k = 0.0241 * Math.pow(film / 273.15, 0.9)
  const nu = mu / rho
  const pr = nu / (k / (rho * 1006))
  const re = WIND_SPEED * diameterM / nu
  const nusselt = 0.3 + 0.62 * Math.sqrt(re) * Math.pow(pr, 1 / 3) /
    Math.pow(1 + Math.pow(0.4 / pr, 2 / 3), 0.25) *
    Math.pow(1 + Math.pow(re / 282000, 5 / 8), 4 / 5)
  const radiation = 0.8 * 5.670374419e-8 * (ts + ta) * (ts * ts + ta * ta)
  return nusselt * k / diameterM + radiation
}

// ── Thermal circuit coefficients ─────────────────────────────────────────────

interface Coeff {
  h_external: number
  h_internal: number
  reynolds: number
  pipe_k: number
  insulation_k: number | null
  velocity: number
  film_fraction: number
  resistance: number
  r_internal: number
}

function computeCoeff(p: PipeParams): Coeff {
  const ri = p.diameter_mm / 2000
  const ro = ri + p.wall_mm / 1000
  const rs = ro + p.insulation_mm / 1000
  const pipeK = PIPE_K[p.material]
  const insK = INSULATION_K[p.insulation_material]
  const area = Math.PI * ri * ri
  const velocity = p.flow_l_min / 60000 / area
  const reynolds = 1000 * velocity * 2 * ri / 0.0013

  let nuInternal = velocity === 0 ? 2.0 : 3.66
  if (reynolds > 2300) {
    const turbRe = Math.max(3000, reynolds)
    const friction = Math.pow(0.79 * Math.log(turbRe) - 1.64, -2)
    const pr = 4184 * 0.0013 / 0.6
    const turbulent = (friction / 8) * (turbRe - 1000) * pr /
      (1 + 12.7 * Math.sqrt(friction / 8) * (Math.pow(pr, 2 / 3) - 1))
    const blend = Math.min(1, (reynolds - 2300) / 700)
    nuInternal = 3.66 * (1 - blend) + turbulent * blend
  }
  const hInternal = nuInternal * 0.6 / (2 * ri)
  const rInternal = 1 / (2 * Math.PI * ri * hInternal)
  const rPipe = Math.log(ro / ri) / (2 * Math.PI * pipeK)
  const rInsulation = insK ? Math.log(rs / ro) / (2 * Math.PI * insK) : 0

  let hExternal = 10 // initial guess
  let surface = p.water_c / 2
  for (let i = 0; i < 30; i++) {
    hExternal = airCoefficient(surface, p.ambient_c, 2 * rs)
    const rAir = 1 / (2 * Math.PI * rs * hExternal)
    const predicted = p.ambient_c + (p.water_c / 2 - p.ambient_c) * rAir /
      (rInternal + rPipe + rInsulation + rAir)
    surface = (surface + predicted) / 2
  }

  const rExternal = 1 / (2 * Math.PI * rs * hExternal)
  const rWaterWall = rInternal + rPipe / 2
  const resistance = rWaterWall + rPipe / 2 + rInsulation + rExternal

  return {
    h_external: hExternal,
    h_internal: hInternal,
    reynolds,
    pipe_k: pipeK,
    insulation_k: insK,
    velocity,
    film_fraction: rInternal / rWaterWall,
    resistance,
    r_internal: rInternal,
  }
}

// ── Critical drip flow (steady-state inner-wall interface = 0 °C) ────────────

function computeCriticalFlow(p: PipeParams): number {
  if (p.ambient_c >= 0) return 0
  function outlet(flow: number): number {
    const c = computeCoeff({ ...p, flow_l_min: flow })
    return p.ambient_c + (p.water_c - p.ambient_c) *
      Math.exp(-p.length_m / (1000 * 4184 * (flow / 60000) * c.resistance)) *
      (1 - c.r_internal / c.resistance)
  }
  let low = 0, high = 1
  while (outlet(high) <= 0) high *= 2
  for (let i = 0; i < 50; i++) {
    const mid = (low + high) / 2
    if (outlet(mid) > 0) high = mid; else low = mid
  }
  return high
}

// ── Parameter translation (frontend → as backend field names) ────────────────

function clamp(v: number, lo: number, hi: number) { return Math.min(hi, Math.max(lo, v)) }

function toBackendParams(p: PipeParams): Record<string, unknown> {
  return {
    inner_diameter_mm: clamp(p.diameter_mm, 6, 100),
    wall_thickness_mm: clamp(p.wall_mm, 0.5, 10),
    pipe_material: p.material,
    insulation: p.insulation_material,
    // Backend always requires >= 5 even when none; value is unused when type = none
    insulation_thickness_mm: p.insulation_material !== 'none' ? clamp(p.insulation_mm, 5, 50) : 5,
    outside_temp_c: clamp(p.ambient_c, -40, -1),
    cold_snap_hours: clamp(p.duration_h, 1, 48),
    initial_water_temp_c: clamp(p.water_c, 1, 25),
    drip_flow_lpm: clamp(p.flow_l_min, 0, 1),
  }
}

// ── Result translation (as AnalysisResults → PipeResult) ────────────────────

const VERDICT_RISK: Record<string, 'freezing' | 'near' | 'above'> = {
  freezes: 'freezing',
  at_risk: 'near',
  safe: 'above',
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toFrontendResult(p: PipeParams, r: any): PipeResult {
  const c = computeCoeff(p)
  const series: { time_hours: number; t_min_water_c: number }[] = r.series ?? []

  const minTemp = series.length
    ? Math.min(...series.map(s => s.t_min_water_c))
    : p.ambient_c
  const lastTemp = series.length ? series[series.length - 1].t_min_water_c : p.ambient_c

  const history = series.map(s => ({
    hours: s.time_hours,
    temperature_c: s.t_min_water_c,
    // as backend only has bulk water; use same value for interface approximation
    interface_temperature_c: s.t_min_water_c,
  }))

  // Spatial profile: as backend has no per-distance data; synthesise 2-point
  const profile = c.velocity > 0
    ? [
        { distance_m: 0, temperature_c: p.water_c },
        { distance_m: p.length_m, temperature_c: Math.max(0, lastTemp) },
      ]
    : Array.from({ length: 5 }, (_, i) => ({
        distance_m: p.length_m * i / 4,
        temperature_c: Math.max(0, lastTemp),
      }))

  return {
    parameters: p,
    engine: r.mode === 'simulation' ? 'allsolve' : 'estimate',
    model_version: 'frost-as-v1',
    risk: VERDICT_RISK[r.verdict?.level] ?? 'above',
    freeze_hours: r.t_onset_hours ?? null,
    end_hours: r.window_hours ?? p.duration_h,
    minimum_c: Math.max(0, minTemp),
    minimum_wall_c: Math.max(0, minTemp),
    minimum_interface_c: Math.max(0, minTemp),
    critical_flow_l_min: computeCriticalFlow(p),
    flow_threshold_note:
      'Flow must exceed this estimate to keep the inner-wall interface above 0 °C at steady state.',
    assumptions: r.assumptions ?? [],
    environment: {
      wind_m_s: WIND_SPEED,
      external_h_w_m2k: r.h_out ?? c.h_external,
      internal_h_w_m2k: c.h_internal,
      reynolds: c.reynolds,
      pipe_k_w_mk: c.pipe_k,
      insulation_k_w_mk: c.insulation_k,
    },
    residence_minutes: c.velocity > 0 ? p.length_m / c.velocity / 60 : null,
    history,
    profile,
  }
}

// ── Low-level fetch wrapper ───────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
  const response = await fetch('/api/analysis' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `Simulation request failed (${response.status}). Check that the backend is running.`,
    )
  }
  return response.json()
}

// ── Public API ────────────────────────────────────────────────────────────────

/** Run a local (demo) estimate. Returns immediately. */
export async function runEstimate(p: PipeParams, signal?: AbortSignal): Promise<PipeResult> {
  const body = JSON.stringify(toBackendParams(p))
  const { analysis_id } = await apiFetch('/start', { method: 'POST', body, signal })
  const results = await apiFetch(`/${analysis_id}/demo`, { method: 'POST', body, signal })
  return toFrontendResult(p, results)
}

/** Queue an Allsolve cloud job. Returns the analysis ID. */
export async function startJob(p: PipeParams, signal?: AbortSignal): Promise<string> {
  const body = JSON.stringify(toBackendParams(p))
  const { analysis_id } = await apiFetch('/start', { method: 'POST', body, signal })
  return analysis_id
}

export interface JobStatus {
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  result?: PipeResult
}

/** Poll an in-flight Allsolve job. Fetches results when status = completed. */
export async function pollJob(id: string, p: PipeParams, signal?: AbortSignal): Promise<JobStatus> {
  const status = await apiFetch(`/${id}/status`, { signal })
  if (status.status === 'completed') {
    const results = await apiFetch(`/${id}/results`, { signal })
    return { status: 'completed', progress: 100, message: 'Complete', result: toFrontendResult(p, results) }
  }
  if (status.status === 'failed') {
    return { status: 'failed', progress: status.progress ?? 0, message: status.message ?? 'Simulation failed.' }
  }
  return { status: status.status, progress: status.progress ?? 0, message: status.message ?? '' }
}
