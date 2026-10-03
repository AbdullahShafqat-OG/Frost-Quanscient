/**
 * Pinia store for freeze-risk analysis state
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PipeParams, AnalysisResults, SeriesPoint } from '@/types'
import { DEFAULT_PARAMS } from '@/types'
import { analysisApi } from '@/api/analysis'

export const useAnalysisStore = defineStore('analysis', () => {
  // ============================================================================
  // STATE
  // ============================================================================

  const params = ref<PipeParams>({ ...DEFAULT_PARAMS })

  const analysisId = ref<string | null>(null)
  const status = ref<'idle' | 'pending' | 'running' | 'completed' | 'failed'>('idle')
  const progress = ref(0)
  const message = ref('')
  const results = ref<AnalysisResults | null>(null)
  const error = ref<string | null>(null)

  // Demo mode toggle (false = full simulation on Allsolve)
  const useDemoMode = ref(false)

  let pollTimer: ReturnType<typeof setTimeout> | null = null

  // ============================================================================
  // GETTERS
  // ============================================================================

  const isRunning = computed(() => status.value === 'running' || status.value === 'pending')
  const hasResults = computed(() => results.value !== null)
  const series = computed<SeriesPoint[]>(() => results.value?.series ?? [])

  // ============================================================================
  // ACTIONS
  // ============================================================================

  function setParam<K extends keyof PipeParams>(key: K, value: PipeParams[K]) {
    params.value[key] = value
  }

  function setDemoMode(demo: boolean) {
    useDemoMode.value = demo
  }

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  async function startAnalysis() {
    stopPolling()
    status.value = 'pending'
    progress.value = 0
    error.value = null
    results.value = null

    try {
      if (useDemoMode.value) {
        message.value = 'Computing local estimate...'
        status.value = 'running'
        const demoResults = await analysisApi.runDemo(params.value)
        results.value = demoResults
        analysisId.value = demoResults.analysis_id
        progress.value = 100
        status.value = 'completed'
        message.value = 'Demo estimate complete'
      } else {
        message.value = 'Starting Allsolve analysis...'
        const response = await analysisApi.start(params.value)
        analysisId.value = response.analysis_id
        status.value = 'running'
        message.value = response.message
        pollStatus()
      }
    } catch (e) {
      status.value = 'failed'
      error.value = e instanceof Error ? e.message : 'Unknown error'
      message.value = error.value
    }
  }

  async function pollStatus() {
    if (!analysisId.value) return
    const id = analysisId.value

    try {
      const statusResponse = await analysisApi.getStatus(id)
      if (id !== analysisId.value || !isRunning.value) return // reset/aborted meanwhile

      progress.value = statusResponse.progress
      message.value = statusResponse.message ?? ''

      if (statusResponse.status === 'completed') {
        results.value = await analysisApi.getResults(id)
        status.value = 'completed'
        message.value = 'Analysis complete'
      } else if (statusResponse.status === 'failed' || statusResponse.status === 'aborted') {
        status.value = 'failed'
        error.value = statusResponse.message ?? 'Analysis failed'
        message.value = error.value
      } else {
        pollTimer = setTimeout(pollStatus, 1000)
      }
    } catch (e) {
      status.value = 'failed'
      error.value = e instanceof Error ? e.message : 'Failed to get status'
      message.value = error.value
    }
  }

  async function abortAnalysis() {
    if (!isRunning.value) return
    stopPolling()

    if (!analysisId.value || useDemoMode.value) {
      status.value = 'idle'
      message.value = 'Aborted'
      progress.value = 0
      return
    }

    try {
      message.value = 'Aborting analysis...'
      await analysisApi.abort(analysisId.value)
      message.value = 'Analysis aborted'
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to abort'
      message.value = error.value
    }
    // Idle either way so the user can retry
    status.value = 'idle'
    progress.value = 0
  }

  function reset() {
    stopPolling()
    status.value = 'idle'
    progress.value = 0
    message.value = ''
    results.value = null
    error.value = null
    analysisId.value = null
  }

  function resetParams() {
    params.value = { ...DEFAULT_PARAMS }
  }

  return {
    // State
    params,
    analysisId,
    status,
    progress,
    message,
    results,
    error,
    useDemoMode,

    // Getters
    isRunning,
    hasResults,
    series,

    // Actions
    setParam,
    setDemoMode,
    startAnalysis,
    abortAnalysis,
    reset,
    resetParams,
  }
})
