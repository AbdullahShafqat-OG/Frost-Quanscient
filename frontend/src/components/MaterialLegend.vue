<script setup lang="ts">
/**
 * Legend for the pipe views: one hatched swatch per layer, with the layer
 * name and its section pattern spelled out for screen readers.
 */
import { computed, useId } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import { usePipeGeometry } from '@/composables/usePipeGeometry'
import SectionPatterns from '@/components/SectionPatterns.vue'
import { LAYER_STYLES, OUTLINE_COLOR, sectionPatternId, type LayerKey } from '@/visuals/materialStyles'

const store = useAnalysisStore()
const { iceFraction, wallLayer, insulationLayer } = usePipeGeometry()
const prefix = `legend-${useId()}`

interface Entry {
  layer: LayerKey
  text: string
}

const entries = computed<Entry[]>(() => {
  const p = store.params
  const list: Entry[] = [{ layer: wallLayer.value, text: `${LAYER_STYLES[wallLayer.value].label} wall, ${p.wall_thickness_mm} mm` }]
  if (insulationLayer.value) {
    list.push({ layer: insulationLayer.value, text: `${LAYER_STYLES[insulationLayer.value].label}, ${p.insulation_thickness_mm} mm` })
  }
  list.push({ layer: 'water', text: 'Water' })
  list.push({
    layer: 'ice',
    text: store.hasResults ? `Ice — ${Math.round(iceFraction.value * 100)}% at end of cold snap` : 'Ice',
  })
  return list
})
</script>

<template>
  <ul class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-grey-700" aria-label="Legend">
    <li v-for="e in entries" :key="e.layer" class="flex items-center gap-1.5">
      <svg width="16" height="16" viewBox="0 0 16 16" class="flex-shrink-0" aria-hidden="true">
        <defs><SectionPatterns :prefix="prefix" :layers="[e.layer]" :scale="0.5" /></defs>
        <rect x="0.5" y="0.5" width="15" height="15" rx="2" :fill="`url(#${sectionPatternId(prefix, e.layer)})`" :stroke="OUTLINE_COLOR" />
      </svg>
      <span>
        {{ e.text }}
        <span class="sr-only">(shown as {{ LAYER_STYLES[e.layer].hatchName }})</span>
      </span>
    </li>
  </ul>
</template>
