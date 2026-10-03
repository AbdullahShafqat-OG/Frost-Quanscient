<script setup lang="ts">
/** Side view: section along the pipe axis (B–B), with break lines at both ends */
import { computed, useId } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import { usePipeGeometry } from '@/composables/usePipeGeometry'
import SectionPatterns from '@/components/SectionPatterns.vue'
import { LAYER_STYLES, OUTLINE_COLOR, sectionPatternId, type LayerKey } from '@/visuals/materialStyles'

const store = useAnalysisStore()
const { dims, radii, iceFraction, wallLayer, insulationLayer } = usePipeGeometry()
const uid = `side-${useId()}`

const CY = 108
const R_MAX = 78 // px for the outermost radius
const X0 = 18
const X1 = 282
const WAVE = 6 // amplitude of the break lines

const px = computed(() => {
  const r = radii.value
  return { liquid: r.liquid * R_MAX, water: r.water * R_MAX, wall: r.wall * R_MAX, outer: R_MAX }
})

interface Band {
  layer: LayerKey
  y: number
  h: number
}

/** Horizontal bands from top to bottom: insulation, wall, ice, water, ice, wall, insulation */
const bands = computed<Band[]>(() => {
  const r = px.value
  const pairs: [LayerKey, number, number][] = [] // layer, inner radius, outer radius
  if (insulationLayer.value) pairs.push([insulationLayer.value, r.wall, r.outer])
  pairs.push([wallLayer.value, r.water, r.wall])
  pairs.push(['ice', r.liquid, r.water])
  const list: Band[] = []
  for (const [layer, rIn, rOut] of pairs) {
    if (rOut - rIn < 0.3) continue
    list.push({ layer, y: CY - rOut, h: rOut - rIn })
    list.push({ layer, y: CY + rIn, h: rOut - rIn })
  }
  if (r.liquid > 0.3) list.push({ layer: 'water', y: CY - r.liquid, h: 2 * r.liquid })
  return list
})

const layers = computed<LayerKey[]>(() => [wallLayer.value, ...(insulationLayer.value ? [insulationLayer.value] : []), 'water', 'ice'])
const fill = (layer: LayerKey) => `url(#${sectionPatternId(uid, layer)})`

/** Wavy vertical break line from top to bottom at x */
function breakLine(x: number, top: number, bottom: number, reverse = false): string {
  const steps = 4
  const dy = (bottom - top) / steps
  let d = ''
  for (let i = 0; i < steps; i++) {
    const k = reverse ? steps - 1 - i : i
    const y0 = top + k * dy
    const y1 = y0 + dy
    const [from, to] = reverse ? [y1, y0] : [y0, y1]
    const bulge = (k % 2 ? -WAVE : WAVE) * (reverse ? -1 : 1)
    d += `${i === 0 ? `L${x},${from} ` : ''}Q${x + bulge},${(from + to) / 2} ${x},${to} `
  }
  return d
}

/** Outline of the cut segment, also used as the clip path */
const outline = computed(() => {
  const top = CY - px.value.outer
  const bottom = CY + px.value.outer
  return `M${X0},${top} L${X1},${top} ${breakLine(X1, top, bottom)}L${X0},${bottom} ${breakLine(X0, top, bottom, true)}Z`
})

const outerDiameterMm = computed(() => +(2 * dims.value.rOut).toFixed(1))

const description = computed(() => {
  const p = store.params
  const ins = insulationLayer.value
    ? `${p.insulation_thickness_mm} mm ${LAYER_STYLES[insulationLayer.value].label.toLowerCase()} on top and bottom, `
    : ''
  const ice = store.hasResults ? `, ${Math.round(iceFraction.value * 100)}% frozen from the wall inward` : ''
  return `Lengthwise section of the pipe: ${ins}${p.wall_thickness_mm} mm ${LAYER_STYLES[wallLayer.value].label} wall, ${p.inner_diameter_mm} mm of water${ice}. Outer diameter ${outerDiameterMm.value} mm.`
})
</script>

<template>
  <div class="flex flex-col">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-base font-semibold text-grey-900">Lengthwise section <span class="text-grey-500 font-normal">(side)</span></h3>
      <span v-if="!radii.toScale" class="text-xs text-grey-600">not to scale</span>
    </div>

    <svg viewBox="0 0 300 220" class="w-full" role="img" :aria-label="description">
      <defs>
        <SectionPatterns :prefix="uid" :layers="layers" />
        <clipPath :id="`${uid}-clip`">
          <path :d="outline" />
        </clipPath>
        <marker :id="`${uid}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" :fill="OUTLINE_COLOR" />
        </marker>
      </defs>

      <text x="292" y="212" font-size="10" fill="#334155" text-anchor="end">Section B–B</text>

      <!-- Layers -->
      <g :clip-path="`url(#${uid}-clip)`" :stroke="OUTLINE_COLOR" stroke-width="0.75">
        <rect v-for="(b, i) in bands" :key="i" :x="X0 - WAVE - 2" :y="b.y" :width="X1 - X0 + 2 * WAVE + 4" :height="b.h" :fill="fill(b.layer)" />
      </g>
      <path :d="outline" fill="none" :stroke="OUTLINE_COLOR" stroke-width="1.25" />

      <!-- Centre line -->
      <line :x1="X0 - 12" :y1="CY" :x2="X1 + 12" :y2="CY" :stroke="OUTLINE_COLOR" stroke-width="0.75" stroke-dasharray="10 3 2 3" />

      <!-- Drip flow direction -->
      <g v-if="store.params.drip_flow_lpm > 0 && px.liquid > 12">
        <line x1="190" :y1="CY + px.liquid / 2" x2="250" :y2="CY + px.liquid / 2" stroke="#FFFFFF" stroke-width="2" :marker-end="`url(#${uid}-arrow)`" />
        <text x="220" :y="CY + px.liquid / 2 - 4" font-size="9" fill="#FFFFFF" text-anchor="middle" stroke="#0B3B66" stroke-width="2.5" paint-order="stroke">drip</text>
      </g>

      <!-- Inner diameter -->
      <g font-size="10" font-weight="600">
        <line
          x1="70"
          :y1="CY - px.water"
          x2="70"
          :y2="CY + px.water"
          stroke="#FFFFFF"
          stroke-width="1.25"
          :marker-start="`url(#${uid}-arrow)`"
          :marker-end="`url(#${uid}-arrow)`"
        />
        <text x="76" :y="CY - 4" fill="#FFFFFF" stroke="#0B3B66" stroke-width="2.5" paint-order="stroke">⌀{{ store.params.inner_diameter_mm }}</text>
      </g>

      <!-- Outer diameter -->
      <g font-size="10" fill="#334155" :stroke="OUTLINE_COLOR" stroke-width="0.75">
        <line x1="150" :y1="CY - px.outer - 12" x2="150" :y2="CY - px.outer - 2" />
        <text x="154" :y="CY - px.outer - 6" stroke="none">OD {{ outerDiameterMm }} mm</text>
      </g>
    </svg>
  </div>
</template>
