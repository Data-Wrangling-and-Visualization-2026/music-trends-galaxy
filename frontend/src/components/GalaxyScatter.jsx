import { useCallback, useEffect, useRef, useState } from 'react'

const COORD_SCALE = 2.0;

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

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

function starColor(x, y, bounds, lyricalIntensity, id) {
  const w = bounds.maxX - bounds.minX || 1;
  const h = bounds.maxY - bounds.minY || 1;
  const nx = (x - bounds.minX) / w;
  const ny = (y - bounds.minY) / h;
  let t = clamp(Number.isFinite(lyricalIntensity) ? lyricalIntensity : ny, 0, 1);

  const easeInOutCubic = (x) => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const tSmooth = easeInOutCubic(t);

  const cx = nx - 0.5;
  const cy = ny - 0.5;
  const angle = Math.atan2(cy, cx);
  const dist = Math.min(1, Math.hypot(cx, cy) * 1.35);

  let hue = lerp(240, 0, tSmooth);
  hue += (angle / (2 * Math.PI)) * 35;
  hue += nx * 20 + ny * 20;
  hue += dist * 15;
  hue = ((hue % 360) + 360) % 360;

  const sat = lerp(50, 100, tSmooth);

  const tw = (hash01(id) - 0.5) * 8;
  const light = lerp(45, 68, 1 - dist * 0.55) + tw;

  const [r, g, b] = hslToRgb(hue, sat / 100, light / 100);
  return { r, g, b };
}

