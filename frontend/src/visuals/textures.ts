/**
 * Procedural canvas textures for the 3D pipe: section hatching (the same
 * patterns as the 2D views) and surface detail for the exterior materials.
 */

import * as THREE from 'three'
import { LAYER_STYLES, HATCH_TILE, HATCH_STROKE_WIDTH, type LayerKey, type SurfaceStyle } from './materialStyles'

function makeCanvas(size: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('2D canvas unavailable')
  return [canvas, ctx]
}

function toTexture(canvas: HTMLCanvasElement, colorSpace: THREE.ColorSpace): THREE.CanvasTexture {
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.colorSpace = colorSpace
  return texture
}

/** Seeded PRNG so the procedural textures look the same on every render */
function random(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 2 ** 32
  }
}

/** One tile of a layer's section lining; used with world-unit UVs so line spacing is uniform */
export function createHatchTexture(layer: LayerKey, size = 256): THREE.CanvasTexture {
  const style = LAYER_STYLES[layer]
  const [canvas, ctx] = makeCanvas(size)
  const k = size / HATCH_TILE

  ctx.fillStyle = style.fill
  ctx.fillRect(0, 0, size, size)
  ctx.scale(k, k)
  ctx.strokeStyle = style.ink
  ctx.lineCap = 'butt'
  for (const stroke of style.hatch) {
    ctx.lineWidth = stroke.width ?? HATCH_STROKE_WIDTH
    ctx.setLineDash(stroke.dash ?? [])
    ctx.stroke(new Path2D(stroke.d))
  }
  return toTexture(canvas, THREE.SRGBColorSpace)
}

/**
 * Greyscale detail for an exterior surface: brushed streaks along the pipe
 * for metals, fibres or foam cells for insulation. Used as a bump map, and
 * for insulation also as a (near-white) colour map so the fill colour shows.
 */
export function createSurfaceTexture(kind: NonNullable<SurfaceStyle['texture']>, size = 256): THREE.CanvasTexture {
  const [canvas, ctx] = makeCanvas(size)
  const rand = random(kind.length * 7919)

  ctx.fillStyle = '#E6E6E6'
  ctx.fillRect(0, 0, size, size)

  if (kind === 'brushed') {
    // Cylinder UVs run u around the pipe and v along it: streaks are vertical lines
    for (let x = 0; x < size; x++) {
      const g = Math.round(200 + rand() * 55)
      ctx.fillStyle = `rgb(${g},${g},${g})`
      ctx.fillRect(x, 0, 1, size)
    }
  } else if (kind === 'fibrous') {
    ctx.lineCap = 'round'
    for (let i = 0; i < 900; i++) {
      const x = rand() * size
      const y = rand() * size
      const angle = rand() * Math.PI
      const len = 4 + rand() * 14
      const g = Math.round(150 + rand() * 105)
      ctx.strokeStyle = `rgb(${g},${g},${g})`
      ctx.lineWidth = 0.6 + rand() * 1.2
      ctx.beginPath()
      ctx.moveTo(x, y)
      ctx.lineTo(x + Math.cos(angle) * len, y + Math.sin(angle) * len)
      ctx.stroke()
    }
  } else {
    for (let i = 0; i < 260; i++) {
      const x = rand() * size
      const y = rand() * size
      const r = 2 + rand() * 6
      const g = Math.round(170 + rand() * 50)
      ctx.fillStyle = `rgb(${g},${g},${g})`
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  return toTexture(canvas, THREE.SRGBColorSpace)
}
