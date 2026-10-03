<script setup lang="ts">
import { computed, defineAsyncComponent, onUnmounted, reactive, ref, watch, watchEffect } from 'vue'
import ResultsChart from '@/components/ResultsChart.vue'
import SliderInput from '@/components/SliderInput.vue'
import PipeSideSection from '@/components/PipeSideSection.vue'
import GeometryViewer from '@/components/GeometryViewer.vue'
import type { PipeParams, PipeResult } from '@/types/pipe'
import { formatHours, formatTemperature } from '@/types'
import { runEstimate, startJob, pollJob } from '@/api/analysis'
import { useAnalysisStore } from '@/stores/analysisStore'

const PipeViewer3D = defineAsyncComponent(() => import('@/components/PipeViewer3D.vue'))
const analysisStore = useAnalysisStore()

const defaults: PipeParams = {
  ambient_c: -20, water_c: 10, diameter_mm: 25,
  wall_mm: 2, material: 'copper', insulation_mm: 0, insulation_material: 'none',
  flow_l_min: 0, duration_h: 12,
}
const params = reactive<PipeParams>({ ...defaults })
const engine = ref<'estimate' | 'allsolve'>('estimate')
const result = ref<PipeResult | null>(null)
const busy = ref(false)
const error = ref('')
const message = ref('')
const progress = ref(0)
const comparison = ref<PipeResult[]>([])
const sidebarOpen = ref(false)
const form = ref<HTMLFormElement | null>(null)
let disposed = false
let pollTimer: ReturnType<typeof setTimeout> | undefined
let requestController: AbortController | undefined
const stale = computed(() => result.value !== null &&
  Object.keys(defaults).some(key => params[key as keyof PipeParams] !== result.value?.parameters[key as keyof PipeParams]))
const RISK_TITLE = { freezing: 'Freezes', near: 'At risk', above: 'Safe' } as const
const title = computed(() => result.value ? RISK_TITLE[result.value.risk] : '')
watch(() => params.insulation_material, material => {
  if (material === 'none') params.insulation_mm = 0
  else if (params.insulation_mm === 0) params.insulation_mm = 20
})