function computeBounds(points) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const p of points) {
    minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y)
  }
  if (!Number.isFinite(minX)) return { minX: -1, maxX: 1, minY: -1, maxY: 1 }
  const padX = (maxX - minX) * 0.04 || 0.08
  const padY = (maxY - minY) * 0.04 || 0.08
  return { minX: minX - padX, maxX: maxX + padX, minY: minY - padY, maxY: maxY + padY }
}

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
  const [limit, setLimit] = useState(8000)
  const [hudZoom, setHudZoom] = useState('100')

  // hover tooltip
  const [hoveredPoint, setHoveredPoint] = useState(null)
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 })

  // selected song panel
  const [selectedSong, setSelectedSong] = useState(null)
  const [songDetails, setSongDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState(null)

  const dragging = useRef(false)
  const lastPtr = useRef({ x: 0, y: 0 })
  const animationFrameRef = useRef(null)

  // ----- data loading -----
  const loadPoints = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      const q = new URLSearchParams({ limit: String(limit), sample, seed: '42' })
      const res = await fetch(`/api/galaxy/points?${q}`)
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`)
      const data = await res.json()
      const scaledPoints = (data.points || []).map(p => ({ ...p, x: p.x * COORD_SCALE, y: p.y * COORD_SCALE }))
      pointsRef.current = scaledPoints
      boundsRef.current = computeBounds(pointsRef.current)
      setMeta({ count: data.count, source_csv: data.source_csv, sample_mode: data.sample_mode })
      if (!data.points || data.points.length === 0) {
        setError('CSV loaded but contains no rows')
        setStatus('error')
        return
      }
      setStatus('ready')
    } catch (e) {
      setError(e.message)
      setStatus('error')
    }
  }, [limit, sample])

  useEffect(() => { loadPoints() }, [loadPoints])

  // ----- canvas drawing (unchanged, except we rely on pointsRef) -----
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

    ctx.setTransform(scale * dpr, 0, 0, scale * dpr, tx * dpr, ty * dpr)
    ctx.globalCompositeOperation = 'lighter'
    ctx.globalAlpha = 0.6
    const zoomRadiusFactor = Math.min(1, 8 / scale)

    for (const p of points) {
      const { r, g, b } = starColor(p.x, p.y, bounds, p.lyrical_intensity, p.id)
      const baseSize = 0.38
      const randomFactor = hash01(p.id + 'o') * 0.65
      const intensityFactor = (1 - p.lyrical_intensity) * 0.2
      let br = baseSize + randomFactor + intensityFactor
      br = br * (0.5 + zoomRadiusFactor * 0.8)
      br = Math.min(1.2, br)

      const core = `rgba(${r},${g},${b},0.92)`
      const halo = `rgba(${Math.min(255, r + 30)},${Math.min(255, g + 20)},${Math.min(255, b + 40)},0.18)`

      ctx.beginPath()
      ctx.fillStyle = halo
      ctx.arc(p.x, p.y, br * 1.2, 0, Math.PI * 2)
      ctx.fill()

      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = core
      ctx.arc(p.x, p.y, br * 0.65, 0, Math.PI * 2)
      ctx.fill()
      ctx.globalCompositeOperation = 'lighter'
    }
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }, [])

  // ----- coordinate transformation helpers -----
  const screenToData = (sx, sy) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const cssX = sx - rect.left
    const cssY = sy - rect.top
    const { scale, tx, ty } = transformRef.current
    return { x: (cssX - tx) / scale, y: (cssY - ty) / scale }
  }

  const dataToScreen = (x, y) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const { scale, tx, ty } = transformRef.current
    return { x: (x * scale + tx) / dpr, y: (y * scale + ty) / dpr }
  }

  // ----- hover detection -----
  const findClosestPoint = (screenX, screenY) => {
    const canvas = canvasRef.current
    if (!canvas || pointsRef.current.length === 0) return null
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const cssX = screenX - rect.left
    const cssY = screenY - rect.top
    const { scale, tx, ty } = transformRef.current
    const px = (cssX - tx) / scale
    const py = (cssY - ty) / scale

    let best = null
    let bestDist = 15 / scale
    for (const p of pointsRef.current) {
      const dx = p.x - px
      const dy = p.y - py
      const dist = Math.hypot(dx, dy)
      if (dist < bestDist) {
        bestDist = dist
        best = p
      }
    }
    return best
  }

  const handleMouseMove = (e) => {
    if (dragging.current) return
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
    animationFrameRef.current = requestAnimationFrame(() => {
      const point = findClosestPoint(e.clientX, e.clientY)
      if (point) {
        const { x: screenX, y: screenY } = dataToScreen(point.x, point.y)
        setHoveredPoint(point)
        setHoverPos({ x: screenX, y: screenY })
      } else {
        setHoveredPoint(null)
      }
    })
  }

  const handleClick = async (e) => {
    const point = findClosestPoint(e.clientX, e.clientY)
    if (!point) return
    setSelectedSong(point)
    setDetailsLoading(true)
    setDetailsError(null)
    setSongDetails(null)
    try {
      const res = await fetch(`/api/song/${point.id}/details`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSongDetails(data)
    } catch (err) {
      setDetailsError(err.message)
    } finally {
      setDetailsLoading(false)
    }
  }

  const closeDetails = () => {
    setSelectedSong(null)
    setSongDetails(null)
    setDetailsError(null)
  }

  // ----- event handlers -----
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
    scale = clamp(scale * factor, 0.20, 800)
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

  // update canvas when transform or points change
  useEffect(() => {
    if (status === 'ready') draw()
  }, [status, draw])

  // adjust transform after container resize
  useEffect(() => {
    if (status !== 'ready') return
    const ro = new ResizeObserver(() => {
      const canvas = canvasRef.current
      const bounds = boundsRef.current
      if (canvas && bounds && pointsRef.current.length > 0) {
        const rect = canvas.getBoundingClientRect()
        transformRef.current = initialTransform(rect.width, rect.height, bounds)
        setHudZoom(String(Math.round(transformRef.current.scale * 100)))
        draw()
      }
    })
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [status, draw])

  // ----- helper for artists formatting -----
  const formatArtists = (artists) => {
    if (!artists) return '—'
    if (Array.isArray(artists)) return artists.join(', ')
    if (typeof artists === 'string') {
      if (artists.startsWith('[') && artists.endsWith(']')) {
        try {
          const parsed = JSON.parse(artists.replace(/'/g, '"'))
          if (Array.isArray(parsed)) return parsed.join(', ')
        } catch {}
      }
      return artists
    }
    return '—'
  }

  const formatDuration = (ms) => {
    if (!ms && ms !== 0) return '—'
    const minutes = Math.floor(ms / 60000)
    const seconds = ((ms % 60000) / 1000).toFixed(0)
    return `${minutes}:${seconds.padStart(2, '0')}`
  }

  const renderEnergyBar = (value) => {
    const percent = clamp(value, 0, 1) * 100
    return (
      <div className="energy-bar">
        <div className="energy-bar-fill" style={{ width: `${percent}%` }} />
      </div>
    )
  }

  // ----- render -----
  return (
    <div className="galaxy-wrap" ref={containerRef}>
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
            <select className="galaxy-select" value={sample} onChange={(e) => setSample(e.target.value)}>
              <option value="first">First rows (fast)</option>
              <option value="random">Random (full scan)</option>
            </select>
          </label>
          <button type="button" className="galaxy-btn" onClick={loadPoints}>Reload</button>
          <button type="button" className="galaxy-btn" onClick={resetView}>Fit</button>
          {/* <span className="galaxy-zoom">zoom ~{hudZoom}%</span> */}
        </div>
        <p className="galaxy-hint">
          Scroll to zoom · drag to pan · red = aggressive lyrics, blue = calm
        </p>
      </div>

      {/* tooltip */}
      {hoveredPoint && (
        <div
          className="galaxy-tooltip"
          style={{
            left: hoverPos.x,
            top: hoverPos.y,
            transform: 'translate(-50%, -120%)',
          }}
        >
          <strong>{hoveredPoint.name || '—'}</strong><br />
          {formatArtists(hoveredPoint.artists)}
        </div>
      )}

      {/* details panel */}
      {selectedSong && (
        <div className="details-panel">
          <div className="details-header">
            <h2>{selectedSong.name || '—'}</h2>
            <button className="details-close" onClick={closeDetails}>×</button>
          </div>
          <div className="details-content">
            <div className="details-artist">{formatArtists(selectedSong.artists)}</div>
            {selectedSong.album && <div className="details-album">Album: {selectedSong.album}</div>}

            {songDetails?.duration_ms && (
              <div className="details-duration">
                Duration: {formatDuration(songDetails.duration_ms)}
              </div>
            )}

            <div className="details-metrics">
              {songDetails?.energy !== undefined && (
                <div className="metric">
                  <span>Energy</span>
                  {renderEnergyBar(songDetails.energy)}
                  <span className="metric-value">{Math.round(songDetails.energy * 10)}/10</span>
                </div>
              )}
              {songDetails?.danceability !== undefined && (
                <div className="metric">
                  <span>Danceability</span>
                  {renderEnergyBar(songDetails.danceability)}
                  <span className="metric-value">{Math.round(songDetails.danceability * 10)}/10</span>
                </div>
              )}
              {songDetails?.valence !== undefined && (
                <div className="metric">
                  <span>Valence</span>
                  {renderEnergyBar(songDetails.valence)}
                  <span className="metric-value">{Math.round(songDetails.valence * 10)}/10</span>
                </div>
              )}
            </div>

            {songDetails?.lyrics && (
              <div className="details-lyrics">
                <h3>Lyrics</h3>
                <pre>{songDetails.lyrics}</pre>
              </div>
            )}

            {detailsLoading && <div className="details-loading">Loading details…</div>}
            {detailsError && <div className="details-error">Error: {detailsError}</div>}
          </div>
        </div>
      )}

      {status === 'loading' && <div className="galaxy-overlay">Loading points…</div>}
      {status === 'error' && (
        <div className="galaxy-overlay galaxy-overlay-err">
          <strong>Could not load galaxy data</strong>
          <pre className="galaxy-err-pre">{error}</pre>
        </div>
      )}

      <canvas
        ref={canvasRef}
        className="galaxy-canvas"
        onWheel={onWheel}
        onMouseDown={onDown}
        onMouseMove={handleMouseMove}
        onMouseUp={onUp}
        onMouseLeave={onUp}
        onClick={handleClick}
      />
    </div>
  )
}