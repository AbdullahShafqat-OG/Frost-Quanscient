/**
 * Bridge between the yo frontend (PipeParams / PipeResult) and the as backend
 * (/api/analysis/* endpoints with different field names and response shape).
 *
 * Only field names are translated; every value shown comes from the backend.
 */

import type { AnalysisResults } from '@/types'
import type { PipeParams, PipeResult } from '@/types/pipe'

// ── Parameter translation (frontend → as backend field names) ────────────────
// The form's input ranges match the backend's validation limits, so values are
// passed through unchanged; out-of-range input is rejected by the backend.

function toBackendParams(p: PipeParams): Record<string, unknown> {
  return {
    inner_diameter_mm: p.diameter_mm,
    wall_thickness_mm: p.wall_mm,
    pipe_material: p.material,
    insulation: p.insulation_material,
    // Backend always requires >= 5 even when none; value is unused when type = none
    insulation_thickness_mm: p.insulation_material !== 'none' ? p.insulation_mm : 5,
    outside_temp_c: p.ambient_c,
    cold_snap_hours: p.duration_h,
    initial_water_temp_c: p.water_c,
    drip_flow_lpm: p.flow_l_min,
  }
}

// ── Result translation (as AnalysisResults → PipeResult) ────────────────────

const VERDICT_RISK: Record<string, 'freezing' | 'near' | 'above'> = {
  freezes: 'freezing',
  at_risk: 'near',
  safe: 'above',
}

function toFrontendResult(p: PipeParams, r: AnalysisResults): PipeResult {
  return {
    parameters: p,
    engine: r.mode === 'simulation' ? 'allsolve' : 'estimate',
    risk: VERDICT_RISK[r.verdict.level],
    raw: r,
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
