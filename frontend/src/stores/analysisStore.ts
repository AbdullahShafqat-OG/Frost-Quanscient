/**
 * Bridge store: lets the as-branch components (PipeViewer3D, PipeSideSection,
 * MaterialLegend, VerdictCard, ResultsChart) read pipe geometry, series data,
 * and full analysis results driven by the yo-branch App.vue simulation loop.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PipeParams, SeriesPoint, AnalysisResults } from '@/types'
import { DEFAULT_PARAMS } from '@/types'

export const useAnalysisStore = defineStore('analysis', () => {
  // Params in as-backend field names (what the 3D geometry composable reads)
  const params = ref<PipeParams>({ ...DEFAULT_PARAMS })

  // Full raw AnalysisResults from the backend (drives VerdictCard + ResultsChart)
  const results = ref<AnalysisResults | null>(null)

  // Series is derived from results so it stays in sync automatically
  const series = computed<SeriesPoint[]>(() => results.value?.series ?? [])

  const hasResults = computed(() => results.value !== null)

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

  /** Store the full raw backend response for VerdictCard / ResultsChart. */
  function setResults(r: AnalysisResults) {
    results.value = r
  }

  /**
   * Called by App.vue after each simulation run.
   */
  function updateFromResult(yoParams: YoParams, rawResults: AnalysisResults) {
    setParams(yoParams)
    setResults(rawResults)
  }

  return { params, results, series, hasResults, setParams, setResults, updateFromResult }
})
