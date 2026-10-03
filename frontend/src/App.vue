<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import PipeChart from '@/components/PipeChart.vue'
import SliderInput from '@/components/SliderInput.vue'
import type { PipeParams, PipeResult } from '@/types/pipe'
import { runEstimate, startJob, pollJob } from '@/api/analysis'

const defaults: PipeParams = {
  ambient_c: -20, water_c: 10, length_m: 20, diameter_mm: 25,
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
const form = ref<HTMLFormElement | null>(null)
let disposed = false
let pollTimer: ReturnType<typeof setTimeout> | undefined
let requestController: AbortController | undefined
const stale = computed(() => result.value !== null &&
  Object.keys(defaults).some(key => params[key as keyof PipeParams] !== result.value?.parameters[key as keyof PipeParams]))
const title = computed(() => result.value?.risk === 'freezing' ? 'Freezing onset predicted' :
  result.value?.risk === 'near' ? 'Close to freezing' : 'Above freezing during exposure')
const resultParams = computed(() => result.value?.parameters ?? params)
const insulationLabels = { none: 'No insulation', fiberglass: 'Fiber glass', foam_wrap: 'Foam wrap', mineral_wool: 'Mineral wool' }
watch(() => params.insulation_material, material => {
  if (material === 'none') params.insulation_mm = 0
  else if (params.insulation_mm === 0) params.insulation_mm = 20
})
const summary = computed(() => {
  const r = result.value
  if (!r) return 'Set up a pipe and run a simulation to explore the conditions.'
  if (r.freeze_hours !== null) return 'Water at the inner pipe wall reaches 0 °C after ' + formatTime(r.freeze_hours) + '. Bulk water may still be warmer. The calculation ends at first freezing onset.'
  return 'The estimated water / inner-wall interface stays above 0 °C throughout the ' + r.parameters.duration_h + '-hour cold exposure.'
})
const pipeGradient = computed(() => {
  const profile = result.value?.profile
  if (!profile) return '#b9e1e5'
  return 'linear-gradient(90deg, ' + profile.map((p, i) =>
    temperatureColor(p.temperature_c) + ' ' + (100 * i / (profile.length - 1)).toFixed(2) + '%').join(', ') + ')'
})
function temperatureColor(t: number) {
  return 'hsl(' + (205 - Math.min(1, Math.max(0, t / 15)) * 45) + ', 65%, 58%)'
}
function formatTime(hours: number | null) {
  if (hours === null) return 'No onset'
  if (hours * 60 < 1) return Math.round(hours * 3600) + ' sec'
  if (hours < 1) return (hours * 60).toFixed(1) + ' min'
  return hours.toFixed(2) + ' hr'
}
function applyPreset(preset: 'exposed' | 'insulated' | 'flowing') {
  Object.assign(params, defaults)
  if (preset === 'insulated') { params.insulation_material = 'foam_wrap'; params.insulation_mm = 30 }
  if (preset === 'flowing') params.flow_l_min = 2
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
  progress.value = 0
  message.value = engine.value === 'estimate' ? 'Calculating pipe cooling…' : 'Connecting to Allsolve…'
  requestController = new AbortController()
  const snapshot = { ...params }
  try {
    if (engine.value === 'estimate') {
      const response = await runEstimate(snapshot, requestController.signal)
      if (!disposed) { result.value = response; busy.value = false }
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
  const metadata = Object.entries(r.parameters).map(([key, value]) => '# ' + key + ',' + value).join('\n')
  const csv = '# Frost pipe simulation\n# engine,' + r.engine +
    '\n# inner-wall freezing onset only; no blockage or bursting prediction\n# wind_m_s,3\n' + metadata +
    '\nhours,minimum_bulk_water_c,minimum_inner_wall_interface_c\n' +
    r.history.map(p => p.hours + ',' + p.temperature_c + ',' + p.interface_temperature_c).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'frost-pipe-results.csv'
  link.click()
  URL.revokeObjectURL(url)
}
onMounted(() => run())
onUnmounted(() => {
  disposed = true
  if (pollTimer) clearTimeout(pollTimer)
  requestController?.abort()
})
</script>

<template>
  <div class="frost-app">
    <header class="topbar">
      <div class="brand"><span class="brand-symbol" aria-hidden="true">✳</span><span>frost<span class="brand-dot">.</span></span><span class="brand-caption">INFRASTRUCTURE RESILIENCE</span></div>
      <span class="header-tag"><span class="status-dot"></span> Water systems · Thermal simulation</span>
    </header>
    <main class="workspace">
      <div class="page-heading">
        <div><p class="eyebrow">COLD WEATHER / WATER INFRASTRUCTURE</p><h1>When does your water freeze?</h1><p class="intro">Explore how exposure, insulation and flow affect an unprepared water pipe.</p></div>
        <div class="model-tag">FREEZING ONSET MODEL <span>v2.0</span></div>
      </div>
      <div class="simulation-layout">
        <aside class="setup-panel">
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
                <div class="input-grid">
                  <label>Pipe length<div class="number-input"><input v-model.number="params.length_m" type="number" min="0.1" max="1000" step="0.1" required /><span>m</span></div></label>
                  <label>Pipe material<select v-model="params.material"><option value="copper">Copper</option><option value="steel">Steel</option><option value="pvc">PVC</option><option value="pex">PEX</option></select></label>
                </div>
                <SliderInput v-model="params.wall_mm" label="Pipe wall thickness" :min="0.5" :max="30" :step="0.5" unit="mm" />
                <SliderInput v-model="params.diameter_mm" label="Inner diameter" :min="5" :max="500" :step="0.5" unit="mm" />
              </section>
              <section class="input-section">
                <h3><span class="section-icon">◎</span> Insulation</h3>
                <label>Pipe insulation material<select v-model="params.insulation_material"><option value="fiberglass">Fiber glass</option><option value="foam_wrap">Foam wrap</option><option value="mineral_wool">Mineral wool</option><option value="none">No insulation</option></select></label>
                <SliderInput v-if="params.insulation_material !== 'none'" v-model="params.insulation_mm" label="Insulation thickness" :min="1" :max="200" :step="1" unit="mm" />
                <p class="input-hint">{{ params.insulation_material === 'none' ? 'Bare pipe. Insulation thickness is 0 mm.' : 'Dry, intact material. Representative conductivity is assigned automatically; actual product and moisture can change performance.' }}</p>
              </section>
              <section class="input-section">
                <h3><span class="section-icon">❄</span> External conditions</h3>
                <p class="exposure-note">Continuously exposed to outside air · <b>3 m/s wind</b></p>
                <div class="input-grid">
                  <label>Outside temperature<div class="number-input"><input v-model.number="params.ambient_c" type="number" min="-60" max="30" step="1" required /><span>°C</span></div></label>
                  <label>Cold snap duration<div class="number-input"><input v-model.number="params.duration_h" type="number" min="0.1" max="168" step="0.1" required /><span>hr</span></div></label>
                </div>
                <p class="input-hint">Outside temperature and wind stay constant. Convection and radiation are estimated automatically.</p>
              </section>
              <section class="input-section">
                <h3><span class="section-icon">≈</span> Water</h3>
                <SliderInput v-model="params.water_c" label="Initial water temperature" :min="0.1" :max="60" :step="0.1" unit="°C" />
                <SliderInput v-model="params.flow_l_min" label="Drip flow" :min="0" :max="2" :step="0.001" unit="L/min" />
                <p class="input-hint">0 L/min means stagnant water. A constant drip supplies water at the initial temperature. 0.01 L/min = 0.6 L/hr.</p>
              </section>
              <section class="engine-section">
                <label>Calculation engine<select v-model="engine"><option value="estimate">Quick estimate</option><option value="allsolve">Quanscient Allsolve · cloud FEM</option></select></label>
                <p class="input-hint">{{ engine === 'estimate' ? 'Coupled water / wall thermal model. No cloud credentials needed.' : 'Runs the coupled pipe model in Allsolve. Uses your configured account and cloud compute.' }}</p>
              </section>
            </fieldset>
            <button class="run-button" type="submit" :disabled="busy"><span>{{ busy ? 'Simulation running…' : 'Run simulation' }}</span><span aria-hidden="true">{{ busy ? '◌' : '→' }}</span></button>
            <div v-if="busy" class="progress-area" role="status"><progress :value="progress" max="100"></progress><span>{{ message }}</span></div>
            <p v-if="error" class="error-message" role="alert">{{ error }}</p>
          </form>
        </aside>

        <div class="results-panel">
          <div v-if="stale" class="stale-notice" role="status">Parameters changed. Run again to update the results below.</div>
          <template v-if="result">
            <section class="risk-card" :class="'risk-' + result.risk">
              <div class="risk-icon" aria-hidden="true">{{ result.risk === 'freezing' ? '❄' : result.risk === 'near' ? '!' : '✓' }}</div>
              <div class="risk-copy"><p class="eyebrow">SIMULATION ASSESSMENT</p><h2>{{ title }}</h2><p>{{ summary }}</p></div>
              <span class="engine-badge">{{ result.engine === 'allsolve' ? 'ALLSOLVE FEM' : 'QUICK ESTIMATE' }}</span>
            </section>
            <div class="metrics-grid">
              <div class="metric"><p>Time to freezing onset</p><strong>{{ formatTime(result.freeze_hours) }}</strong><span>Within {{ result.parameters.duration_h }} hr of exposure</span></div>
              <div class="metric"><p>Coldest bulk water</p><strong>{{ result.minimum_c.toFixed(1) }}<small> °C</small></strong><span>At {{ formatTime(result.end_hours) }}</span></div>
              <div class="metric"><p>Steady flow threshold · estimate</p><strong>{{ result.critical_flow_l_min.toFixed(3) }}<small> L/min</small></strong><span>{{ result.flow_threshold_note }}</span></div>
            </div>

            <section class="visualization-card">
              <div class="card-heading"><div><p class="eyebrow">EXPOSED PIPE · 3 M/S WIND</p><h2>Temperature along the water line</h2></div><span class="subtle-tag">{{ resultParams.length_m }} m · {{ resultParams.material.toUpperCase() }}</span></div>
              <div class="pipe-scene">
                <div class="ambient-label">❄ Outside {{ resultParams.ambient_c }} °C · {{ result.environment.wind_m_s }} m/s wind</div>
                <div class="pipe-labels"><span>{{ resultParams.flow_l_min > 0 ? 'INLET' : 'STAGNANT WATER' }}</span><span>{{ resultParams.flow_l_min > 0 ? 'OUTLET' : 'EXPOSED END' }}</span></div>
                <div class="pipe-insulation" :class="{ insulated: resultParams.insulation_mm > 0 }">
                  <div class="pipe-wall"><div class="pipe-water" :style="{ background: pipeGradient }"><span v-if="resultParams.flow_l_min > 0" class="flow-arrows" aria-hidden="true">→ &nbsp; → &nbsp; → &nbsp; → &nbsp; →</span></div></div>
                  <div class="pipe-collar collar-left"></div><div class="pipe-collar collar-right"></div>
                </div>
                <div class="pipe-temperatures"><span>{{ result.profile[0].temperature_c.toFixed(1) }} °C</span><span>{{ result.profile[result.profile.length - 1].temperature_c.toFixed(1) }} °C</span></div>
                <div class="pipe-legend"><span><i class="legend-color cold"></i>0 °C</span><div></div><span><i class="legend-color warm"></i>15 °C</span></div>
                <p class="schematic-caption">Schematic, not to scale · Bulk water at {{ formatTime(result.end_hours) }}{{ result.freeze_hours !== null ? ' · Calculation stops at onset' : '' }}</p>
              </div>
              <div class="pipe-details"><span><b>{{ insulationLabels[resultParams.insulation_material] }}</b>{{ resultParams.insulation_material !== 'none' ? ' · ' + resultParams.insulation_mm + ' mm' : '' }}</span><span><b>{{ resultParams.flow_l_min }} L/min</b> drip</span><span><b>{{ result.residence_minutes === null ? 'Stagnant' : result.residence_minutes.toFixed(1) + ' min' }}</b> {{ result.residence_minutes === null ? 'water' : 'residence time' }}</span></div>
            </section>

            <section class="assumptions-card">
              <div class="card-heading"><div><p class="eyebrow">CONDITIONS USED IN THIS RUN</p><h2>Derived heat transfer & approximations</h2></div></div>
              <div class="derived-values"><span>Pipe conductivity <b>{{ result.environment.pipe_k_w_mk }} W/m·K</b></span><span>Insulation conductivity <b>{{ result.environment.insulation_k_w_mk === null ? 'None' : result.environment.insulation_k_w_mk + ' W/m·K' }}</b></span><span>External convection + radiation <b>{{ result.environment.external_h_w_m2k.toFixed(1) }} W/m²·K</b></span><span>Water-side heat transfer <b>{{ result.environment.internal_h_w_m2k.toFixed(1) }} W/m²·K</b></span></div>
              <p v-if="result.freeze_hours !== null && result.minimum_c > 0" class="wall-note">At first freezing onset the bulk water is still {{ result.minimum_c.toFixed(1) }} °C. The reported event is water at the inner pipe wall reaching 0 °C.</p>
              <details><summary>Model assumptions and limits</summary><ul><li v-for="assumption in result.assumptions" :key="assumption">{{ assumption }}</li></ul></details>
            </section>

            <section class="chart-card">
              <div class="card-heading"><div><p class="eyebrow">THERMAL RESPONSE</p><h2>How fast does the water cool?</h2></div><button class="text-button" type="button" @click="exportResult">Export CSV ↗</button></div>
              <PipeChart :result="result" />
              <p v-if="result.freeze_hours !== null" class="chart-note">The curves end when the water / inner-wall interface reaches 0 °C. Ice growth is outside this model.</p>
              <div class="result-actions"><button type="button" class="outline-button" :disabled="stale || comparison.length >= 4 || busy" @click="saveScenario">+ Save scenario for comparison</button><a v-if="result.project_url" :href="result.project_url" target="_blank" rel="noopener noreferrer">Open Allsolve project ↗</a></div>
            </section>

            <section v-if="comparison.length" class="comparison-card">
              <div class="card-heading"><div><p class="eyebrow">EXPLORE THE TRADEOFFS</p><h2>Scenario comparison</h2></div><button type="button" class="text-button" @click="comparison = []">Clear</button></div>
              <div class="table-scroll"><table><thead><tr><th>Scenario</th><th>Ambient</th><th>Insulation</th><th>Flow</th><th>Exposure</th><th>Freezing onset</th><th>Minimum</th><th></th></tr></thead><tbody><tr v-for="(scenario, index) in comparison" :key="index"><td>{{ index + 1 }} · {{ scenario.engine === 'estimate' ? 'Estimate' : 'Allsolve' }}</td><td>{{ scenario.parameters.ambient_c }} °C</td><td>{{ scenario.parameters.insulation_mm }} mm</td><td>{{ scenario.parameters.flow_l_min }} L/min</td><td>{{ scenario.parameters.duration_h }} hr</td><td>{{ formatTime(scenario.freeze_hours) }}</td><td>{{ scenario.minimum_c.toFixed(1) }} °C</td><td><button type="button" class="text-button" :aria-label="'Remove scenario ' + (index + 1)" @click="comparison.splice(index, 1)">×</button></td></tr></tbody></table></div>
            </section>
          </template>
          <section v-else class="empty-card"><div class="empty-symbol">◎</div><h2>Understand your cold-weather exposure</h2><p>Choose a scenario or enter your pipe parameters, then run the model to see freezing onset and water temperatures.</p></section>
        </div>
      </div>
      <section class="physics-note">
        <div><p class="eyebrow">ABOUT THIS MODEL</p><h2>Heat escapes. Flow replenishes it.</h2></div>
        <div><h3>What is calculated</h3><p>An exposed pipe in constant outside air at 3 m/s. Water and pipe wall exchange heat through radial resistance and cool through insulation, convection and radiation. A drip supplies fresh water at the initial temperature.</p></div>
        <div><h3>What freezing onset means</h3><p>Water at the inner pipe wall reaches 0 °C at atmospheric pressure. Bulk water can still be warmer. Separate water and wall thermal nodes estimate this first onset; ice growth, blockage and bursting need a fuller model.</p></div>
        <div><h3>Use the results to compare</h3><p>Compare pipe materials, insulation and drip flow. The local and Allsolve models share their thermal coefficients. The steady inner-wall freezing threshold accounts for flow-dependent internal heat transfer.</p></div>
      </section>
      <footer class="page-footer"><span>FROST · Water infrastructure resilience</span><span>Vue 3 + Quanscient Allsolve</span></footer>
    </main>
  </div>
</template>

<style>
.frost-app { --ink:#152c3c; --muted:#657985; --line:#dfe7eb; --teal:#087f79; color:var(--ink); background:#f3f6f8; min-height:100vh; font-family:Inter,system-ui,sans-serif; }
.topbar { background:#112d3b; color:#fff; min-height:78px; display:flex; align-items:center; justify-content:space-between; padding:0 max(28px,calc((100vw - 1400px)/2)); gap:20px; }
.brand { display:flex; align-items:center; gap:12px; font-size:30px; font-weight:700; letter-spacing:-1.2px; }
.brand-symbol { color:#75dcd2; font-size:34px; font-weight:400; }
.brand-dot { color:#75dcd2; }
.brand-caption { margin-left:20px; padding-left:24px; border-left:1px solid #ffffff2b; font-size:10px; font-weight:500; letter-spacing:1.9px; }
.header-tag { font-size:11px; color:#bad0d8; display:flex; align-items:center; gap:8px; }
.status-dot { width:6px; height:6px; border-radius:50%; background:#75dcd2; }
.workspace { max-width:1456px; padding:38px 28px 0; margin:auto; }
.page-heading { display:flex; align-items:center; justify-content:space-between; margin-bottom:30px; gap:20px; }
.eyebrow { font-size:10px; letter-spacing:1.7px; font-weight:600; color:var(--muted); margin:0 0 9px; }
.page-heading h1 { font-size:34px; font-weight:600; letter-spacing:-1.3px; line-height:1.25; margin:0 0 10px; }
.intro { color:var(--muted); font-size:14px; margin:0; }
.model-tag { font-size:9px; font-weight:600; color:#77909b; border:1px solid var(--line); padding:11px 13px; border-radius:5px; letter-spacing:1px; white-space:nowrap; }
.model-tag span { margin-left:14px; color:var(--teal); }
.simulation-layout { display:grid; grid-template-columns:350px minmax(0,1fr); gap:24px; align-items:start; }
.setup-panel,.visualization-card,.chart-card,.comparison-card,.empty-card { background:#fff; border:1px solid var(--line); border-radius:10px; overflow:hidden; }
.setup-panel { padding:22px; }
.panel-heading { display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; }
.panel-heading h2,.card-heading h2 { font-size:16px; font-weight:600; margin:0; letter-spacing:-.25px; }
.step-number { font-size:11px; color:#8ba0aa; font-family:monospace; }
.setup-panel fieldset { padding:0; border:0; margin:0; min-width:0; }
.presets { display:flex; padding:4px; gap:4px; background:#f1f5f7; border-radius:6px; margin-bottom:8px; }
.presets button { flex:1; padding:8px 4px; border:0; border-radius:4px; color:#42616f; font-size:11px; background:#fff; box-shadow:0 1px 2px #00000006; cursor:pointer; }
.presets button:hover { color:var(--teal); background:#e8f6f4; }
.input-section { padding:18px 0 16px; border-bottom:1px solid #edf1f3; }
.input-section h3 { font-size:12px; font-weight:600; display:flex; gap:8px; align-items:center; margin:0 0 14px; }
.section-icon { color:var(--teal); font-size:16px; width:19px; text-align:center; }
.input-grid { display:grid; grid-template-columns:1fr 1fr; gap:11px; }
.input-grid + .input-grid { margin-top:11px; }
.setup-panel label { font-size:10px; color:#57707e; display:block; line-height:1.6; }
.number-input { display:flex; align-items:center; background:#fbfcfd; border:1px solid #dce5e9; border-radius:5px; height:39px; margin-top:5px; overflow:hidden; }
.number-input:focus-within { border-color:var(--teal); box-shadow:0 0 0 2px #087f7910; }
.number-input input { font:500 13px Inter,system-ui,sans-serif; width:100%; min-width:0; border:0; outline:none; background:transparent; padding:9px 0 9px 10px; color:var(--ink); }
.number-input span { font-size:10px; color:#78909b; white-space:nowrap; padding:0 9px 0 4px; }
.setup-panel select { display:block; width:100%; padding:9px 7px; margin-top:5px; border:1px solid #dce5e9; background:#fbfcfd; border-radius:5px; font-size:12px; color:var(--ink); height:39px; }
.input-section > label { margin-top:11px; }
.input-hint { color:#8a9ca6; font-size:10px; line-height:1.65; margin:8px 0 0; }
.exposure-note { padding:10px 12px; border-radius:5px; background:#eff7f6; color:#4d7777; font-size:11px; line-height:1.7; margin:0 0 12px; }
.assumptions-card { background:white; border:1px solid var(--line); border-radius:10px; padding-bottom:18px; }
.derived-values { display:grid; grid-template-columns:1fr 1fr; gap:15px; padding:18px 24px; font-size:10px; color:var(--muted); }
.derived-values b { display:block; font-size:12px; font-weight:500; margin-top:4px; color:var(--ink); }
.assumptions-card details { margin:0 24px; font-size:11px; color:var(--muted); }
.assumptions-card summary { cursor:pointer; color:var(--teal); }
.assumptions-card ul { list-style:disc; padding-left:18px; margin-top:12px; line-height:1.8; }
.assumptions-card li { margin-bottom:6px; }
.wall-note { margin:0 24px 16px; padding:10px 12px; font-size:11px; line-height:1.7; color:#956a36; background:#fff9ec; border-radius:5px; }
.engine-section { padding:17px 0 19px; }
.run-button { width:100%; background:var(--teal); color:#fff; border:0; border-radius:6px; padding:13px 15px; display:flex; align-items:center; justify-content:space-between; font-size:12px; font-weight:600; cursor:pointer; }
.run-button:hover { background:#056963; }
button:disabled { opacity:.5; cursor:not-allowed; }
input:disabled,select:disabled { opacity:.65; }
button:focus-visible,select:focus-visible,a:focus-visible { outline:2px solid #22a99e; outline-offset:3px; }
.progress-area { margin-top:14px; font-size:11px; color:var(--muted); }
.progress-area progress { display:block; width:100%; height:5px; accent-color:var(--teal); margin-bottom:8px; }
.error-message { background:#fff2ee; color:#a4412a; padding:12px; margin:12px 0 0; font-size:12px; line-height:1.6; border-radius:5px; }
.results-panel { display:flex; flex-direction:column; gap:18px; min-width:0; }
.stale-notice { font-size:12px; color:#7a642b; background:#fff8e6; border:1px solid #eee1bb; padding:12px 16px; border-radius:7px; }
.risk-card { display:flex; align-items:center; gap:17px; background:#edf8f5; border:1px solid #cce7df; border-radius:9px; padding:21px 24px; position:relative; }
.risk-freezing { background:#fff3ed; border-color:#efd6c8; }
.risk-near { background:#fff9ea; border-color:#eee1bc; }
.risk-icon { font-size:25px; width:44px; height:44px; display:flex; align-items:center; justify-content:center; background:#fff; color:var(--teal); border-radius:50%; flex-shrink:0; }
.risk-freezing .risk-icon { color:#c16d43; }.risk-near .risk-icon { color:#af8129; }
.risk-copy { min-width:0; }
.risk-copy .eyebrow { font-size:9px; margin-bottom:5px; }
.risk-copy h2 { font-size:20px; font-weight:600; letter-spacing:-.4px; margin:0 0 7px; }
.risk-copy > p:last-child { font-size:11px; line-height:1.7; color:#6d797c; margin:0; max-width:620px; }
.engine-badge { font-size:8px; letter-spacing:.8px; border:1px solid #d5dfde; background:#ffffff90; padding:6px 8px; border-radius:4px; white-space:nowrap; margin-left:auto; align-self:flex-start; }
.metrics-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.metric { padding:18px 20px; background:white; border:1px solid var(--line); border-radius:8px; }
.metric p { margin:0 0 10px; font-size:10px; color:var(--muted); }
.metric strong { display:block; font-size:27px; font-weight:600; line-height:1.2; letter-spacing:-.8px; margin-bottom:8px; }
.metric small { font-size:14px; font-weight:400; letter-spacing:0; color:var(--muted); }
.metric > span { display:block; font-size:9px; color:#8a9ba6; line-height:1.6; }
.card-heading { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:22px 24px 0; }
.card-heading .eyebrow { font-size:9px; margin-bottom:6px; }
.subtle-tag { font-size:10px; background:#f2f5f7; border:1px solid #e6ecef; border-radius:4px; padding:6px 9px; white-space:nowrap; color:#78909b; }
.pipe-scene { padding:24px 44px 16px; background:radial-gradient(ellipse at center,#f2f8fb 0,white 70%); margin-top:10px; }
.ambient-label { font-size:10px; color:#7d9bad; text-align:center; margin-bottom:28px; }
.pipe-labels,.pipe-temperatures { display:flex; justify-content:space-between; }
.pipe-labels { font-size:8px; font-weight:600; letter-spacing:1.5px; color:#8aa0ac; margin-bottom:12px; }
.pipe-insulation { padding:10px 0; border:2px solid transparent; border-radius:6px; position:relative; }
.pipe-insulation.insulated { background:repeating-linear-gradient(120deg,#e4e9e9,#e4e9e9 4px,#f1f4f4 4px,#f1f4f4 8px); border-color:#c5d1d3; padding:10px; }
.pipe-wall { background:linear-gradient(#91a8b5,#e6edf2 18%,#e6edf2 82%,#91a8b5); padding:7px 0; border:1px solid #a4b7c3; border-radius:4px; }
.pipe-water { height:39px; display:flex; align-items:center; justify-content:center; overflow:hidden; box-shadow:inset 0 3px 6px #163f5910; }
.flow-arrows { color:#ffffffc9; font-size:24px; letter-spacing:16px; white-space:nowrap; }
.pipe-collar { position:absolute; width:15px; height:65px; top:5px; border-radius:3px; border:1px solid #a6b9c4; background:linear-gradient(90deg,#b0c1cb,#f2f6f8,#b0c1cb); }
.collar-left { left:10px; }.collar-right { right:10px; }
.pipe-temperatures { font-size:12px; color:#4f7184; font-weight:600; margin-top:13px; }
.pipe-legend { display:flex; align-items:center; justify-content:center; gap:8px; margin:21px auto 12px; font-size:9px; color:#8496a1; }
.pipe-legend > div { background:linear-gradient(90deg,hsl(205,65%,58%),hsl(160,65%,58%)); width:85px; height:5px; border-radius:5px; }
.legend-color { display:none; }
.schematic-caption { font-size:9px; color:#92a3ad; text-align:center; margin:0; line-height:1.6; }
.pipe-details { border-top:1px solid #edf1f3; display:flex; justify-content:space-around; padding:14px; gap:12px; font-size:10px; color:#8397a2; flex-wrap:wrap; }
.pipe-details b { color:#526f7f; font-weight:500; }
.chart-wrap { height:295px; padding:18px 23px 0; }
.text-button { background:none; border:0; font-size:10px; color:var(--teal); padding:6px 0; cursor:pointer; white-space:nowrap; }
.text-button:hover { text-decoration:underline; }
.chart-note { padding:0 24px; margin:6px 0 16px; font-size:10px; color:#8a9ba5; }
.result-actions { display:flex; justify-content:space-between; align-items:center; border-top:1px solid #edf1f3; padding:16px 24px; gap:12px; }
.outline-button { border:1px solid #d7e3e6; border-radius:5px; color:#547985; padding:8px 11px; font-size:10px; background:white; cursor:pointer; }
.result-actions a { color:var(--teal); font-size:10px; text-decoration:none; }
.comparison-card { padding-bottom:10px; }
.table-scroll { overflow-x:auto; padding:15px 24px 5px; }
.comparison-card table { width:100%; border-collapse:collapse; font-size:10px; white-space:nowrap; text-align:left; }
.comparison-card th { font-weight:500; color:#8196a1; border-bottom:1px solid var(--line); padding:10px 10px 10px 0; }
.comparison-card td { padding:12px 10px 12px 0; border-bottom:1px solid #edf1f3; color:#476472; }
.empty-card { padding:110px 35px; text-align:center; color:var(--muted); }
.empty-symbol { font-size:54px; color:#94c8cc; margin-bottom:20px; }
.empty-card h2 { font-size:19px; font-weight:500; color:var(--ink); }
.empty-card p { max-width:460px; margin:12px auto 0; font-size:13px; line-height:1.8; }
.physics-note { margin-top:32px; display:grid; grid-template-columns:1.15fr 1fr 1fr 1fr; gap:30px; border-top:1px solid var(--line); padding:28px 0 32px; }
.physics-note h2 { font-size:20px; letter-spacing:-.5px; font-weight:500; line-height:1.5; margin:0; max-width:220px; }
.physics-note h3 { font-size:11px; font-weight:600; margin:0 0 9px; }
.physics-note p:not(.eyebrow) { font-size:10px; line-height:1.9; color:#7d929e; margin:0; }
.page-footer { display:flex; justify-content:space-between; padding:20px 0; border-top:1px solid var(--line); color:#98a9b2; font-size:9px; gap:15px; }
@media(min-width:1200px) { .setup-panel { position:sticky; top:20px; } }
@media(max-width:1100px) { .simulation-layout { grid-template-columns:310px minmax(0,1fr); gap:18px; }.risk-card { padding:18px; }.engine-badge { display:none; }.metric { padding:16px 13px; }.metric strong { font-size:23px; }.physics-note { grid-template-columns:1fr 1fr; }.brand-caption { display:none; } }
@media(max-width:800px) { .workspace { padding:27px 18px 0; }.topbar { padding:0 18px; min-height:65px; }.header-tag { font-size:9px; }.page-heading h1 { font-size:28px; }.page-heading { margin-bottom:23px; }.model-tag { display:none; }.simulation-layout { grid-template-columns:1fr; }.setup-panel { padding:20px; }.input-section { padding:14px 0; }.pipe-scene { padding-left:28px; padding-right:28px; }.physics-note { gap:20px; }.metrics-grid { gap:9px; }.card-heading { padding:20px 18px 0; } }
@media(max-width:480px) { .header-tag { display:none; }.page-heading h1 { font-size:25px; }.intro { font-size:12px; line-height:1.7; }.metrics-grid { grid-template-columns:1fr; }.metric { padding:15px 18px; }.metric strong { font-size:26px; }.risk-card { gap:12px; }.risk-copy h2 { font-size:17px; }.risk-icon { width:35px; height:35px; font-size:20px; }.physics-note { grid-template-columns:1fr; }.physics-note h2 { max-width:none; }.result-actions { flex-wrap:wrap; }.pipe-details { font-size:9px; }.subtle-tag { display:none; }.chart-wrap { padding-left:10px; padding-right:12px; } }
</style>
