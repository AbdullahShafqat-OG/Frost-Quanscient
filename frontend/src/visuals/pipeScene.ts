/**
 * three.js scene for the interactive 3D pipe.
 *
 * Framework-agnostic: the Vue component owns the canvas and lifecycle, this
 * class owns everything three.js. Renders on demand (only when the camera or
 * the model changes) rather than in a continuous loop.
 *
 * The pipe is a short segment along the x axis, normalised so the outermost
 * radius is 1. Layers are stepped back at the right end (insulation shortest)
 * and, in cutaway mode, a quarter is removed along the length so every layer
 * shows its section. Cut faces use the same hatching as the 2D sections;
 * exterior surfaces use physically based materials.
 */

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { PipeRadii } from '@/composables/usePipeGeometry'
import { LAYER_STYLES, OUTLINE_COLOR, type LayerKey } from './materialStyles'
import { createHatchTexture, createSurfaceTexture } from './textures'

export interface PipeModel {
  radii: PipeRadii
  wall: LayerKey
  insulation: LayerKey | null
  cutaway: boolean
}

const LENGTH = 5
/** How far each layer is stepped back from the one inside it, at the right end */
const STEP = 0.7
/** World size of one hatch tile: keeps line spacing equal on every face */
const HATCH_WORLD_SIZE = 0.28
const SEGMENTS = 128
/** Cutaway keeps 270° of the pipe; the removed quarter faces the default camera */
const CUT_THETA = Math.PI * 1.5

const BACKGROUND = '#F1F5F9'
const CAMERA_HOME = new THREE.Vector3(4.4, 2.6, 4.8)
const TARGET_HOME = new THREE.Vector3(0.2, -0.1, 0)
const MIN_DISTANCE = 3
const MAX_DISTANCE = 14

interface Annulus {
  layer: LayerKey
  rIn: number
  rOut: number
  /** Right end along the pipe axis; all layers start at -LENGTH / 2 */
  end: number
}

