<script setup lang="ts">
/**
 * SVG <pattern> definitions for section lining. Render inside an <svg>'s
 * <defs>; reference with fill="url(#<sectionPatternId(prefix, layer)>)".
 */
import {
  LAYER_STYLES,
  HATCH_TILE,
  HATCH_STROKE_WIDTH,
  sectionPatternId,
  type LayerKey,
} from '@/visuals/materialStyles'

const props = withDefaults(
  defineProps<{
    /** Unique per <svg>, keeps ids from clashing across the page */
    prefix: string
    layers: LayerKey[]
    /** Pattern tile scale in the SVG's user units */
    scale?: number
  }>(),
  { scale: 0.6 }
)
</script>

<template>
  <pattern
    v-for="layer in props.layers"
    :id="sectionPatternId(props.prefix, layer)"
    :key="layer"
    :width="HATCH_TILE"
    :height="HATCH_TILE"
    patternUnits="userSpaceOnUse"
    :patternTransform="`scale(${props.scale})`"
  >
    <rect :width="HATCH_TILE" :height="HATCH_TILE" :fill="LAYER_STYLES[layer].fill" />
    <path
      v-for="(stroke, i) in LAYER_STYLES[layer].hatch"
      :key="i"
      :d="stroke.d"
      fill="none"
      :stroke="LAYER_STYLES[layer].ink"
      :stroke-width="stroke.width ?? HATCH_STROKE_WIDTH"
      :stroke-dasharray="stroke.dash?.join(' ')"
      stroke-linecap="butt"
    />
  </pattern>
</template>
