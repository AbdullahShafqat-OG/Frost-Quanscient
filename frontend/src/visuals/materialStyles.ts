/**
 * Visual language for every layer of the pipe, shared by the 2D sections
 * (SVG patterns) and the 3D model (canvas textures + PBR materials).
 *
 * Accessibility: each layer has its own section-lining pattern, so layers
 * can be told apart without relying on colour. Fill/ink pairs keep at least
 * 3:1 contrast (WCAG 1.4.11), and neighbouring layers differ in lightness so
 * they stay distinct for colour-blind viewers and in greyscale.
 *
 * Patterns loosely follow engineering drawing conventions: 45° lining for
 * metals (dashed alternate lines for copper alloys), cross-hatch for
 * plastics, wavy batt / zigzag / cell symbols for insulation, and horizontal
 * dashes for liquid.
 */

import type { InsulationType, PipeMaterial } from '@/types'

export type LayerKey = PipeMaterial | Exclude<InsulationType, 'none'> | 'water' | 'ice'

/** Side length of one pattern tile, in tile units */
export const HATCH_TILE = 16

export interface HatchStroke {
  /** SVG path data in tile units; also fed to Path2D for canvas textures */
  d: string
  width?: number
  dash?: number[]
}

/** Exterior look of a layer in the 3D model */
export interface SurfaceStyle {
  metalness: number
  roughness: number
  clearcoat?: number
  /** Procedural detail baked into a texture: brushed metal or fibrous/cellular insulation */
  texture?: 'brushed' | 'fibrous' | 'cells'
}

export interface LayerStyle {
  label: string
  /** Section fill and the 3D surface colour */
  fill: string
  /** Hatch line colour, high contrast against the fill */
  ink: string
  /** Name of the section pattern, for legends and screen readers */
  hatchName: string
  hatch: HatchStroke[]
  surface: SurfaceStyle
}

/** Parallel 45° lines across a tile; `rising` picks the direction. Seamless when HATCH_TILE % step === 0. */
function diagonal(step: number, rising: boolean, every: (i: number) => Partial<HatchStroke> = () => ({})): HatchStroke[] {
  const t = HATCH_TILE
  const strokes: HatchStroke[] = []
  for (let c = -t, i = 0; c <= t; c += step, i++) {
    const d = rising ? `M${c},${t} L${c + t},0` : `M${c},0 L${c + t},${t}`
    strokes.push({ d, ...every(i) })
  }
  return strokes
}

/** Horizontal repeating curve, two staggered rows */
function rows(segment: (y: number) => string): HatchStroke[] {
  return [{ d: segment(4) }, { d: segment(12) }]
}

function circle(cx: number, cy: number, r: number): string {
  return `M${cx + r},${cy} A${r},${r} 0 1 0 ${cx - r},${cy} A${r},${r} 0 1 0 ${cx + r},${cy}`
}

export const LAYER_STYLES: Record<LayerKey, LayerStyle> = {
  // ---------------------------------------------------------------- pipe walls
  copper: {
    label: 'Copper',
    fill: '#C47A45',
    ink: '#4A230A',
    hatchName: '45° lines, alternate dashed (copper alloy)',
    hatch: diagonal(4, true, (i) => (i % 2 ? { dash: [2.5, 1.5] } : {})),
    surface: { metalness: 1, roughness: 0.3, texture: 'brushed' },
  },
  steel: {
    label: 'Steel',
    fill: '#A7B0B8',
    ink: '#27313B',
    hatchName: '45° lines (steel)',
    hatch: diagonal(4, true),
    surface: { metalness: 1, roughness: 0.42, texture: 'brushed' },
  },
  pvc: {
    label: 'PVC',
    fill: '#E8ECEF',
    ink: '#4B5563',
    hatchName: 'cross-hatch (plastic)',
    hatch: [...diagonal(8, true), ...diagonal(8, false)],
    surface: { metalness: 0, roughness: 0.45, clearcoat: 0.3 },
  },
  pex: {
    label: 'PEX',
    fill: '#F3DCD3',
    ink: '#8A2B1A',
    hatchName: 'paired 45° lines (plastic)',
    hatch: [...diagonal(8, false), ...diagonal(8, false).map((s) => ({ ...s, d: shift(s.d, 2) }))],
    surface: { metalness: 0, roughness: 0.35, clearcoat: 0.5 },
  },

  // ---------------------------------------------------------------- insulation
  fiberglass: {
    label: 'Fiberglass',
    fill: '#F2CF5B',
    ink: '#6B4E00',
    hatchName: 'wavy batt lines (fibrous insulation)',
    hatch: rows((y) => `M0,${y} C2,${y - 4} 6,${y - 4} 8,${y} S14,${y + 4} 16,${y}`),
    surface: { metalness: 0, roughness: 1, texture: 'fibrous' },
  },
  foam_wrap: {
    label: 'Foam wrap',
    fill: '#374151',
    ink: '#B8C2CC',
    hatchName: 'cells (closed-cell foam)',
    hatch: [
      { d: circle(4, 4, 2.6) },
      { d: circle(12, 12, 2.6) },
      { d: circle(12, 4, 1.3) },
      { d: circle(4, 12, 1.3) },
    ],
    surface: { metalness: 0, roughness: 0.85, texture: 'cells' },
  },
  mineral_wool: {
    label: 'Mineral wool',
    fill: '#CBB89D',
    ink: '#4F4030',
    hatchName: 'zigzag (mineral wool)',
    hatch: rows((y) => `M0,${y + 2} L4,${y - 2} L8,${y + 2} L12,${y - 2} L16,${y + 2}`),
    surface: { metalness: 0, roughness: 1, texture: 'fibrous' },
  },

  // ---------------------------------------------------------------- contents
  water: {
    label: 'Water',
    fill: '#1F6FB2',
    ink: '#D6ECFA',
    hatchName: 'horizontal dashes (liquid)',
    hatch: [{ d: 'M1,4 L7,4 M9,4 L15,4' }, { d: 'M-3,12 L3,12 M5,12 L11,12 M13,12 L19,12' }],
    surface: { metalness: 0, roughness: 0.08, clearcoat: 1 },
  },
  ice: {
    label: 'Ice',
    fill: '#E3F4FB',
    ink: '#1F6FB2',
    hatchName: 'crystals (ice)',
    hatch: [
      { d: 'M4,1.5 L4,6.5 M1.8,2.75 L6.2,5.25 M1.8,5.25 L6.2,2.75' },
      { d: 'M12,9.5 L12,14.5 M9.8,10.75 L14.2,13.25 M9.8,13.25 L14.2,10.75' },
    ],
    surface: { metalness: 0, roughness: 0.2, clearcoat: 0.8 },
  },
}

/** Moves every x coordinate of a simple "M x,y L x,y" path by dx */
function shift(d: string, dx: number): string {
  return d.replace(/([ML])(-?[\d.]+),/g, (_, cmd: string, x: string) => `${cmd}${Number(x) + dx},`)
}

/** Default stroke width in tile units */
export const HATCH_STROKE_WIDTH = 0.9

/** Boundary lines between layers */
export const OUTLINE_COLOR = '#1F2937'

/** Id of a layer's SVG section pattern (see SectionPatterns.vue) */
export function sectionPatternId(prefix: string, layer: LayerKey): string {
  return `${prefix}-hatch-${layer}`
}
