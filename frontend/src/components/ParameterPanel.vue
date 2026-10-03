<script setup lang="ts">
import { useAnalysisStore } from '@/stores/analysisStore'
import {
  PIPE_MATERIALS,
  INSULATION_TYPES,
  LOCATIONS,
  FIXED_LOCATION,
  type PipeMaterial,
  type InsulationType,
  type Location,
  type PipeParams,
} from '@/types'

const store = useAnalysisStore()

type NumericKey = {
  [K in keyof PipeParams]: PipeParams[K] extends number ? K : never
}[keyof PipeParams]

interface SliderSpec {
  key: NumericKey
  label: string
  min: number
  max: number
  step: number
  unit: string
  hint?: () => string
}

const pipeSliders: SliderSpec[] = [
  { key: 'wall_thickness_mm', label: 'Wall thickness', min: 0.5, max: 10, step: 0.1, unit: 'mm' },
  { key: 'inner_diameter_mm', label: 'Inner diameter', min: 6, max: 100, step: 1, unit: 'mm' },
]

const conditionSliders: SliderSpec[] = [
  { key: 'outside_temp_c', label: 'Outside temperature', min: -40, max: -1, step: 1, unit: '°C' },
  { key: 'cold_snap_hours', label: 'Cold snap duration', min: 1, max: 48, step: 1, unit: 'h' },
]

const waterSliders: SliderSpec[] = [
  { key: 'initial_water_temp_c', label: 'Initial water temperature', min: 1, max: 25, step: 1, unit: '°C' },
  {
    key: 'drip_flow_lpm',
    label: 'Drip flow',
    min: 0,
    max: 1,
    step: 0.01,
    unit: 'L/min',
    hint: () => (store.params.drip_flow_lpm === 0 ? 'Stagnant' : 'Tap left dripping'),
  },
]

const materialOptions = Object.entries(PIPE_MATERIALS) as [PipeMaterial, (typeof PIPE_MATERIALS)[PipeMaterial]][]
const insulationOptions = Object.entries(INSULATION_TYPES) as [InsulationType, (typeof INSULATION_TYPES)[InsulationType]][]
const locationOptions = Object.entries(LOCATIONS) as [Location, (typeof LOCATIONS)[Location]][]

function onSlider(key: NumericKey, event: Event) {
  store.setParam(key, Number((event.target as HTMLInputElement).value))
}

function toggleMode() {
  store.setDemoMode(!store.useDemoMode)
}
</script>

