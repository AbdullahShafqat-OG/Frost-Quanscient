/**
 * Pipe geometry shared by the cross-section, side-section and 3D views.
 *
 * Normalisation strategy — each layer is fully independent:
 *   wallBand  = wall_thickness_mm  × SCALE_PER_MM  (never changes with bore size)
 *   insBand   = insulation_thickness_mm × SCALE_PER_MM  (never changes with bore size)
 *   water     = (inner_diameter_mm / 2) × SCALE_PER_MM, capped at 1 − wallBand − insBand
 *
 *   This means:
 *     – changing inner_diameter grows/shrinks the bore only ✓
 *     – changing wall_thickness grows/shrinks the wall band only ✓
 *     – the two never influence each other ✓
 *
 *   Edge case: if wall + insulation together would leave less than MIN_WATER_FRACTION
 *   for the bore, the annulus bands are scaled down proportionally as a group.
 *
 * Geometry always reflects live slider values. Ice fraction is separately
 * gated by store.series (empty when results are stale), so the two stay consistent.
 */

import { computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysisStore'
import type { PipeParams } from '@/types'
import type { LayerKey } from '@/visuals/materialStyles'

/**
 * 1 mm → 0.05 canvas-fraction.
 * Default pipe (rIn=7.5 mm, wall=1 mm): bore = 0.375, wall band = 0.05.
 * At max wall (10 mm): bore still = 0.375, wall band = 0.5.
 */
const SCALE_PER_MM = 0.05

/** Below this bore radius (fraction) the drawing switches to "not to scale" */
const MIN_WATER_FRACTION = 0.07
/** Bore radius used in "not to scale" mode */
const FALLBACK_WATER_FRACTION = 0.29

export interface PipeRadii {
  liquid: number
  water: number
  wall: number
  outer: number
  toScale: boolean
}

export function usePipeGeometry() {
  const store = useAnalysisStore()

  /** Always use live params so sliders update the models in real time. */
  const displayParams = computed<PipeParams>(() => store.params)

  const dims = computed(() => {
    const p = displayParams.value
    const rIn   = p.inner_diameter_mm / 2
    const rWall = rIn + p.wall_thickness_mm
    const hasIns = p.insulation !== 'none'
    const rOut  = hasIns ? rWall + p.insulation_thickness_mm : rWall
    return { rIn, rWall, rOut, hasIns }
  })

  const iceFraction = computed(() => {
    const series = store.series
    if (!series.length) return 0
    const target = displayParams.value.cold_snap_hours
    const point = series.reduce((best, p) =>
      Math.abs(p.time_hours - target) < Math.abs(best.time_hours - target) ? p : best
    )
    return Math.min(1, Math.max(0, point.ice_fraction))
  })

  const radii = computed<PipeRadii>(() => {
    const { rIn, hasIns } = dims.value
    const p = displayParams.value

    // Each band is sized solely by its own thickness — bore and wall never affect each other.
    const wallBand = p.wall_thickness_mm * SCALE_PER_MM
    const insBand  = hasIns ? p.insulation_thickness_mm * SCALE_PER_MM : 0
    const totalAnnulus = wallBand + insBand

    // Edge case: annulus alone too wide → scale it down as a group so the bore
    // still gets at least MIN_WATER_FRACTION of canvas space.
    let scaledWallBand = wallBand
    let scaledInsBand  = insBand
    if (totalAnnulus > 1 - MIN_WATER_FRACTION) {
      const fit = (1 - MIN_WATER_FRACTION) / totalAnnulus
      scaledWallBand *= fit
      scaledInsBand  *= fit
    }

    // Bore grows with inner diameter, capped so total stays ≤ 1.
    const maxBore = 1 - scaledWallBand - scaledInsBand
    let water = Math.min(rIn * SCALE_PER_MM, maxBore)

    let wall  = water + scaledWallBand
    let outer = wall  + scaledInsBand

    const toScale = rIn * SCALE_PER_MM >= MIN_WATER_FRACTION
    if (!toScale) {
      water = FALLBACK_WATER_FRACTION
      wall  = water + scaledWallBand
      outer = wall  + scaledInsBand
    }

    const liquid = water * Math.sqrt(1 - iceFraction.value)
    return { liquid, water, wall, outer, toScale }
  })

  const wallLayer     = computed<LayerKey>(() => displayParams.value.pipe_material)
  const insulationLayer = computed<LayerKey | null>(() =>
    displayParams.value.insulation === 'none' ? null : displayParams.value.insulation
  )

  return { dims, displayParams, radii, iceFraction, wallLayer, insulationLayer }
}