export class PipeScene {
  private readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100)
  private readonly controls: OrbitControls
  private readonly pipe = new THREE.Group()
  private readonly materials = new Map<string, THREE.Material>()
  private readonly textures: THREE.Texture[] = []
  private readonly outlineMaterial = new THREE.LineBasicMaterial({ color: OUTLINE_COLOR })
  private frame = 0

  constructor(canvas: HTMLCanvasElement, options: { reducedMotion: boolean }) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    // Neutral tone mapping keeps the material colours close to the 2D palette
    this.renderer.toneMapping = THREE.NeutralToneMapping
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    const room = new RoomEnvironment()
    this.scene.environment = pmrem.fromScene(room, 0.04).texture
    this.scene.environmentIntensity = 0.9
    room.dispose()
    pmrem.dispose()

    const key = new THREE.DirectionalLight(0xffffff, 1.4)
    key.position.set(3, 5, 4)
    this.scene.add(key)

    // Pipe axis: cylinders are built along y, the group turns them onto x
    this.pipe.rotation.z = -Math.PI / 2
    this.scene.add(this.pipe)

    this.controls = new OrbitControls(this.camera, canvas)
    this.controls.enableDamping = !options.reducedMotion
    this.controls.dampingFactor = 0.08
    this.controls.enablePan = false
    this.controls.minDistance = MIN_DISTANCE
    this.controls.maxDistance = MAX_DISTANCE
    this.controls.addEventListener('change', this.requestRender)
    this.resetView()
  }

  // ------------------------------------------------------------------ public

  setModel(model: PipeModel): void {
    this.clearPipe()
    for (const annulus of this.layout(model)) this.addAnnulus(annulus, model.cutaway)
    this.requestRender()
  }

  setSize(width: number, height: number): void {
    if (!width || !height) return
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
    this.requestRender()
  }

  resetView(): void {
    this.camera.position.copy(CAMERA_HOME)
    this.controls.target.copy(TARGET_HOME)
    this.controls.update()
    this.requestRender()
  }

  /**
   * Fit the camera to a pipe whose outermost radius is `outerRadius` in world-space.
   * Pass `resetOrientation = true` only on first mount and when the user clicks
   * "Reset view" — subsequent model changes (wall / insulation tweaks) just update
   * the distance constraints so the user's current rotation is preserved.
   */
  fitCamera(outerRadius: number, resetOrientation = false): void {
    const s = Math.max(outerRadius, 0.2)
    this.controls.minDistance = MIN_DISTANCE * s
    this.controls.maxDistance = MAX_DISTANCE * s

    if (resetOrientation) {
      this.camera.position.copy(CAMERA_HOME.clone().multiplyScalar(s))
      this.controls.target.copy(TARGET_HOME.clone().multiplyScalar(s))
    } else {
      // Keep the current orbit angle; only clamp distance into the new valid range.
      const offset = this.camera.position.clone().sub(this.controls.target)
      const dist = THREE.MathUtils.clamp(offset.length(), MIN_DISTANCE * s, MAX_DISTANCE * s)
      this.camera.position.copy(this.controls.target.clone().add(offset.setLength(dist)))
    }

    this.controls.update()
    this.requestRender()
  }

  /** Keyboard orbit: angles in radians */
  orbit(dAzimuth: number, dPolar: number): void {
    const offset = this.camera.position.clone().sub(this.controls.target)
    const spherical = new THREE.Spherical().setFromVector3(offset)
    spherical.theta += dAzimuth
    spherical.phi = THREE.MathUtils.clamp(spherical.phi + dPolar, 0.05, Math.PI - 0.05)
    this.camera.position.copy(this.controls.target).add(offset.setFromSpherical(spherical))
    this.controls.update()
  }

  /** factor < 1 moves closer */
  zoom(factor: number): void {
    const offset = this.camera.position.clone().sub(this.controls.target)
    const distance = THREE.MathUtils.clamp(offset.length() * factor, MIN_DISTANCE, MAX_DISTANCE)
    this.camera.position.copy(this.controls.target).add(offset.setLength(distance))
    this.controls.update()
  }

  dispose(): void {
    cancelAnimationFrame(this.frame)
    this.controls.removeEventListener('change', this.requestRender)
    this.controls.dispose()
    this.clearPipe()
    this.materials.forEach((m) => m.dispose())
    this.textures.forEach((t) => t.dispose())
    this.outlineMaterial.dispose()
    this.scene.environment?.dispose()
    this.renderer.dispose()
  }

  // ------------------------------------------------------------------ rendering

  private readonly requestRender = (): void => {
    if (!this.frame) this.frame = requestAnimationFrame(this.render)
  }

  private readonly render = (): void => {
    this.frame = 0
    // With damping, update() keeps emitting 'change' until the camera settles
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  // ------------------------------------------------------------------ geometry

  /** Layers from the core outwards, each stepped back from the one inside it */
  private layout({ radii, wall, insulation }: PipeModel): Annulus[] {
    const end = LENGTH / 2
    const layers: Annulus[] = []
    if (radii.liquid > 1e-3) layers.push({ layer: 'water', rIn: 0, rOut: radii.liquid, end })
    if (radii.water - radii.liquid > 1e-3) layers.push({ layer: 'ice', rIn: radii.liquid, rOut: radii.water, end })
    layers.push({ layer: wall, rIn: radii.water, rOut: radii.wall, end })
    if (insulation && radii.outer - radii.wall > 1e-3) {
      layers.push({ layer: insulation, rIn: radii.wall, rOut: radii.outer, end: end - STEP })
    }
    return layers
  }

  private addAnnulus({ layer, rIn, rOut, end }: Annulus, cutaway: boolean): void {
    const start = -LENGTH / 2
    const length = end - start
    const thetaLength = cutaway ? CUT_THETA : Math.PI * 2
    const section = this.sectionMaterial(layer)

    // Exterior surface
    const shell = new THREE.CylinderGeometry(rOut, rOut, length, SEGMENTS, 1, true, 0, thetaLength)
    shell.translate(0, (start + end) / 2, 0)
    this.pipe.add(new THREE.Mesh(shell, this.surfaceMaterial(layer)))

    // End faces. A ring's angle φ maps to the cylinder's θ as φ = π/2 − θ after rotating it into xz
    for (const y of [start, end]) {
      const ring = new THREE.RingGeometry(rIn, rOut, SEGMENTS, 1, Math.PI / 2 - thetaLength, thetaLength)
      ring.rotateX(Math.PI / 2)
      ring.translate(0, y, 0)
      setPlanarUVs(ring, 'x', 'z')
      this.addSection(ring, section)
    }

    // Lengthwise cut faces
    if (cutaway) {
      for (const theta of [0, thetaLength]) {
        this.addSection(cutFace(rIn, rOut, start, end, theta), section)
      }
    }
  }

  private addSection(geometry: THREE.BufferGeometry, material: THREE.Material): void {
    this.pipe.add(new THREE.Mesh(geometry, material))
    this.pipe.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), this.outlineMaterial))
  }

  private clearPipe(): void {
    for (const child of [...this.pipe.children]) {
      if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments) child.geometry.dispose()
      this.pipe.remove(child)
    }
  }

  // ------------------------------------------------------------------ materials

  /** Cut faces: flat hatched fill, like a drawing; pushed back so outlines draw on top */
  private sectionMaterial(layer: LayerKey): THREE.Material {
    return this.cached(`section:${layer}`, () => {
      const map = this.track(createHatchTexture(layer))
      map.anisotropy = this.renderer.capabilities.getMaxAnisotropy()
      return new THREE.MeshStandardMaterial({
        map,
        roughness: 0.9,
        metalness: 0,
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      })
    })
  }

  /** Exterior: physically based look of the real material */
  private surfaceMaterial(layer: LayerKey): THREE.Material {
    return this.cached(`surface:${layer}`, () => {
      const { fill, surface } = LAYER_STYLES[layer]
      const material = new THREE.MeshPhysicalMaterial({
        color: fill,
        metalness: surface.metalness,
        roughness: surface.roughness,
        clearcoat: surface.clearcoat ?? 0,
        side: THREE.DoubleSide,
      })
      if (surface.texture) {
        const detail = this.track(createSurfaceTexture(surface.texture))
        detail.repeat.set(surface.texture === 'brushed' ? 2 : 4, 2)
        material.bumpMap = detail
        material.bumpScale = surface.texture === 'brushed' ? 0.4 : 2
        if (surface.texture === 'brushed') material.roughnessMap = detail
        else material.map = detail
      }
      return material
    })
  }

  private cached(key: string, create: () => THREE.Material): THREE.Material {
    let material = this.materials.get(key)
    if (!material) {
      material = create()
      this.materials.set(key, material)
    }
    return material
  }

  private track<T extends THREE.Texture>(texture: T): T {
    this.textures.push(texture)
    return texture
  }
}