<template>
  <div class="parameter-panel">
    <!-- ================= PIPE ================= -->
    <section class="input-section">
      <h3><span class="section-icon">↔</span> Pipe</h3>

      <div v-for="s in pipeSliders" :key="s.key" class="param-slider">
        <div class="param-row">
          <label :for="`param-${s.key}`">{{ s.label }}</label>
          <span class="param-value">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input :id="`param-${s.key}`" type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
      </div>

      <div class="param-group">
        <span class="param-label">Pipe material</span>
        <div class="option-group cols-4">
          <button
            v-for="[value, spec] in materialOptions"
            :key="value"
            type="button"
            :class="{ selected: store.params.pipe_material === value }"
            :aria-pressed="store.params.pipe_material === value"
            @click="store.setParam('pipe_material', value)"
          >
            {{ spec.label }}
          </button>
        </div>
      </div>

      <div class="param-group">
        <span class="param-label">Insulation material</span>
        <div class="option-group cols-2">
          <button
            v-for="[value, spec] in insulationOptions"
            :key="value"
            type="button"
            :class="{ selected: store.params.insulation === value }"
            :aria-pressed="store.params.insulation === value"
            @click="store.setParam('insulation', value)"
          >
            {{ spec.label }}
          </button>
        </div>
        <div class="param-slider" :class="{ dimmed: store.params.insulation === 'none' }">
          <div class="param-row">
            <label for="param-insulation_thickness_mm">Insulation thickness</label>
            <span class="param-value">
              {{ store.params.insulation === 'none' ? '—' : `${store.params.insulation_thickness_mm} mm` }}
            </span>
          </div>
          <input
            id="param-insulation_thickness_mm"
            type="range"
            :value="store.params.insulation_thickness_mm"
            @input="onSlider('insulation_thickness_mm', $event)"
            :disabled="store.params.insulation === 'none'"
            min="5"
            max="50"
            step="1"
          />
        </div>
      </div>
    </section>

    <!-- ================= EXTERNAL CONDITIONS ================= -->
    <section class="input-section">
      <h3><span class="section-icon">❄</span> External conditions</h3>

      <div class="param-group">
        <span class="param-label">Where the pipe is</span>
        <div class="option-group cols-3">
          <!-- Fixed in this version: shown for context, not selectable -->
          <button
            v-for="[value, spec] in locationOptions"
            :key="value"
            type="button"
            disabled
            :aria-pressed="value === FIXED_LOCATION"
            :class="{ selected: value === FIXED_LOCATION, fixed: value === FIXED_LOCATION }"
          >
            {{ spec.label }}
          </button>
        </div>
        <p class="input-hint">Fixed to {{ LOCATIONS[FIXED_LOCATION].label.toLowerCase() }} in this version.</p>
        <p class="exposure-note">
          <b>Assumed:</b> {{ LOCATIONS[store.params.location].summary }}
        </p>
      </div>

      <div v-for="s in conditionSliders" :key="s.key" class="param-slider">
        <div class="param-row">
          <label :for="`param-${s.key}`">{{ s.label }}</label>
          <span class="param-value">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input :id="`param-${s.key}`" type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
      </div>
      <p class="input-hint">
        External heat transfer is estimated from the location and outside temperature.
      </p>
    </section>

    <!-- ================= WATER ================= -->
    <section class="input-section">
      <h3><span class="section-icon">≈</span> Water</h3>

      <div v-for="s in waterSliders" :key="s.key" class="param-slider">
        <div class="param-row">
          <label :for="`param-${s.key}`">{{ s.label }}</label>
          <span class="param-value">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input :id="`param-${s.key}`" type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
        <p v-if="s.hint" class="input-hint">{{ s.hint() }}</p>
      </div>
    </section>

    <!-- Analysis Mode Toggle -->
    <section class="engine-section">
      <button
        type="button"
        class="mode-toggle"
        :class="store.useDemoMode ? 'mode-demo' : 'mode-full'"
        :disabled="store.isRunning"
        @click="toggleMode"
      >
        <span class="mode-name">{{ store.useDemoMode ? 'Demo (local estimate)' : 'Full simulation (Allsolve)' }}</span>
        <span class="mode-switch">click to switch</span>
      </button>
      <p class="input-hint mode-hint">
        {{ store.useDemoMode
          ? 'Lumped heat-loss model with a latent-heat plateau (instant)'
          : '3D FEM with freezing, on the Quanscient Allsolve cloud (requires API key)' }}
      </p>
    </section>

    <!-- Action Buttons -->
    <div class="actions">
      <button v-if="!store.isRunning" type="button" class="run-button" @click="store.startAnalysis()">
        <span>Analyse freeze risk</span><span aria-hidden="true">→</span>
      </button>

      <button v-if="store.isRunning" type="button" class="run-button abort-button" @click="store.abortAnalysis()">
        <span class="abort-copy">
          <span class="abort-title">{{ Math.round(store.progress) }}% — Click to Abort</span>
          <span class="abort-message">{{ store.message }}</span>
        </span>
        <span class="spinner" aria-hidden="true"></span>
      </button>
      <div v-if="store.isRunning" class="progress-area" role="status">
        <progress :value="store.progress" max="100"></progress>
      </div>

      <div class="secondary-actions">
        <button
          v-if="store.results !== null || store.status === 'failed'"
          type="button"
          class="outline-button"
          @click="store.reset()"
        >
          Clear results
        </button>
        <button v-if="!store.isRunning" type="button" class="outline-button" @click="store.resetParams()">
          Default inputs
        </button>
      </div>
    </div>

    <!-- Status Message -->
    <p
      v-if="store.message && !store.isRunning"
      :class="store.status === 'failed' ? 'error-message' : 'status-message'"
      :role="store.status === 'failed' ? 'alert' : 'status'"
    >
      {{ store.message }}
    </p>
  </div>
