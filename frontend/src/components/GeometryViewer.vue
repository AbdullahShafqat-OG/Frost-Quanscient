<script setup lang="ts">
/** Front view: section across the pipe axis (A–A) */
import { computed, useId } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import { usePipeGeometry } from '@/composables/usePipeGeometry'
import SectionPatterns from '@/components/SectionPatterns.vue'
import MaterialLegend from '@/components/MaterialLegend.vue'
import { LAYER_STYLES, OUTLINE_COLOR, sectionPatternId, type LayerKey } from '@/visuals/materialStyles'

const store = useAnalysisStore()
const { radii, displayParams, iceFraction, wallLayer, insulationLayer } = usePipeGeometry()
const prefix = `front-${useId()}`

const CX = 150
const CY = 140
const R_MAX = 105 // px for the outermost radius

const px = computed(() => {
  const r = radii.value
  return { liquid: r.liquid * R_MAX, water: r.water * R_MAX, wall: r.wall * R_MAX, outer: r.outer * R_MAX }
})

const layers = computed<LayerKey[]>(() => [wallLayer.value, ...(insulationLayer.value ? [insulationLayer.value] : []), 'water', 'ice'])
const fill = (layer: LayerKey) => `url(#${sectionPatternId(prefix, layer)})`

// Surroundings backdrop per location
const BACKDROP = {
  outdoors: { fill: '#F1F5F9', label: 'Outside air' },
  indoors: { fill: '#FEF3C7', label: 'Wall cavity / unheated space' },
  underground: { fill: '#D6C3A5', label: 'Soil, 0.45 m deep' },
} as const
const backdrop = computed(() => BACKDROP[displayParams.value.location])

const description = computed(() => {
  const p = displayParams.value
  const ins = insulationLayer.value
    ? `, wrapped in ${p.insulation_thickness_mm} mm of ${LAYER_STYLES[insulationLayer.value].label.toLowerCase()}`
    : ', uninsulated'
  const ice = store.hasResults ? ` About ${Math.round(iceFraction.value * 100)}% of the water is ice at the end of the cold snap.` : ''
  return `Cross-section of a ${p.inner_diameter_mm} mm ${LAYER_STYLES[wallLayer.value].label} pipe with a ${p.wall_thickness_mm} mm wall${ins}.${ice}`
})
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-base font-semibold text-grey-900">Pipe cross-section <span class="text-grey-500 font-normal">(front)</span></h2>
      <span v-if="!radii.toScale" class="text-xs text-grey-600">not to scale</span>
    </div>

    <svg viewBox="0 0 300 290" class="flex-1 w-full min-h-0" role="img" :aria-label="description">
      <defs>
        <SectionPatterns :prefix="prefix" :layers="layers" />
      </defs>

      <!-- Surroundings backdrop — just wind arrows, no filled rect -->
      <g v-if="displayParams.location === 'outdoors'" stroke="#64748B" stroke-width="1.5" fill="#64748B">
        <g v-for="i in 3" :key="i" :transform="`translate(8, ${CY - 40 + (i - 1) * 40})`">
          <line x1="0" y1="0" x2="22" y2="0" />
          <path d="M22 -3 L28 0 L22 3 z" />
        </g>
      </g>
      <text x="8" y="16" font-size="10" fill="#334155">{{ backdrop.label }}</text>
      <text x="8" y="280" font-size="10" fill="#334155">Outside {{ displayParams.outside_temp_c }}°C</text>
      <text x="292" y="280" font-size="10" fill="#334155" text-anchor="end">Section A–A</text>

      <g :stroke="OUTLINE_COLOR" stroke-width="1">
        <!-- Insulation -->
        <circle v-if="insulationLayer" :cx="CX" :cy="CY" :r="px.outer" :fill="fill(insulationLayer)" />
        <!-- Wall -->
        <circle :cx="CX" :cy="CY" :r="px.wall" :fill="fill(wallLayer)" />
        <!-- Ice grows inward from the wall; the liquid core is what is left -->
        <circle :cx="CX" :cy="CY" :r="px.water" :fill="fill('ice')" />
        <circle v-if="px.liquid > 0.5" :cx="CX" :cy="CY" :r="px.liquid" :fill="fill('water')" stroke-width="0.75" />
      </g>

      <!-- Centre marks and inner diameter -->
      <g :stroke="OUTLINE_COLOR" stroke-width="0.75" stroke-dasharray="8 2 2 2">
        <line :x1="CX - px.outer - 8" :y1="CY" :x2="CX + px.outer + 8" :y2="CY" />
        <line :x1="CX" :y1="CY - px.outer - 8" :x2="CX" :y2="CY + px.outer + 8" />
      </g>
      <text
        :x="CX + 4"
        :y="CY - 4"
        font-size="10"
        font-weight="600"
        fill="#FFFFFF"
        stroke="#0B3B66"
        stroke-width="2.5"
        paint-order="stroke"
      >⌀{{ displayParams.inner_diameter_mm }}</text>
    </svg>

    <MaterialLegend class="mt-2" />
  </div>
</template>
