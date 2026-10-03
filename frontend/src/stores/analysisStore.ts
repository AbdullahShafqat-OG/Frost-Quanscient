/**
 * Bridge store: lets the as-branch 3D components (PipeViewer3D, PipeSideSection,
 * MaterialLegend) read pipe geometry and ice-fraction data that is driven by the
 * yo-branch App.vue simulation loop.
 *
 * App.vue calls updateFromResult() after each successful run.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PipeParams, SeriesPoint } from '@/types'
import { DEFAULT_PARAMS } from '@/types'

export const useAnalysisStore = defineStore('analysis', () => {
  // Params in as-backend field names (what the 3D geometry composable reads)
  const params = ref<PipeParams>({ ...DEFAULT_PARAMS })

  // Series from the last run (provides ice_fraction for the 3D viewer)
  const series = ref<SeriesPoint[]>([])
  const hasResults = ref(false)

  type YoParams = {
    diameter_mm: number; wall_mm: number; material: string
    insulation_material: string; insulation_mm: number
    duration_h: number; ambient_c: number; water_c: number
    flow_l_min: number
  }

  /** Translate yo field names → as field names and update store params. */
  function setParams(yoParams: YoParams) {
    params.value = {
      pipe_material: yoParams.material as PipeParams['pipe_material'],
      inner_diameter_mm: yoParams.diameter_mm,
      wall_thickness_mm: yoParams.wall_mm,
      insulation: yoParams.insulation_material as PipeParams['insulation'],
      insulation_thickness_mm: yoParams.insulation_mm || 25,
      location: 'outdoors',
      outside_temp_c: yoParams.ambient_c,
      cold_snap_hours: yoParams.duration_h,
      initial_water_temp_c: yoParams.water_c,
      drip_flow_lpm: yoParams.flow_l_min,
    }
  }

  /**
   * Called by App.vue after each simulation run with the yo PipeParams
   * (front-end field names) and the raw series from the backend.
   */
  function updateFromResult(yoParams: YoParams, rawSeries: SeriesPoint[]) {
    setParams(yoParams)
    series.value = rawSeries
    hasResults.value = true
  }

  /** Drop the last run's series so the 3D viewer shows no ice it hasn't computed. */
  function clearResults() {
    series.value = []
    hasResults.value = false
  }

  return { params, series, hasResults, setParams, updateFromResult, clearResults }
})