</template>

<style scoped>
.param-slider { margin-top: 12px; }
.param-slider.dimmed { opacity: .5; }
.param-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 4px; }
.param-row label { margin: 0; }
.param-value { font-size: 14px; font-weight: 600; color: var(--teal); font-variant-numeric: tabular-nums; white-space: nowrap; }
.param-slider input[type="range"]:disabled { cursor: not-allowed; }

.param-group { margin-top: 12px; }
.param-label { display: block; font-size: 13px; color: var(--muted); font-weight: 500; line-height: 1.5; margin-bottom: 6px; }

/* Segmented option buttons */
.option-group { display: grid; gap: 3px; padding: 4px; background: rgba(14,28,40,0.05); border-radius: var(--r-sm); }
.option-group.cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.option-group.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.option-group.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.option-group button {
  padding: 8px 4px; border: 1px solid transparent; border-radius: 7px; color: var(--muted);
  font-size: 13px; font-weight: 500; background: transparent; cursor: pointer;
  font-family: inherit; transition: all .16s ease; min-width: 0;
}
.option-group button:hover:not(:disabled) { background: rgba(10,150,136,0.1); color: var(--teal); }
.option-group button.selected {
  background: rgba(255,255,255,0.92); color: var(--teal-dk); border-color: rgba(10,150,136,0.25);
  box-shadow: 0 1px 4px rgba(14,28,40,0.08);
}
/* Fixed location: selected but not interactive, so keep it fully legible */
.option-group button.fixed:disabled { opacity: 1; }

.exposure-note { margin: 8px 0 0; }

/* Mode toggle */
.mode-toggle {
  width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 10px 12px; border-radius: var(--r-sm); font-family: inherit; font-size: 14px;
  cursor: pointer; transition: all .15s ease; border: 1px solid;
}
.mode-full { background: rgba(10,150,136,0.08); color: var(--teal-dk); border-color: rgba(10,150,136,0.25); }
.mode-full:hover:not(:disabled) { background: rgba(10,150,136,0.14); }
.mode-demo { background: rgba(235,195,60,0.12); color: #7a6020; border-color: rgba(200,160,35,0.3); }
.mode-demo:hover:not(:disabled) { background: rgba(235,195,60,0.2); }
.mode-name { font-weight: 600; }
.mode-switch { font-size: 12px; opacity: .8; white-space: nowrap; }
.mode-hint { text-align: center; }

/* Actions */
.actions { display: flex; flex-direction: column; gap: 10px; }
.abort-button { background: linear-gradient(135deg, #c0502a 0%, #a8411f 100%); box-shadow: 0 2px 14px rgba(192,80,42,0.3), inset 0 1px 0 rgba(255,255,255,0.14); }
.abort-button:hover { background: linear-gradient(135deg, #cf5a32 0%, #b24822 100%); box-shadow: 0 5px 20px rgba(192,80,42,0.36), inset 0 1px 0 rgba(255,255,255,0.14); }
.abort-copy { display: flex; flex-direction: column; align-items: flex-start; min-width: 0; text-align: left; }
.abort-title { font-weight: 600; }
.abort-message { font-size: 12px; font-weight: 400; opacity: .85; }
.spinner { width: 16px; height: 16px; flex-shrink: 0; border-radius: 50%; border: 2px solid rgba(255,255,255,0.35); border-top-color: #fff; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.progress-area { margin-top: 0; }
.secondary-actions { display: flex; gap: 8px; }
.secondary-actions .outline-button { flex: 1; }
.status-message { margin: 12px 0 0; font-size: 13px; color: var(--muted); text-align: center; }
</style>
