import { useCallback, useEffect, useRef, useState } from 'react'

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

/** Simple deterministic hash in [0, 1) from string id */
function hash01(s) {
  let h = 2166136261
  const str = String(s)
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0) / 4294967296
}

function hslToRgb(h, s, l) {
  const a = s * Math.min(l, 1 - l)
  const f = (n) => {
    const k = (n + h / 30) % 12
    return l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
  }
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)]
}

/**
 * Galaxy-like colour: red = aggressive (high lyrical_intensity), blue = calm.
 * x/y shift hue/saturation/lightness like stellar dust and spiral arms.
 */
function starColor(x, y, bounds, lyricalIntensity, id) {
  const w = bounds.maxX - bounds.minX || 1
  const h = bounds.maxY - bounds.minY || 1
  const nx = (x - bounds.minX) / w
  const ny = (y - bounds.minY) / h
  const t = clamp(Number.isFinite(lyricalIntensity) ? lyricalIntensity : ny, 0, 1)

  const cx = nx - 0.5
  const cy = ny - 0.5
  const angle = Math.atan2(cy, cx)
  const dist = Math.min(1, Math.hypot(cx, cy) * 1.35)

  // Base hue: calm -> blue (240°), aggressive -> red (0°)
  let hue = lerp(230, 2, t)
  hue += (angle / (2 * Math.PI)) * 55
  hue += nx * 38 + ny * 42
  hue += dist * 28
  hue = ((hue % 360) + 360) % 360

  const sat = lerp(58, 100, t)
  const tw = (hash01(id) - 0.5) * 14
  const light = lerp(36, 72, 1 - dist * 0.65) + tw

  const [r, g, b] = hslToRgb(hue, sat / 100, light / 100)
  return { r, g, b }
}

function computeBounds(points) {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const p of points) {
    minX = Math.min(minX, p.x)
    maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y)
    maxY = Math.max(maxY, p.y)
  }
  if (!Number.isFinite(minX)) {
    return { minX: -1, maxX: 1, minY: -1, maxY: 1 }
  }
  const padX = (maxX - minX) * 0.04 || 0.08
  const padY = (maxY - minY) * 0.04 || 0.08
  return {
    minX: minX - padX,
    maxX: maxX + padX,
    minY: minY - padY,
    maxY: maxY + padY,
  }
}

/** Fit the full data bounding box inside the canvas (both axes), with a thin margin. */
function initialTransform(canvasW, canvasH, bounds) {
  const bw = bounds.maxX - bounds.minX || 1
  const bh = bounds.maxY - bounds.minY || 1
  const margin = 0.94
  const scale = Math.min(canvasW / bw, canvasH / bh) * margin
  const cx = (bounds.minX + bounds.maxX) / 2
  const cy = (bounds.minY + bounds.maxY) / 2
  const tx = canvasW / 2 - scale * cx
  const ty = canvasH / 2 - scale * cy
  return { scale, tx, ty }
}

