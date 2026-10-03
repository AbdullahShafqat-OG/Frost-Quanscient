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

const optionClass = (selected: boolean) => [
  'px-2 py-2 rounded-lg text-sm font-medium transition-all border',
  selected
    ? 'bg-primary-50 text-primary-700 border-primary-300'
    : 'bg-white text-grey-600 border-grey-200 hover:bg-grey-50',
]

function onSlider(key: NumericKey, event: Event) {
  store.setParam(key, Number((event.target as HTMLInputElement).value))
}

function toggleMode() {
  store.setDemoMode(!store.useDemoMode)
}
</script>

<template>
  <div class="card p-6 space-y-5">
    <!-- ================= PIPE ================= -->
    <section class="space-y-4">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-grey-500">Pipe</h2>

      <div v-for="s in pipeSliders" :key="s.key" class="space-y-1.5">
        <div class="flex justify-between">
          <label class="text-sm font-medium text-grey-700">{{ s.label }}</label>
          <span class="text-sm text-primary-600 font-mono font-medium">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
      </div>

      <div class="space-y-2">
        <label class="text-sm font-medium text-grey-700">Pipe material</label>
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="[value, spec] in materialOptions"
            :key="value"
            @click="store.setParam('pipe_material', value)"
            :class="optionClass(store.params.pipe_material === value)"
          >
            {{ spec.label }}
          </button>
        </div>
      </div>

      <div class="space-y-2">
        <label class="text-sm font-medium text-grey-700">Insulation material</label>
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="[value, spec] in insulationOptions"
            :key="value"
            @click="store.setParam('insulation', value)"
            :class="optionClass(store.params.insulation === value)"
          >
            {{ spec.label }}
          </button>
        </div>
        <div class="space-y-1.5 pt-1" :class="store.params.insulation === 'none' ? 'opacity-50' : ''">
          <div class="flex justify-between">
            <label class="text-sm font-medium text-grey-700">Insulation thickness</label>
            <span class="text-sm text-primary-600 font-mono font-medium">
              {{ store.params.insulation === 'none' ? '—' : `${store.params.insulation_thickness_mm} mm` }}
            </span>
          </div>
          <input
            type="range"
            :value="store.params.insulation_thickness_mm"
            @input="onSlider('insulation_thickness_mm', $event)"
            :disabled="store.params.insulation === 'none'"
            min="5"
            max="50"
            step="1"
            class="disabled:cursor-not-allowed"
          />
        </div>
      </div>
    </section>

    <!-- ================= EXTERNAL CONDITIONS ================= -->
    <section class="pt-4 border-t border-grey-200 space-y-4">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-grey-500">External conditions</h2>

      <div class="space-y-2">
        <label class="text-sm font-medium text-grey-700">Where the pipe is</label>
        <div class="grid grid-cols-3 gap-2">
          <!-- Fixed in this version: shown for context, not selectable -->
          <button
            v-for="[value, spec] in locationOptions"
            :key="value"
            disabled
            :aria-pressed="value === FIXED_LOCATION"
            :class="[...optionClass(value === FIXED_LOCATION), 'cursor-not-allowed', value === FIXED_LOCATION ? '' : 'opacity-50']"
          >
            {{ spec.label }}
          </button>
        </div>
        <p class="text-xs text-grey-400">Fixed to {{ LOCATIONS[FIXED_LOCATION].label.toLowerCase() }} in this version.</p>
        <p class="text-xs text-grey-500 bg-grey-50 border border-grey-200 rounded-lg p-2">
          <span class="font-medium">Assumed:</span> {{ LOCATIONS[store.params.location].summary }}
        </p>
      </div>

      <div v-for="s in conditionSliders" :key="s.key" class="space-y-1.5">
        <div class="flex justify-between">
          <label class="text-sm font-medium text-grey-700">{{ s.label }}</label>
          <span class="text-sm text-primary-600 font-mono font-medium">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
      </div>
      <p class="text-xs text-grey-400">
        External heat transfer is estimated from the location and outside temperature.
      </p>
    </section>

    <!-- ================= WATER ================= -->
    <section class="pt-4 border-t border-grey-200 space-y-4">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-grey-500">Water</h2>

      <div v-for="s in waterSliders" :key="s.key" class="space-y-1.5">
        <div class="flex justify-between">
          <label class="text-sm font-medium text-grey-700">{{ s.label }}</label>
          <span class="text-sm text-primary-600 font-mono font-medium">{{ store.params[s.key] }} {{ s.unit }}</span>
        </div>
        <input type="range" :value="store.params[s.key]" @input="onSlider(s.key, $event)" :min="s.min" :max="s.max" :step="s.step" />
        <p v-if="s.hint" class="text-xs text-grey-400">{{ s.hint() }}</p>
      </div>
    </section>

    <!-- Analysis Mode Toggle -->
    <div class="pt-3 border-t border-grey-200">
      <button
        @click="toggleMode"
        :disabled="store.isRunning"
        class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all border disabled:opacity-50"
        :class="store.useDemoMode
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : 'bg-green-50 text-green-700 border-green-200'"
      >
        <span class="font-medium">{{ store.useDemoMode ? 'Demo (local estimate)' : 'Full simulation (Allsolve)' }}</span>
        <span class="text-xs opacity-80">click to switch</span>
      </button>
      <p class="mt-1.5 text-xs text-grey-400 text-center">
        {{ store.useDemoMode
          ? 'Lumped heat-loss model with a latent-heat plateau (instant)'
          : '3D FEM with freezing, on the Quanscient Allsolve cloud (requires API key)' }}
      </p>
    </div>

    <!-- Action Buttons -->
    <div class="pt-1 space-y-3">
      <button
        v-if="!store.isRunning"
        @click="store.startAnalysis()"
        class="w-full btn-primary flex items-center justify-center gap-2 py-3"
      >
        Analyse freeze risk
      </button>

      <button
        v-if="store.isRunning"
        @click="store.abortAnalysis()"
        class="w-full btn-danger flex items-center justify-center gap-2 py-3"
      >
        <svg class="animate-spin w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
        <div class="flex flex-col items-center">
          <span class="font-semibold">{{ Math.round(store.progress) }}% — Click to Abort</span>
          <span class="text-xs opacity-80">{{ store.message }}</span>
        </div>
      </button>

      <div class="flex gap-2">
        <button
          v-if="store.hasResults || store.status === 'failed'"
          @click="store.reset()"
          class="flex-1 btn-secondary py-2.5"
        >
          Clear results
        </button>
        <button v-if="!store.isRunning" @click="store.resetParams()" class="flex-1 btn-secondary py-2.5">
          Default inputs
        </button>
      </div>
    </div>

    <!-- Status Message -->
    <div v-if="store.message && !store.isRunning" class="text-xs text-center" :class="store.status === 'failed' ? 'text-red-500' : 'text-grey-500'">
      {{ store.message }}
    </div>
  </div>
</template>