// Keep the 3D model in sync with form params without needing a run
watchEffect(() => {
  analysisStore.setParams({ ...params })
})
// Ice in the 3D model belongs to the last run's inputs; drop it once they change
watch(stale, isStale => {
  if (isStale) analysisStore.clearResults()
})
function applyPreset(preset: 'exposed' | 'insulated' | 'flowing') {
  Object.assign(params, defaults)
  if (preset === 'insulated') { params.insulation_material = 'foam_wrap'; params.insulation_mm = 30 }
  if (preset === 'flowing') params.flow_l_min = 1
  error.value = ''
}
async function poll(id: string, snapshot: PipeParams) {
  try {
    const job = await pollJob(id, snapshot, requestController?.signal)
    if (disposed) return
    message.value = job.message
    progress.value = job.progress
    if (job.status === 'completed') {
      result.value = job.result!
      analysisStore.updateFromResult(snapshot, job.result!.raw.series)
      busy.value = false
    } else if (job.status === 'failed') {
      throw new Error(job.message)
    } else {
      pollTimer = setTimeout(() => poll(id, snapshot), 1500)
    }
  } catch (e) {
    if (!disposed) {
      error.value = e instanceof Error ? e.message : 'Unable to retrieve the simulation.'
      busy.value = false
    }
  }
}
async function run() {
  if (busy.value || !form.value?.reportValidity()) return
  busy.value = true
  error.value = ''
  result.value = null
  analysisStore.clearResults()
  progress.value = 0
  message.value = engine.value === 'estimate' ? 'Calculating pipe cooling…' : 'Connecting to Allsolve…'
  requestController = new AbortController()
  const snapshot = { ...params }
  try {
    if (engine.value === 'estimate') {
      const response = await runEstimate(snapshot, requestController.signal)
      if (!disposed) {
        result.value = response
        analysisStore.updateFromResult(snapshot, response.raw.series)
        busy.value = false
      }
    } else {
      const id = await startJob(snapshot, requestController.signal)
      if (!disposed) await poll(id, snapshot)
    }
  } catch (e) {
    if (!disposed) {
      error.value = e instanceof Error ? e.message : 'Unable to run simulation.'
      busy.value = false
    }
  }
}
function saveScenario() {
  if (result.value && !stale.value && comparison.value.length < 4) {
    comparison.value.push(JSON.parse(JSON.stringify(result.value)))
  }
}
function exportResult() {
  if (!result.value) return
  const r = result.value
  const metadata = Object.entries(r.raw.parameters).map(([key, value]) => '# ' + key + ',' + value).join('\n')
  const csv = '# Frost pipe simulation\n# engine,' + r.engine + '\n' + metadata +
    '\ntime_hours,t_min_water_c,t_avg_water_c,t_max_water_c,ice_fraction\n' +
    r.raw.series.map(p => [p.time_hours, p.t_min_water_c, p.t_avg_water_c, p.t_max_water_c, p.ice_fraction].join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'frost-pipe-results.csv'
  link.click()
  URL.revokeObjectURL(url)
}
onUnmounted(() => {
  disposed = true
  if (pollTimer) clearTimeout(pollTimer)
  requestController?.abort()
})
</script>

<template>
  <div class="frost-app">
    <header class="topbar">
      <div class="brand"><span class="brand-symbol" aria-hidden="true">✳</span><span>frost<span class="brand-dot">.</span></span></div>
      <div class="qs-brand" aria-label="Powered by Quanscient Allsolve">
        <svg class="qs-logo" viewBox="0 0 1040 201" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path fill="currentColor" d="m228.09,143.88l-16.7-16.66-.07-.07-7.88-7.86-4.08-4.08-.46-.46h0s-20.51-20.53-20.51-20.53c-.53-.59-1.61-.42-2.06.34l-6.96,21.25-.06.18-.11.34c-.26.44-.24.95.07,1.29l5.91,6.61c.53.59,1.59.41,2.06-.32l.04-.07.04-.09,1.91-3.93c.44-.79,1.55-.99,2.09-.39l.23.21,6.36,6.37.22.22,11.98,12,.23.23,6.57,6.58c.7.7,1.65,1.09,2.64,1.09h17.63c1.18,0,1.77-1.43.94-2.26Zm-56.68-96.9c-28.33-.36-51.36,22.68-50.99,51,.36,27.7,22.85,49.8,50.55,49.69,7.99-.03,15.54-1.93,22.24-5.27.82-.41,1-1.49.36-2.14l-10.42-10.42c-.5-.5-1.23-.67-1.9-.45-3.46,1.13-7.17,1.72-11.02,1.66-17.93-.28-33.05-15.53-33.19-33.46-.14-18.87,15.22-34.18,34.11-33.98,18.13.2,33.33,15.57,33.34,33.69,0,3.9-.66,7.64-1.87,11.12-.24.68-.07,1.43.44,1.94l10.35,10.35c.64.64,1.71.48,2.12-.32,3.49-6.76,5.49-14.4,5.58-22.51.3-27.39-22.3-50.56-49.69-50.9Zm720.1,31h-19.4c-1.4,0-2.41-1.06-2.41-2.23v-9.64c0-1.17,1.01-2.23,2.41-2.23h55.42c1.39,0,2.41,1.06,2.41,2.23v9.64c0,1.18-1.02,2.23-2.41,2.23h-19.4v65.93c0,1.18-1.14,2.23-2.41,2.23h-11.79c-1.27,0-2.41-1.06-2.41-2.23v-65.93Zm-109.95-13.16c0-1.17,1.14-2.11,2.41-2.11h3.17l52.76,51.94h.12v-48.54c0-1.17,1.02-2.23,2.41-2.23h11.67c1.27,0,2.41,1.06,2.41,2.23v79.09c0,1.18-1.14,2.12-2.41,2.12h-3.04l-53.01-53.95h-.13v50.53c0,1.18-1.01,2.23-2.41,2.23h-11.54c-1.27,0-2.41-1.06-2.41-2.23v-79.09Zm-74.57,1.29c0-1.17,1.01-2.23,2.41-2.23h51.62c1.39,0,2.41,1.06,2.41,2.23v9.64c0,1.18-1.02,2.23-2.41,2.23h-37.54v19.27h31.32c1.27,0,2.41,1.06,2.41,2.23v9.75c0,1.29-1.14,2.23-2.41,2.23h-31.32v20.57h37.54c1.39,0,2.41,1.06,2.41,2.23v9.64c0,1.18-1.02,2.23-2.41,2.23h-51.62c-1.4,0-2.41-1.06-2.41-2.23v-77.8Zm-39.69,0c0-1.17,1.14-2.23,2.41-2.23h11.79c1.27,0,2.41,1.06,2.41,2.23v77.8c0,1.18-1.14,2.23-2.41,2.23h-11.79c-1.27,0-2.41-1.06-2.41-2.23v-77.8Zm-47.43-3.41c12.81,0,22.06,3.76,30.69,10.93,1.14.94,1.14,2.35.13,3.29l-7.74,7.4c-.89.94-2.15.94-3.17,0-5.33-4.35-12.43-6.93-19.53-6.93-16.23,0-28.28,12.57-28.28,27.39s12.17,27.15,28.41,27.15c7.61,0,14.08-2.7,19.4-6.7,1.02-.82,2.41-.7,3.17,0l7.86,7.52c1.01.82.76,2.35-.13,3.17-8.62,7.76-19.53,11.4-30.82,11.4-25.37,0-45.78-18.69-45.78-42.19s20.42-42.43,45.78-42.43Zm-113.25,71.92l4.57-7.29c1.01-1.64,3.17-1.64,4.31-.82.63.35,10.91,7.29,19.15,7.29,6.59,0,11.54-4,11.54-9.05,0-5.99-5.45-10.11-16.11-14.1-11.92-4.47-23.84-11.52-23.84-25.38,0-10.46,8.37-22.56,28.54-22.56,12.94,0,22.83,6.11,25.36,7.87,1.27.7,1.65,2.7.76,3.88l-4.82,6.7c-1.01,1.41-2.92,2.35-4.44,1.41-1.02-.59-10.65-6.47-17.63-6.47s-11.16,4.47-11.16,8.23c0,5.52,4.7,9.28,14.97,13.16,12.3,4.58,26.51,11.4,26.51,26.56,0,12.11-11.29,23.27-29.17,23.27-15.98,0-25.36-6.93-27.9-9.17-1.14-1.06-1.78-1.65-.64-3.53Zm-92.83-69.81c0-1.17,1.14-2.11,2.41-2.11h3.17l52.76,51.94h.12v-48.54c0-1.17,1.02-2.23,2.41-2.23h11.67c1.27,0,2.41,1.06,2.41,2.23v79.09c0,1.18-1.14,2.12-2.41,2.12h-3.04l-53.01-53.95h-.13v50.53c0,1.18-1.01,2.23-2.41,2.23h-11.54c-1.27,0-2.41-1.06-2.41-2.23v-79.09Zm-40.2,53.24l-12.68-25.85h-.38l-12.43,25.85h25.49Zm-54.79,25.03l39.44-79.09c.38-.7,1.01-1.29,2.16-1.29h1.27c1.27,0,1.77.59,2.15,1.29l39.06,79.09c.76,1.53-.25,3.05-2.16,3.05h-11.03c-1.9,0-2.79-.7-3.68-2.35l-6.22-12.69h-37.92l-6.21,12.69c-.51,1.17-1.65,2.35-3.68,2.35h-11.03c-1.9,0-2.92-1.53-2.16-3.05Zm-79.01-76.98c0-1.17,1.14-2.23,2.41-2.23h12.05c1.4,0,2.41,1.06,2.41,2.23v48.07c0,9.99,7.35,17.86,18.39,17.86s18.52-7.87,18.52-17.75v-48.19c0-1.17,1.01-2.23,2.41-2.23h12.05c1.27,0,2.41,1.06,2.41,2.23v48.89c0,17.86-15.34,32.32-35.38,32.32s-35.26-14.46-35.26-32.32v-48.89Z"/>
        </svg>
        <span class="qs-allsolve">Allsolve</span>
      </div>
    </header>
    <main class="workspace">
      <button class="config-fab" @click="sidebarOpen = !sidebarOpen" :aria-expanded="sidebarOpen" aria-label="Open configuration panel">
        <svg width="15" height="12" viewBox="0 0 15 12" fill="none"><path d="M1 1h13M1 6h9M1 11h13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <span>Configure</span>
      </button>
      <div class="sidebar-backdrop" :class="{visible: sidebarOpen}" @click="sidebarOpen = false"></div>
      <div class="tri-layout">
        <aside class="setup-panel" :class="{open: sidebarOpen}">
          <button class="sidebar-close" @click="sidebarOpen = false" aria-label="Close panel">&times;</button>
          <form ref="form" @submit.prevent="run">
            <div class="panel-heading"><h2>Configure your pipe</h2><span class="step-number">01</span></div>
            <fieldset :disabled="busy">
              <div class="presets" aria-label="Example scenarios">
                <button type="button" @click="applyPreset('exposed')">Exposed</button>
                <button type="button" @click="applyPreset('insulated')">Insulated</button>
                <button type="button" @click="applyPreset('flowing')">Flowing</button>
              </div>
              <section class="input-section">
                <h3><span class="section-icon">↔</span> Pipe</h3>
                <label>Pipe material<select v-model="params.material"><option value="copper">Copper</option><option value="steel">Steel</option><option value="pvc">PVC</option><option value="pex">PEX</option></select></label>
                <SliderInput v-model="params.wall_mm" label="Pipe wall thickness" :min="0.5" :max="10" :step="0.5" unit="mm" />
                <SliderInput v-model="params.diameter_mm" label="Inner diameter" :min="6" :max="100" :step="0.5" unit="mm" />
              </section>
              <section class="input-section">
                <h3><span class="section-icon">◎</span> Insulation</h3>
                <label>Pipe insulation material<select v-model="params.insulation_material"><option value="fiberglass">Fiber glass</option><option value="foam_wrap">Foam wrap</option><option value="mineral_wool">Mineral wool</option><option value="none">No insulation</option></select></label>
                <SliderInput v-if="params.insulation_material !== 'none'" v-model="params.insulation_mm" label="Insulation thickness" :min="5" :max="50" :step="1" unit="mm" />
                <p class="input-hint">{{ params.insulation_material === 'none' ? 'Bare pipe. Insulation thickness is 0 mm.' : 'Dry, intact material. Representative conductivity is assigned automatically; actual product and moisture can change performance.' }}</p>
              </section>
              <section class="input-section">
                <h3><span class="section-icon">❄</span> External conditions</h3>
                <p class="exposure-note">Continuously exposed to outside air · <b>3 m/s wind</b></p>
                <div class="input-grid">
                  <label>Outside temperature<div class="number-input"><input v-model.number="params.ambient_c" type="number" min="-40" max="-1" step="1" required /><span>°C</span></div></label>
                  <label>Cold snap duration<div class="number-input"><input v-model.number="params.duration_h" type="number" min="1" max="48" step="0.5" required /><span>hr</span></div></label>
                </div>
                <p class="input-hint">Outside temperature and wind stay constant. Convection and radiation are estimated automatically.</p>
              </section>
              <section class="input-section">
                <h3><span class="section-icon">≈</span> Water</h3>
                <SliderInput v-model="params.water_c" label="Initial water temperature" :min="1" :max="25" :step="0.1" unit="°C" />
                <SliderInput v-model="params.flow_l_min" label="Drip flow" :min="0" :max="1" :step="0.001" unit="L/min" />
                <p class="input-hint">0 L/min means stagnant water. A constant drip supplies water at the initial temperature through a 3 m pipe run. 0.01 L/min = 0.6 L/hr.</p>
              </section>
              <section class="engine-section">
                <label>Calculation engine<select v-model="engine"><option value="estimate">Quick estimate</option><option value="allsolve">Quanscient Allsolve · cloud FEM</option></select></label>
                <p class="input-hint">{{ engine === 'estimate' ? 'Local lumped estimate. No cloud credentials needed.' : 'Runs the coupled pipe model in Allsolve. Uses your configured account and cloud compute.' }}</p>
              </section>
            </fieldset>
            <button class="run-button" type="submit" :disabled="busy"><span>{{ busy ? 'Simulation running…' : 'Run simulation' }}</span><span aria-hidden="true">{{ busy ? '◌' : '→' }}</span></button>
            <div v-if="busy" class="progress-area" role="status"><progress :value="progress" max="100"></progress><span>{{ message }}</span></div>
            <p v-if="error" class="error-message" role="alert">{{ error }}</p>
          </form>
        </aside>

        <!-- Column 2: 3D models stacked -->
        <div class="model-column">
          <div class="model-col-head"><p class="eyebrow">PIPE MODEL</p><h3>Cross-section &amp; geometry</h3></div>
          <div class="pipe-3d-wrap"><Suspense><PipeViewer3D /></Suspense></div>
          <div class="pipe-side-stack">
            <!-- Front cross-section includes the material legend -->
            <div class="pipe-front-wrap"><GeometryViewer /></div>
            <PipeSideSection />
          </div>
        </div>

        <div class="results-panel">
          <div v-if="stale" class="stale-notice" role="status">Parameters changed. Run again to update the results below.</div>
          <template v-if="result">
            <section class="risk-card" :class="'risk-' + result.risk">
              <div class="risk-icon" aria-hidden="true">{{ result.risk === 'freezing' ? '❄' : result.risk === 'near' ? '!' : '✓' }}</div>
              <div class="risk-copy"><p class="eyebrow">SIMULATION ASSESSMENT</p><h2>{{ title }}</h2><p>{{ result.raw.verdict.headline }}</p></div>
              <span class="engine-badge">{{ result.engine === 'allsolve' ? 'ALLSOLVE FEM' : 'QUICK ESTIMATE' }}</span>
            </section>
            <div class="metrics-grid">
              <div class="metric"><p>Critical outside temperature</p><strong>{{ formatTemperature(result.raw.critical_ambient_c) }}</strong><span>{{ result.raw.critical_note ?? 'Blocks within the ' + result.raw.parameters.cold_snap_hours + ' h cold snap below this' }}</span></div>
              <div class="metric"><p>First ice</p><strong>{{ formatHours(result.raw.t_onset_hours) }}</strong><span>At {{ result.raw.parameters.outside_temp_c }} °C outside</span></div>
              <div class="metric"><p>Blocked</p><strong>{{ formatHours(result.raw.t_blockage_hours) }}</strong><span>90% of the water is ice</span></div>
            </div>

            <section class="assumptions-card">
              <div class="card-heading"><div><p class="eyebrow">CONDITIONS USED IN THIS RUN</p><h2>Verdict details &amp; advice</h2></div></div>
              <div class="derived-values"><span>External heat transfer <b>{{ result.raw.h_out.toFixed(1) }} W/m²·K</b></span><span>Surroundings <b>{{ formatTemperature(result.raw.surroundings_c) }}</b></span></div>
              <ul class="verdict-list"><li v-for="line in result.raw.verdict.details" :key="line">{{ line }}</li></ul>
              <div v-if="result.raw.verdict.actions.length" class="verdict-actions"><h3>What to do</h3><ul><li v-for="action in result.raw.verdict.actions" :key="action">{{ action }}</li></ul></div>
              <details><summary>Model assumptions and limits</summary><ul><li v-for="assumption in [...result.raw.assumptions, ...result.raw.verdict.caveats]" :key="assumption">{{ assumption }}</li></ul></details>
            </section>

            <section class="chart-card">
              <div class="card-heading"><div><p class="eyebrow">THERMAL RESPONSE</p><h2>How fast does the water cool?</h2></div><button class="text-button" type="button" @click="exportResult">Export CSV ↗</button></div>
              <ResultsChart :results="result.raw" />
              <div class="result-actions"><button type="button" class="outline-button" :disabled="stale || comparison.length >= 4 || busy" @click="saveScenario">+ Save scenario for comparison</button></div>
            </section>

            <section v-if="comparison.length" class="comparison-card">
              <div class="card-heading"><div><p class="eyebrow">EXPLORE THE TRADEOFFS</p><h2>Scenario comparison</h2></div><button type="button" class="text-button" @click="comparison = []">Clear</button></div>
              <div class="table-scroll"><table><thead><tr><th>Scenario</th><th>Ambient</th><th>Insulation</th><th>Flow</th><th>Exposure</th><th>First ice</th><th>Blocked</th><th></th></tr></thead><tbody><tr v-for="(scenario, index) in comparison" :key="index"><td>{{ index + 1 }} · {{ scenario.engine === 'estimate' ? 'Estimate' : 'Allsolve' }}</td><td>{{ scenario.parameters.ambient_c }} °C</td><td>{{ scenario.parameters.insulation_mm }} mm</td><td>{{ scenario.parameters.flow_l_min }} L/min</td><td>{{ scenario.parameters.duration_h }} hr</td><td>{{ formatHours(scenario.raw.t_onset_hours) }}</td><td>{{ formatHours(scenario.raw.t_blockage_hours) }}</td><td><button type="button" class="text-button" :aria-label="'Remove scenario ' + (index + 1)" @click="comparison.splice(index, 1)">×</button></td></tr></tbody></table></div>
            </section>
          </template>
          <section v-else class="empty-card"><div class="empty-symbol">◎</div><h2>Understand your cold-weather exposure</h2><p>Choose a scenario or enter your pipe parameters, then run the model to see when ice forms and when the pipe blocks.</p></section>
        </div>
      </div>
      <section class="physics-note">
        <div><p class="eyebrow">ABOUT THIS MODEL</p><h2>Heat escapes. Flow replenishes it.</h2></div>
        <div><h3>What is calculated</h3><p>An exposed pipe in constant outside air at 3 m/s. The water cools through the pipe wall, insulation, convection and radiation, then freezes from the wall inward. A drip supplies fresh water at the initial temperature.</p></div>
        <div><h3>First ice and blockage</h3><p>First ice is when the coldest water reaches 0 °C. The pipe counts as blocked once 90% of the water is ice. Bursting is not modelled.</p></div>
        <div><h3>Critical outside temperature</h3><p>The outside temperature at which the pipe just blocks by the end of the cold snap, found by repeating the run across a range of outside temperatures.</p></div>
      </section>
      <footer class="page-footer"><span>FROST · Water infrastructure resilience</span><span>Vue 3 + Quanscient Allsolve</span></footer>
    </main>
  </div>
</template>

<style>
/* ── Design tokens ───────────────────────────────────────────────────────────── */
.frost-app {
  --ink: #0e1c28;
  --ink-2: #1b3146;
  --muted: #5c6e7c;
  --subtle: #8fa2b0;
  --line: rgba(14, 28, 40, 0.07);
  --teal: #0a9688;
  --teal-dk: #077a6d;
  --glass: rgba(255,255,255,0.74);
  --glass-hi: rgba(255,255,255,0.88);
  --glass-bd: rgba(255,255,255,0.58);
  --shadow-sm: 0 1px 3px rgba(14,28,40,0.05), 0 0 0 1px rgba(14,28,40,0.04);
  --shadow-md: 0 4px 24px rgba(14,28,40,0.08), 0 1px 6px rgba(14,28,40,0.04), inset 0 1px 0 rgba(255,255,255,0.82);
  --shadow-lg: 0 8px 40px rgba(14,28,40,0.1), 0 2px 10px rgba(14,28,40,0.05), inset 0 1px 0 rgba(255,255,255,0.9);
  --r: 16px;
  --r-sm: 10px;
  --r-xs: 7px;
  font-size: 16px;
  color: var(--ink);
  background: #eaecf2;
  min-height: 100dvh;
  font-family: 'Outfit', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* ── Topbar ──────────────────────────────────────────────────────────────────── */
.topbar {
  background: rgba(11,22,35,0.90);
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  color: #fff;
  min-height: 66px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 max(28px, calc((100vw - 1456px) / 2));
  gap: 20px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.brand { display:flex; align-items:center; gap:10px; font-size:26px; font-weight:700; letter-spacing:-1px; }
.brand-symbol { color:#4ed9cf; font-size:28px; font-weight:400; }
.brand-dot { color:#4ed9cf; }
.qs-brand {
  display: flex; align-items: center; gap: 9px;
  color: rgba(255,255,255,0.55);
  padding-left: 20px;
  border-left: 1px solid rgba(255,255,255,0.1);
}
.qs-logo { height: 18px; width: auto; color: rgba(255,255,255,0.7); flex-shrink: 0; }
.qs-allsolve {
  font-size: 13px; font-weight: 500; letter-spacing: .2px;
  color: rgba(255,255,255,0.55); white-space: nowrap;
}
.status-dot {
  width:6px; height:6px; border-radius:50%; background:#4ed9cf;
  box-shadow: 0 0 8px rgba(78,217,207,0.55);
  animation: blink 2.6s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.55;transform:scale(.8)} }

/* ── Workspace ───────────────────────────────────────────────────────────────── */
.workspace { max-width:1456px; padding:28px 28px 64px; margin:0 auto; }
.eyebrow { font-size:11px; letter-spacing:1.5px; font-weight:600; color:var(--muted); margin:0 0 8px; text-transform:uppercase; }

/* ── Three-column layout ─────────────────────────────────────────────────────── */
.config-fab {
  display: none; /* visible only on tablet/mobile */
  align-items: center; gap: 8px;
  background: var(--teal); border: none; border-radius: var(--r-sm);
  color: #fff; font-family: inherit; font-size: 14px; font-weight: 600;
  padding: 10px 16px; cursor: pointer;
  box-shadow: 0 2px 12px rgba(10,150,136,0.28);
  margin-bottom: 14px; transition: background .15s, transform .14s;
}
.config-fab:hover { background: var(--teal-dk); transform: translateY(-1px); }
.config-fab:active { transform: translateY(0); }

.sidebar-backdrop {
  display: none;
  position: fixed; inset: 0; z-index: 199;
  background: rgba(14,28,40,0.38);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
}
.sidebar-backdrop.visible { display: block; }

.sidebar-close {
  display: none; /* shown on tablet/mobile */
  margin-left: auto; background: none; border: 0;
  font-size: 20px; color: var(--muted); cursor: pointer; padding: 4px 8px;
  line-height: 1; border-radius: var(--r-xs); transition: color .13s;
}
.sidebar-close:hover { color: var(--ink); }

.tri-layout { display: grid; grid-template-columns: 280px 420px minmax(0,1fr); gap: 18px; align-items: start; }

/* Column 2 – 3D model and 2D sections (taller than the viewport, so not sticky) */
.model-column {
  display: flex; flex-direction: column; gap: 12px;
}
.model-col-head { margin-bottom: 2px; }
.model-col-head h3 { font-size: 15px; font-weight: 600; margin: 4px 0 0; letter-spacing: -.2px; }
.pipe-3d-wrap {
  height: 420px; border-radius: 12px; overflow: hidden;
  background: rgba(14,28,40,0.02);
}
.pipe-side-stack { display: flex; flex-direction: column; gap: 10px; }
.pipe-front-wrap { height: 380px; }

/* ── Glass card base ─────────────────────────────────────────────────────────── */
.setup-panel,
.chart-card,
.comparison-card,
.empty-card,
.assumptions-card {
  background: var(--glass);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid var(--glass-bd);
  border-radius: var(--r);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

/* ── Setup panel ─────────────────────────────────────────────────────────────── */
.setup-panel { padding:20px; }
.panel-heading { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.panel-heading h2, .card-heading h2 { font-size:16px; font-weight:600; margin:0; letter-spacing:-.2px; }
.step-number { font-size:12px; color:var(--subtle); font-family:'Outfit',monospace; font-variant-numeric:tabular-nums; }
.setup-panel fieldset { padding:0; border:0; margin:0; min-width:0; }

/* Presets */
.presets { display:flex; padding:4px; gap:3px; background:rgba(14,28,40,0.05); border-radius:var(--r-sm); margin-bottom:8px; }
.presets button {
  flex:1; padding:8px 4px; border:0; border-radius:7px; color:var(--muted);
  font-size:13px; font-weight:500; background:transparent; cursor:pointer;
  font-family:inherit; transition:all .16s ease;
}
.presets button:hover { background:rgba(10,150,136,0.1); color:var(--teal); }
.presets button:active { background:rgba(10,150,136,0.18); }

/* Sections */
.input-section { padding:15px 0 13px; border-bottom:1px solid var(--line); }
.input-section h3 { font-size:13px; font-weight:600; display:flex; gap:7px; align-items:center; margin:0 0 11px; color:var(--ink-2); }
.section-icon { color:var(--teal); font-size:15px; width:17px; text-align:center; opacity:.9; }
.input-grid { display:grid; grid-template-columns:1fr 1fr; gap:9px; }
.input-grid + .input-grid { margin-top:9px; }
.setup-panel label { font-size:13px; color:var(--muted); display:block; line-height:1.5; font-weight:500; }
.input-hint { color:var(--subtle); font-size:13px; line-height:1.65; margin:7px 0 0; }
.exposure-note { padding:9px 11px; border-radius:var(--r-xs); background:rgba(10,150,136,0.06); color:#3a7570; font-size:13px; line-height:1.65; margin:0 0 10px; border:1px solid rgba(10,150,136,0.12); }

/* Number inputs */
.number-input {
  display:flex; align-items:center;
  background:rgba(255,255,255,0.68); border:1px solid rgba(14,28,40,0.1);
  border-radius:var(--r-xs); height:37px; margin-top:5px; overflow:hidden;
  transition:border-color .15s, box-shadow .15s;
}
.number-input:focus-within { border-color:var(--teal); box-shadow:0 0 0 3px rgba(10,150,136,0.11); background:rgba(255,255,255,0.9); }
.number-input input { font:500 15px 'Outfit',system-ui; width:100%; min-width:0; border:0; outline:none; background:transparent; padding:0 0 0 10px; color:var(--ink); }
.number-input span { font-size:13px; color:var(--subtle); white-space:nowrap; padding:0 9px 0 3px; }

/* Selects */
.setup-panel select {
  display:block; width:100%; padding:0 28px 0 9px; margin-top:5px;
  border:1px solid rgba(14,28,40,0.1); background:rgba(255,255,255,0.68);
  border-radius:var(--r-xs); font-size:14px; font-family:inherit; color:var(--ink);
  height:40px; appearance:none; cursor:pointer;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%235c6e7c' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:right 10px center;
  transition:border-color .15s, box-shadow .15s;
}
.setup-panel select:focus { outline:none; border-color:var(--teal); box-shadow:0 0 0 3px rgba(10,150,136,0.11); background-color:rgba(255,255,255,0.9); }
.input-section > label { margin-top:10px; }
.engine-section { padding:15px 0 17px; }

/* Run button */
.run-button {
  width:100%; background:linear-gradient(135deg,var(--teal) 0%,#088478 100%);
  color:#fff; border:0; border-radius:var(--r-sm); padding:13px 15px;
  display:flex; align-items:center; justify-content:space-between;
  font-size:15px; font-weight:600; font-family:inherit; cursor:pointer;
  box-shadow:0 2px 14px rgba(10,150,136,0.32), inset 0 1px 0 rgba(255,255,255,0.14);
  transition:all .17s ease; letter-spacing:.1px;
}
.run-button:hover { background:linear-gradient(135deg,#0ba898 0%,#098880 100%); transform:translateY(-1px); box-shadow:0 5px 20px rgba(10,150,136,0.38), inset 0 1px 0 rgba(255,255,255,0.14); }
.run-button:active { transform:translateY(0); }

button:disabled { opacity:.42; cursor:not-allowed; }
input:disabled, select:disabled { opacity:.55; }
button:focus-visible, select:focus-visible, a:focus-visible { outline:2px solid var(--teal); outline-offset:3px; border-radius:4px; }

/* Progress */
.progress-area { margin-top:13px; font-size:14px; color:var(--muted); }
.progress-area progress { display:block; width:100%; height:3px; accent-color:var(--teal); margin-bottom:7px; border:none; border-radius:99px; background:rgba(14,28,40,0.07); }
.error-message { background:rgba(175,55,35,0.07); color:#9e3420; border:1px solid rgba(175,55,35,0.13); padding:11px 13px; margin:12px 0 0; font-size:14px; line-height:1.6; border-radius:var(--r-xs); }

/* ── Results panel ───────────────────────────────────────────────────────────── */
.results-panel { display:flex; flex-direction:column; gap:15px; min-width:0; }
.stale-notice { font-size:14px; color:#7a6020; background:rgba(235,195,60,0.1); border:1px solid rgba(200,160,35,0.2); padding:11px 15px; border-radius:var(--r-sm); backdrop-filter:blur(8px); }

/* Risk card */
.risk-card {
  display:flex; align-items:center; gap:15px;
  background:rgba(215,242,237,0.78); border:1px solid rgba(10,150,136,0.17);
  border-radius:var(--r); padding:19px 22px; position:relative;
  backdrop-filter:blur(18px) saturate(160%); -webkit-backdrop-filter:blur(18px) saturate(160%);
  box-shadow:var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.7);
}
.risk-freezing { background:rgba(255,234,224,0.82); border-color:rgba(195,80,50,0.17); }
.risk-near    { background:rgba(255,247,218,0.82); border-color:rgba(195,150,28,0.2); }
.risk-icon {
  font-size:19px; width:40px; height:40px; display:flex; align-items:center; justify-content:center;
  background:rgba(255,255,255,0.82); color:var(--teal); border-radius:11px; flex-shrink:0;
  box-shadow:0 2px 8px rgba(14,28,40,0.09); border:1px solid rgba(255,255,255,0.9);
}
.risk-freezing .risk-icon { color:#c0502a; }
.risk-near .risk-icon    { color:#ae7a14; }
.risk-copy { min-width:0; }
.risk-copy .eyebrow { font-size:11px; margin-bottom:4px; }
.risk-copy h2 { font-size:18px; font-weight:700; letter-spacing:-.4px; margin:0 0 5px; }
.risk-copy > p:last-child { font-size:14px; line-height:1.65; color:var(--muted); margin:0; max-width:600px; }
.engine-badge { font-size:11px; letter-spacing:.5px; border:1px solid rgba(14,28,40,0.09); background:rgba(255,255,255,0.68); backdrop-filter:blur(8px); padding:5px 8px; border-radius:6px; white-space:nowrap; margin-left:auto; align-self:flex-start; color:var(--muted); }

/* Metrics */
.metrics-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.metric {
  padding:17px 18px;
  background:var(--glass); backdrop-filter:blur(20px) saturate(160%); -webkit-backdrop-filter:blur(20px) saturate(160%);
  border:1px solid var(--glass-bd); border-radius:var(--r);
  box-shadow:var(--shadow-md);
}
.metric p { margin:0 0 8px; font-size:13px; color:var(--muted); font-weight:500; }
.metric strong { display:block; font-size:25px; font-weight:700; line-height:1.2; letter-spacing:-.7px; margin-bottom:6px; }
.metric small { font-size:14px; font-weight:400; letter-spacing:0; color:var(--muted); }
.metric > span { display:block; font-size:12px; color:var(--subtle); line-height:1.6; }

/* Card heading */
.card-heading { display:flex; justify-content:space-between; align-items:center; gap:14px; padding:20px 22px 0; }
.card-heading .eyebrow { font-size:11px; margin-bottom:5px; }
.subtle-tag { font-size:12px; background:rgba(14,28,40,0.04); border:1px solid rgba(14,28,40,0.07); border-radius:7px; padding:5px 9px; white-space:nowrap; color:var(--muted); }

/* Chart */
.text-button { background:none; border:0; font-size:13px; color:var(--teal); padding:5px 0; cursor:pointer; white-space:nowrap; font-family:inherit; font-weight:500; }
.text-button:hover { text-decoration:underline; }
.result-actions { margin-top:14px; }
.result-actions { display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--line); padding:14px 22px; gap:12px; }
.outline-button {
  border: 1px solid rgba(10,150,136,0.35); border-radius: var(--r-xs);
  color: var(--teal); padding: 8px 13px; font-size: 13px; font-weight: 500;
  font-family: inherit; background: rgba(10,150,136,0.06); cursor: pointer;
  transition: all .15s ease;
}
.outline-button:hover { background: rgba(10,150,136,0.12); border-color: rgba(10,150,136,0.5); }
.outline-button:active { background: rgba(10,150,136,0.18); }
.result-actions a { color:var(--teal); font-size:13px; text-decoration:none; font-weight:500; }
.result-actions a:hover { text-decoration:underline; }

/* Assumptions */
.assumptions-card { padding-bottom:16px; }
.derived-values { display:grid; grid-template-columns:1fr 1fr; gap:13px; padding:17px 22px; font-size:13px; color:var(--muted); }
.derived-values b { display:block; font-size:14px; font-weight:500; margin-top:3px; color:var(--ink); }
.assumptions-card details { margin:0 22px; font-size:14px; color:var(--muted); }
.assumptions-card summary { cursor:pointer; color:var(--teal); font-weight:500; }
.assumptions-card ul { list-style:disc; padding-left:17px; margin-top:10px; line-height:1.8; }
.assumptions-card li { margin-bottom:5px; }
.verdict-list, .verdict-actions ul { list-style:disc; padding-left:17px; margin:0; font-size:14px; line-height:1.8; color:var(--ink-2); }
.verdict-list { margin:0 22px 14px; }
.verdict-actions { margin:0 22px 14px; padding:11px 13px; border-radius:var(--r-xs); background:rgba(10,150,136,0.06); border:1px solid rgba(10,150,136,0.12); }
.verdict-actions h3 { font-size:13px; font-weight:600; margin:0 0 6px; color:var(--teal-dk); }

/* Comparison */
.comparison-card { padding-bottom:10px; }
.table-scroll { overflow-x:auto; padding:13px 22px 5px; }
.comparison-card table { width:100%; border-collapse:collapse; font-size:14px; white-space:nowrap; text-align:left; }
.comparison-card th { font-weight:500; color:var(--muted); border-bottom:1px solid var(--line); padding:9px 9px 9px 0; }
.comparison-card td { padding:11px 9px 11px 0; border-bottom:1px solid var(--line); color:#3d5668; }

/* Empty state */
.empty-card { padding:100px 35px; text-align:center; color:var(--muted); }
.empty-symbol { font-size:46px; color:rgba(10,150,136,0.32); margin-bottom:16px; }
.empty-card h2 { font-size:18px; font-weight:600; color:var(--ink); }
.empty-card p { max-width:440px; margin:10px auto 0; font-size:16px; line-height:1.8; }

/* Physics note */
.physics-note { margin-top:26px; display:grid; grid-template-columns:1.15fr 1fr 1fr 1fr; gap:28px; border-top:1px solid var(--line); padding:26px 0 30px; }
.physics-note h2 { font-size:18px; letter-spacing:-.4px; font-weight:600; line-height:1.45; margin:0; max-width:210px; }
.physics-note h3 { font-size:14px; font-weight:600; margin:0 0 7px; color:var(--ink-2); }
.physics-note p:not(.eyebrow) { font-size:14px; line-height:1.85; color:var(--muted); margin:0; }

/* Footer */
.page-footer { display:flex; justify-content:space-between; padding:18px 0; border-top:1px solid var(--line); color:var(--subtle); font-size:12px; gap:15px; }


/* ── Responsive ──────────────────────────────────────────────────────────────── */

/* Desktop: all 3 columns, setup sticky */
@media(min-width:1024px) {
  .setup-panel { position:sticky; top:84px; }
}

/* Tablet (768–1023px): 3D + results columns, config becomes floating drawer */
@media(max-width:1023px) {
  .tri-layout { grid-template-columns: 300px minmax(0,1fr); gap:15px; }

  /* Setup panel floats as a slide-in drawer */
  .setup-panel {
    position: fixed !important;
    left: 0; top: 0; bottom: 0; z-index: 200;
    width: 300px; max-width: 88vw;
    border-radius: 0 var(--r) var(--r) 0;
    overflow-y: auto;
    transform: translateX(-100%);
    transition: transform 0.28s cubic-bezier(0.16,1,0.3,1),
                box-shadow 0.28s;
    box-shadow: none;
  }
  .setup-panel.open {
    transform: translateX(0);
    box-shadow: 8px 0 40px rgba(14,28,40,0.18);
  }

  .config-fab { display: flex; }
  .sidebar-close { display: block; }
  .engine-badge { display:none; }
  .physics-note { grid-template-columns:1fr 1fr; }
}

/* Mobile (<768px): single column, config floating drawer */
@media(max-width:767px) {
  .workspace { padding:18px 14px 44px; }
  .topbar { padding:0 16px; min-height:60px; }
  .tri-layout { grid-template-columns: 1fr; gap:13px; }
  .pipe-3d-wrap { height:280px; }

  .risk-card { padding:16px 16px; }
  .metrics-grid { gap:9px; }
  .card-heading { padding:16px 16px 0; }
  .physics-note { gap:16px; }
}

@media(max-width:767px) {
  .qs-brand { display: none; }
}

@media(max-width:540px) {
  .metrics-grid { grid-template-columns:1fr; }
  .metric { padding:14px 16px; }
  .metric strong { font-size:24px; }
  .risk-card { gap:12px; flex-wrap:wrap; }
  .risk-copy h2 { font-size:16px; }
  .risk-icon { width:36px; height:36px; font-size:17px; }
  .physics-note { grid-template-columns:1fr; }
  .physics-note h2 { max-width:none; }
  .result-actions { flex-wrap:wrap; }
  .subtle-tag { display:none; }
}
</style>
