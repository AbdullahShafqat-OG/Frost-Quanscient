/**
 * Type definitions for the Pipe Freeze-Risk Analyser
 */

export type PipeMaterial = 'copper' | 'steel' | 'pvc' | 'pex'
export type InsulationType = 'fiberglass' | 'foam_wrap' | 'mineral_wool' | 'none'
export type Location = 'underground' | 'indoors' | 'outdoors'

export interface PipeParams {
  // Pipe
  pipe_material: PipeMaterial
  inner_diameter_mm: number
  wall_thickness_mm: number
  insulation: InsulationType
  insulation_thickness_mm: number
  // External conditions
  location: Location
  outside_temp_c: number
  cold_snap_hours: number
  // Water
  initial_water_temp_c: number
  drip_flow_lpm: number
}

export interface AnalysisResponse {
  analysis_id: string
  status: string
  message: string
}

export type AnalysisState = 'pending' | 'running' | 'completed' | 'failed' | 'aborted'

export interface AnalysisStatus {
  analysis_id: string
  status: AnalysisState
  progress: number
  message?: string
}

export interface SeriesPoint {
  time_hours: number
  t_min_water_c: number
  t_avg_water_c: number
  t_max_water_c: number
  ice_fraction: number
}

export interface SweepPoint {
  ambient_c: number
  t_onset_hours: number | null
  t_blockage_hours: number | null
}

export type VerdictLevel = 'safe' | 'at_risk' | 'freezes'

export interface Verdict {
  level: VerdictLevel
  headline: string
  details: string[]
  actions: string[]
  caveats: string[]
}

export interface AnalysisResults {
  analysis_id: string
  mode: 'simulation' | 'demo'
  status: string
  parameters: PipeParams
  h_out: number
  surroundings_c: number
  assumptions: string[]
  window_hours: number
  series: SeriesPoint[]
  t_onset_hours: number | null
  t_blockage_hours: number | null
  critical_ambient_c: number | null
  critical_note: string | null
  sweep: SweepPoint[]
  verdict: Verdict
}

// Material tables for the UI (the backend holds the full property set;
// colours and hatching live in visuals/materialStyles.ts)
export interface MaterialSpec {
  label: string
  k: number
}

export const PIPE_MATERIALS: Record<PipeMaterial, MaterialSpec> = {
  copper: { label: 'Copper', k: 400 },
  steel: { label: 'Steel', k: 50 },
  pvc: { label: 'PVC', k: 0.19 },
  pex: { label: 'PEX', k: 0.4 },
}

export const INSULATION_TYPES: Record<InsulationType, MaterialSpec> = {
  fiberglass: { label: 'Fiberglass', k: 0.035 },
  foam_wrap: { label: 'Foam wrap', k: 0.038 },
  mineral_wool: { label: 'Mineral wool', k: 0.037 },
  none: { label: 'No insulation', k: 0 },
}

/** Location is fixed in this version (backend: FIXED_LOCATION) */
export const FIXED_LOCATION: Location = 'outdoors'

export interface LocationSpec {
  label: string
  summary: string
}

/** Fixed surroundings per location (backend: analysis/environment.py) */
export const LOCATIONS: Record<Location, LocationSpec> = {
  underground: {
    label: 'Underground',
    summary: '0.45 m deep in moist loam starting at 5°C; the cold soaks down from the surface over time.',
  },
  indoors: {
    label: 'Indoors',
    summary: 'In a wall or unheated space of a building heated to 20°C; the space sits 30% of the way from outside to indoor temperature.',
  },
  outdoors: {
    label: 'Outdoors',
    summary: 'Exposed to outside air with a constant 3 m/s wind.',
  },
}

export const DEFAULT_PARAMS: PipeParams = {
  pipe_material: 'copper',
  inner_diameter_mm: 15,
  wall_thickness_mm: 1,
  insulation: 'none',
  insulation_thickness_mm: 13,
  location: FIXED_LOCATION,
  outside_temp_c: -10,
  cold_snap_hours: 8,
  initial_water_temp_c: 10,
  drip_flow_lpm: 0,
}

export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '—'
  if (hours < 1) return `${Math.round(hours * 60)} min`
  return `${hours.toFixed(1)} h`
}

export function formatTemperature(celsius: number | null | undefined): string {
  if (celsius === null || celsius === undefined) return '—'
  return `${celsius.toFixed(1)}°C`
}
