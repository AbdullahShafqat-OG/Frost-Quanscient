<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import { PIPE_MATERIALS, INSULATION_TYPES } from '@/types'

const store = useAnalysisStore()

const CX = 150
const CY = 140
const R_MAX = 105 // px for the outermost radius
const R_WATER_MIN = 14 // below this the drawing switches to "not to scale"

const dims = computed(() => {
  const p = store.params
  const rIn = p.inner_diameter_mm / 2
  const rWall = rIn + p.wall_thickness_mm
  const hasIns = p.insulation !== 'none'
  const rOut = hasIns ? rWall + p.insulation_thickness_mm : rWall
  return { rIn, rWall, rOut, hasIns }
})

// Radii in px
const radii = computed(() => {
  const { rIn, rWall, rOut } = dims.value
  const scale = R_MAX / rOut
  if (rIn * scale >= R_WATER_MIN) {
    return { water: rIn * scale, wall: rWall * scale, outer: R_MAX, toScale: true }
  }
  // Thick insulation: keep the pipe readable
  const water = 30
  const wall = water + Math.max(4, (water * (rWall - rIn)) / rIn)
  return { water, wall, outer: R_MAX, toScale: false }
})

// Ice state at the end of the cold snap, if results are available
const iceFraction = computed(() => {
  const series = store.series
  if (!series.length) return 0
  const target = store.params.cold_snap_hours
  const point = series.reduce((best, p) =>
    Math.abs(p.time_hours - target) < Math.abs(best.time_hours - target) ? p : best
  )
  return point.ice_fraction
})

// Ice grows inward from the wall: liquid core radius
const liquidRadius = computed(() => radii.value.water * Math.sqrt(1 - iceFraction.value))

const wallColor = computed(() => PIPE_MATERIALS[store.params.pipe_material].color)
const insulationColor = computed(() => INSULATION_TYPES[store.params.insulation].color)

// Surroundings backdrop per location
const BACKDROP = {
  outdoors: { fill: '#F1F5F9', label: 'Outside air' },
  indoors: { fill: '#FEF3C7', label: 'Wall cavity / unheated space' },
  underground: { fill: '#D6C3A5', label: 'Soil, 0.45 m deep' },
} as const
const backdrop = computed(() => BACKDROP[store.params.location])
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-base font-semibold text-grey-900">Pipe cross-section</h2>
      <span v-if="!radii.toScale" class="text-xs text-grey-400">not to scale</span>
    </div>

    <svg viewBox="0 0 300 290" class="flex-1 w-full">
      <defs>
        <pattern id="ins-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" :fill="insulationColor" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="white" stroke-opacity="0.25" stroke-width="2" />
        </pattern>
      </defs>

      <!-- Surroundings -->
      <rect x="0" y="0" width="300" height="290" rx="8" :fill="backdrop.fill" />
      <g v-if="store.params.location === 'outdoors'" stroke="#94A3B8" stroke-width="1.5" fill="#94A3B8">
        <g v-for="i in 3" :key="i" :transform="`translate(8, ${CY - 40 + (i - 1) * 40})`">
          <line x1="0" y1="0" x2="22" y2="0" />
          <path d="M22 -3 L28 0 L22 3 z" />
        </g>
      </g>
      <text x="8" y="16" font-size="10" fill="#475569">{{ backdrop.label }}</text>
      <text x="8" y="280" font-size="10" fill="#475569">Outside {{ store.params.outside_temp_c }}°C</text>

      <!-- Insulation -->
      <circle v-if="dims.hasIns" :cx="CX" :cy="CY" :r="radii.outer" fill="url(#ins-hatch)" stroke="#374151" stroke-width="1" />
      <!-- Wall -->
      <circle :cx="CX" :cy="CY" :r="radii.wall" :fill="wallColor" stroke="#374151" stroke-width="1" />
      <!-- Water / ice -->
      <circle :cx="CX" :cy="CY" :r="radii.water" fill="#E0F2FE" stroke="#0369A1" stroke-width="0.75" />
      <circle :cx="CX" :cy="CY" :r="liquidRadius" fill="#38BDF8" />

      <!-- Dimension labels -->
      <g font-size="10" fill="#374151">
        <line :x1="CX - radii.water" :y1="CY" :x2="CX + radii.water" :y2="CY" stroke="#0C4A6E" stroke-dasharray="2 2" />
        <text :x="CX" :y="CY - 4" text-anchor="middle" fill="#0C4A6E">⌀{{ store.params.inner_diameter_mm }}</text>
      </g>
    </svg>

    <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-grey-600 mt-1">
      <div class="flex items-center gap-1.5">
        <span class="inline-block w-3 h-3 rounded-full border border-grey-400" :style="{ background: wallColor }" />
        {{ PIPE_MATERIALS[store.params.pipe_material].label }}, {{ store.params.wall_thickness_mm }} mm wall
      </div>
      <div class="flex items-center gap-1.5">
        <span class="inline-block w-3 h-3 rounded-full border border-grey-400" :style="{ background: dims.hasIns ? insulationColor : 'transparent' }" />
        {{ dims.hasIns ? `${INSULATION_TYPES[store.params.insulation].label}, ${store.params.insulation_thickness_mm} mm` : 'No insulation' }}
      </div>
      <div class="flex items-center gap-1.5">
        <span class="inline-block w-3 h-3 rounded-full bg-sky-400" /> Water
      </div>
      <div class="flex items-center gap-1.5">
        <span class="inline-block w-3 h-3 rounded-full bg-sky-100 border border-sky-700" />
        Ice<template v-if="store.hasResults"> — {{ Math.round(iceFraction * 100) }}% at end of cold snap</template>
      </div>
    </div>
  </div>
</template>
