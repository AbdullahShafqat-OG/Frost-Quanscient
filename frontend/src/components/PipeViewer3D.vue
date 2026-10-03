<script setup lang="ts">
/**
 * Interactive 3D pipe (three.js). Drag to orbit, scroll to zoom; when the
 * view has keyboard focus, arrow keys orbit, +/- zoom and Home resets.
 */
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { usePreferredReducedMotion, useResizeObserver } from '@vueuse/core'
import { useAnalysisStore } from '@/stores/analysisStore'
import { usePipeGeometry } from '@/composables/usePipeGeometry'
import { LAYER_STYLES } from '@/visuals/materialStyles'
import { PipeScene } from '@/visuals/pipeScene'

const store = useAnalysisStore()
const { radii, displayParams, iceFraction, wallLayer, insulationLayer } = usePipeGeometry()
const reducedMotion = usePreferredReducedMotion()

const container = ref<HTMLDivElement>()
const canvas = ref<HTMLCanvasElement>()
const cutaway = ref(true)
const unsupported = ref(false)
const hintId = `pipe3d-hint-${useId()}`

// three.js objects stay out of Vue's reactivity
let scene: PipeScene | null = null

const ORBIT_STEP = Math.PI / 24
const ZOOM_STEP = 0.9

const description = computed(() => {
  const p = displayParams.value
  const ins = insulationLayer.value
    ? `${p.insulation_thickness_mm} mm ${LAYER_STYLES[insulationLayer.value].label.toLowerCase()} insulation stepped back to show the pipe, `
    : 'no insulation, '
  const ice = store.hasResults ? ` ${Math.round(iceFraction.value * 100)}% of the water is ice.` : ''
  const cut = cutaway.value ? ' A quarter is cut away to show every layer in section.' : ''
  return `3D model of a ${p.inner_diameter_mm} mm ${LAYER_STYLES[wallLayer.value].label} pipe: ${ins}${p.wall_thickness_mm} mm wall, water core.${ice}${cut}`
})

let modelInitialized = false

function updateModel() {
  const r = radii.value
  scene?.setModel({
    radii: r,
    wall: wallLayer.value,
    insulation: insulationLayer.value,
    cutaway: cutaway.value,
  })
  // On first mount reset the camera to a good starting position;
  // after that only update distance constraints so the user's rotation is kept.
  scene?.fitCamera(r.outer, !modelInitialized)
  modelInitialized = true
}

onMounted(() => {
  if (!canvas.value) return
  try {
    scene = new PipeScene(canvas.value, { reducedMotion: reducedMotion.value === 'reduce' })
  } catch {
    unsupported.value = true
    return
  }
  const { clientWidth, clientHeight } = container.value!
  scene.setSize(clientWidth, clientHeight)
  updateModel()
})

watch([radii, wallLayer, insulationLayer, cutaway], updateModel)

useResizeObserver(container, ([entry]) => {
  scene?.setSize(entry.contentRect.width, entry.contentRect.height)
})

onBeforeUnmount(() => {
  scene?.dispose()
  scene = null
})

function onKeydown(event: KeyboardEvent) {
  if (!scene) return
  const actions: Record<string, () => void> = {
    ArrowLeft: () => scene!.orbit(-ORBIT_STEP, 0),
    ArrowRight: () => scene!.orbit(ORBIT_STEP, 0),
    ArrowUp: () => scene!.orbit(0, -ORBIT_STEP),
    ArrowDown: () => scene!.orbit(0, ORBIT_STEP),
    '+': () => scene!.zoom(ZOOM_STEP),
    '=': () => scene!.zoom(ZOOM_STEP),
    '-': () => scene!.zoom(1 / ZOOM_STEP),
    Home: () => scene!.fitCamera(radii.value.outer, true),
  }
  const action = actions[event.key]
  if (action) {
    event.preventDefault()
    action()
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between gap-2 mb-2">
      <h3 class="text-base font-semibold text-grey-900">3D model</h3>
      <div class="flex items-center gap-2">
        <span v-if="!radii.toScale" class="text-xs text-grey-600">not to scale</span>
        <button
          type="button"
          class="px-2.5 py-1 rounded-md text-xs font-medium border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500"
          :class="cutaway ? 'bg-primary-50 text-primary-700 border-primary-300' : 'bg-white text-grey-700 border-grey-300 hover:bg-grey-50'"
          :aria-pressed="cutaway"
          :disabled="unsupported"
          @click="cutaway = !cutaway"
        >
          Cutaway
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded-md text-xs font-medium border bg-white text-grey-700 border-grey-300 hover:bg-grey-50 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500"
          :disabled="unsupported"
          @click="scene?.fitCamera(radii.outer, true)"
        >
          Reset view
        </button>
      </div>
    </div>

    <div
      ref="container"
      class="relative flex-1 min-h-0 rounded-lg overflow-hidden cursor-grab active:cursor-grabbing focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500"
      :tabindex="unsupported ? -1 : 0"
      role="img"
      :aria-label="description"
      :aria-describedby="hintId"
      @keydown="onKeydown"
    >
      <canvas ref="canvas" class="block w-full h-full touch-none" aria-hidden="true" />
      <p v-if="unsupported" class="absolute inset-0 flex items-center justify-center p-6 text-sm text-grey-600 text-center">
        3D view unavailable: this browser could not start WebGL. The 2D sections show the same layers.
      </p>
    </div>

    <p :id="hintId" class="mt-1.5 text-xs text-grey-600">
      Drag to rotate, scroll or pinch to zoom. With the view focused: arrow keys rotate, + / − zoom, Home resets.
    </p>
  </div>
</template>
