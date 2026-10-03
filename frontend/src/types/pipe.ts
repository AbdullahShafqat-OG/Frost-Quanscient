import type { AnalysisResults } from '@/types'
export type PipeMaterial = 'copper' | 'steel' | 'pvc' | 'pex'
export type InsulationMaterial = 'fiberglass' | 'foam_wrap' | 'mineral_wool' | 'none'
export interface PipeParams {
  ambient_c: number; water_c: number; diameter_mm: number
  wall_mm: number; material: PipeMaterial; insulation_material: InsulationMaterial
  insulation_mm: number; flow_l_min: number; duration_h: number
}
export interface PipeResult {
  /** Form values the run was started with */
  parameters: PipeParams
  engine: 'estimate' | 'allsolve'
  risk: 'freezing' | 'near' | 'above'
  /** Backend results, untranslated: every number shown comes from here */
  raw: AnalysisResults
}