/** Flat radial strip at angle θ, from rIn to rOut, along the pipe axis */
function cutFace(rIn: number, rOut: number, y0: number, y1: number, theta: number): THREE.BufferGeometry {
  const dx = Math.sin(theta)
  const dz = Math.cos(theta)
  const corners: [number, number][] = [
    [rIn, y0],
    [rOut, y0],
    [rOut, y1],
    [rIn, y1],
  ]
  const positions = corners.flatMap(([r, y]) => [r * dx, y, r * dz])
  // u along the axis, so horizontal pattern features (water dashes) follow the pipe as in the side section
  const uvs = corners.flatMap(([r, y]) => [y / HATCH_WORLD_SIZE, r / HATCH_WORLD_SIZE])
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  geometry.setIndex([0, 1, 2, 0, 2, 3])
  geometry.computeVertexNormals()
  return geometry
}

/** UVs in world units from two position axes, so hatching has the same scale on every face */
function setPlanarUVs(geometry: THREE.BufferGeometry, u: 'x' | 'y' | 'z', v: 'x' | 'y' | 'z'): void {
  const position = geometry.getAttribute('position')
  const uvs = new Float32Array(position.count * 2)
  const read = { x: position.getX.bind(position), y: position.getY.bind(position), z: position.getZ.bind(position) }
  for (let i = 0; i < position.count; i++) {
    uvs[i * 2] = read[u](i) / HATCH_WORLD_SIZE
    uvs[i * 2 + 1] = read[v](i) / HATCH_WORLD_SIZE
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2))
}
