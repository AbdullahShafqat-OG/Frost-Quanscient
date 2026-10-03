/**
 * Pipe geometry shared by the cross-section, side-section and 3D views.
 *
 * Radii are normalised so the outermost layer is 1. When the water core
 * would be too small to read (thick insulation on a thin pipe), the drawing
 * switches to "not to scale" and keeps the pipe legible instead.
 */

import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { LayerKey } from '@/visuals/materialStyles'

/** Below this water radius (fraction of the outer radius) the views stop being to scale */
const MIN_WATER_FRACTION = 0.13
/** Water radius used when not to scale */
const FALLBACK_WATER_FRACTION = 0.29
/** Minimum wall band when not to scale, so the wall stays visible */
const MIN_WALL_BAND = 0.04

export interface PipeRadii {
  /** Liquid core (shrinks as ice grows inward from the wall) */
  liquid: number
  /** Inner pipe radius = water/ice boundary with the wall */
  water: number
  /** Outer pipe wall radius */
  wall: number
  /** Outermost radius: insulation if present, otherwise the wall */
  outer: number
  toScale: boolean
}

export function usePipeGeometry() {
  const store = useAnalysisStore()

  /** Physical radii in mm */
  const dims = computed(() => {
    const p = store.params
    const rIn = p.inner_diameter_mm / 2
    const rWall = rIn + p.wall_thickness_mm
    const hasIns = p.insulation !== 'none'
    const rOut = hasIns ? rWall + p.insulation_thickness_mm : rWall
    return { rIn, rWall, rOut, hasIns }
  })

  /** Ice fraction at the end of the cold snap, 0 before a run */
  const iceFraction = computed(() => {
    const series = store.series
    if (!series.length) return 0
    const target = store.params.cold_snap_hours
    const point = series.reduce((best, p) =>
      Math.abs(p.time_hours - target) < Math.abs(best.time_hours - target) ? p : best
    )
    return Math.min(1, Math.max(0, point.ice_fraction))
  })

  const radii = computed<PipeRadii>(() => {
    const { rIn, rWall, rOut } = dims.value
    let water = rIn / rOut
    let wall = rWall / rOut
    const toScale = water >= MIN_WATER_FRACTION
    if (!toScale) {
      water = FALLBACK_WATER_FRACTION
      wall = Math.min(1, water + Math.max(MIN_WALL_BAND, (water * (rWall - rIn)) / rIn))
    }
    // Ice grows inward from the wall: the liquid core keeps the unfrozen area
    const liquid = water * Math.sqrt(1 - iceFraction.value)
    return { liquid, water, wall, outer: 1, toScale }
  })

  const wallLayer = computed<LayerKey>(() => store.params.pipe_material)
  const insulationLayer = computed<LayerKey | null>(() =>
    store.params.insulation === 'none' ? null : store.params.insulation
  )

  return { dims, radii, iceFraction, wallLayer, insulationLayer }
}
