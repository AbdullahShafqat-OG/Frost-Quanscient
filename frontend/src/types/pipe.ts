export type PipeMaterial = 'copper' | 'steel' | 'pvc' | 'pex'
export type InsulationMaterial = 'fiberglass' | 'foam_wrap' | 'mineral_wool' | 'none'
export interface PipeParams {
  ambient_c: number; water_c: number; length_m: number; diameter_mm: number
  wall_mm: number; material: PipeMaterial; insulation_material: InsulationMaterial
  insulation_mm: number; flow_l_min: number; duration_h: number
}
export interface PipeResult {
  parameters: PipeParams; engine: 'estimate' | 'allsolve'; project_url?: string
  model_version: string
  risk: 'freezing' | 'near' | 'above'
  freeze_hours: number | null
  end_hours: number; minimum_c: number; minimum_wall_c: number; minimum_interface_c: number; critical_flow_l_min: number
  flow_threshold_note: string; assumptions: string[]
  environment: {
    wind_m_s: number; external_h_w_m2k: number
    internal_h_w_m2k: number; reynolds: number; pipe_k_w_mk: number
    insulation_k_w_mk: number | null
  }
  residence_minutes: number | null
  history: { hours: number; temperature_c: number; interface_temperature_c: number }[]
  profile: { distance_m: number; temperature_c: number }[]
}