export default function GalaxyScatter() {
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const transformRef = useRef({ scale: 1, tx: 0, ty: 0 })
  const boundsRef = useRef(null)
  const pointsRef = useRef([])

  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [meta, setMeta] = useState(null)
  const [sample, setSample] = useState('first')
  const [limit, setLimit] = useState(8_000)
  const [hudZoom, setHudZoom] = useState('100')

  const dragging = useRef(false)
  const lastPtr = useRef({ x: 0, y: 0 })

  const loadPoints = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      const q = new URLSearchParams({
        limit: String(limit),
        sample,
        seed: '42',
      })
      const res = await fetch(`/api/galaxy/points?${q}`)
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data = await res.json()
      pointsRef.current = data.points || []
      boundsRef.current = computeBounds(pointsRef.current)
      setMeta({
        count: data.count,
        source_csv: data.source_csv,
        sample_mode: data.sample_mode,
      })
      if (!data.points || data.points.length === 0) {
        setError('CSV loaded but contains no rows (check filters and file).')
        setStatus('error')
        return
      }
      setStatus('ready')
    } catch (e) {
      setError(e.message || String(e))
      setStatus('error')
    }
  }, [limit, sample])

  useEffect(() => {
    loadPoints()
  }, [loadPoints])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const points = pointsRef.current
    const bounds = boundsRef.current
    if (!canvas || !bounds || points.length === 0) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const w = Math.max(1, Math.floor(rect.width * dpr))
    const h = Math.max(1, Math.floor(rect.height * dpr))
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }

    const ctx = canvas.getContext('2d')
    const { scale, tx, ty } = transformRef.current

    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.fillStyle = '#030308'
    ctx.fillRect(0, 0, w, h)

    if (points.length === 0) return

    ctx.setTransform(scale * dpr, 0, 0, scale * dpr, tx * dpr, ty * dpr)
    ctx.globalCompositeOperation = 'lighter'
    ctx.globalAlpha = 1

    for (const p of points) {
      const { r, g, b } = starColor(p.x, p.y, bounds, p.lyrical_intensity, p.id)
      const br = 0.55 + hash01(p.id + 'o') * 1.15 + (1 - p.lyrical_intensity) * 0.35
      const core = `rgba(${r},${g},${b},0.92)`
      const halo = `rgba(${Math.min(255, r + 40)},${Math.min(255, g + 30)},${Math.min(255, b + 55)},0.22)`

      ctx.beginPath()
      ctx.fillStyle = halo
      ctx.arc(p.x, p.y, br * 2.8, 0, Math.PI * 2)
      ctx.fill()

      ctx.beginPath()
      ctx.fillStyle = core
      ctx.arc(p.x, p.y, br * 0.55, 0, Math.PI * 2)
      ctx.fill()
    }

    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }, [])

  useEffect(() => {
    if (status !== 'ready') return
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const bounds = boundsRef.current
    const rect = canvas.getBoundingClientRect()
    transformRef.current = initialTransform(rect.width, rect.height, bounds)
    setHudZoom(String(Math.round(transformRef.current.scale * 100)))

    draw()

    const ro = new ResizeObserver(() => {
      const c = canvasRef.current
      const b = boundsRef.current
      if (c && b && pointsRef.current.length > 0) {
        const r = c.getBoundingClientRect()
        transformRef.current = initialTransform(r.width, r.height, b)
        setHudZoom(String(Math.round(transformRef.current.scale * 100)))
      }
      draw()
    })
    ro.observe(container)
    return () => ro.disconnect()
  }, [status, draw])

  const screenToData = (sx, sy) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const cssX = sx - rect.left
    const cssY = sy - rect.top
    const { scale, tx, ty } = transformRef.current
    return {
      x: (cssX - tx) / scale,
      y: (cssY - ty) / scale,
    }
  }

  const onWheel = (e) => {
    e.preventDefault()
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const before = screenToData(e.clientX, e.clientY)
    const factor = e.deltaY > 0 ? 0.9 : 1.11
    let { scale, tx, ty } = transformRef.current
    scale = clamp(scale * factor, 0.02, 800)
    tx = mx - before.x * scale
    ty = my - before.y * scale
    transformRef.current = { scale, tx, ty }
    setHudZoom(String(Math.round(scale * 100)))
    draw()
  }

  const onDown = (e) => {
    dragging.current = true
    lastPtr.current = { x: e.clientX, y: e.clientY }
  }

  const onMove = (e) => {
    if (!dragging.current) return
    const dx = e.clientX - lastPtr.current.x
    const dy = e.clientY - lastPtr.current.y
    lastPtr.current = { x: e.clientX, y: e.clientY }
    const t = transformRef.current
    t.tx += dx
    t.ty += dy
    draw()
  }

  const onUp = () => {
    dragging.current = false
  }

  const resetView = () => {
    const canvas = canvasRef.current
    const bounds = boundsRef.current
    if (!canvas || !bounds) return
    const rect = canvas.getBoundingClientRect()
    transformRef.current = initialTransform(rect.width, rect.height, bounds)
    setHudZoom(String(Math.round(transformRef.current.scale * 100)))
    draw()
  }

  return (
    <div className="galaxy-wrap galaxy-wrap--compact" ref={containerRef}>
      <div className="galaxy-hud">
        <div className="galaxy-hud-title">Galaxy map</div>
        {meta && (
          <div className="galaxy-hud-meta">
            {meta.count.toLocaleString()} points · {meta.sample_mode}
          </div>
        )}
        <div className="galaxy-hud-controls">
          <label className="galaxy-label">
            Rows
            <input
              type="number"
              className="galaxy-input"
              min={1}
              max={120000}
              step={1}
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 1))}
            />
          </label>
          <label className="galaxy-label">
            Sample
            <select
              className="galaxy-select"
              value={sample}
              onChange={(e) => setSample(e.target.value)}
            >
              <option value="first">First rows (fast)</option>
              <option value="random">Random (full scan)</option>
            </select>
          </label>
          <button type="button" className="galaxy-btn" onClick={loadPoints}>
            Reload
          </button>
          <button type="button" className="galaxy-btn" onClick={resetView}>
            Fit
          </button>
          <span className="galaxy-zoom">zoom ~{hudZoom}%</span>
        </div>
        <p className="galaxy-hint">
          Scroll to zoom · drag to pan · red = aggressive lyrics, blue = calm
        </p>
      </div>

      {status === 'loading' && <div className="galaxy-overlay">Loading points…</div>}
      {status === 'error' && (
        <div className="galaxy-overlay galaxy-overlay-err">
          <strong>Could not load galaxy data</strong>
          <pre className="galaxy-err-pre">{error}</pre>
          <p className="galaxy-hint">
            Ensure <code>storage/embeded_data.csv</code> exists and the backend volume is mounted
            (<code>./storage:/app/storage</code>).
          </p>
        </div>
      )}

      <canvas
        ref={canvasRef}
        className="galaxy-canvas"
        onWheel={onWheel}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={onUp}
        onMouseLeave={onUp}
      />
    </div>
  )
}
