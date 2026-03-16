import { useEffect, useState } from 'react'

function formatArtists(raw) {
  if (raw == null || raw === '') return '—'
  const s = String(raw).trim()
  if (s.startsWith('[') && s.endsWith(']')) {
    try {
      const arr = JSON.parse(s.replace(/'/g, '"'))
      if (Array.isArray(arr)) return arr.filter(Boolean).join(', ')
    } catch {
      return s
        .slice(1, -1)
        .split(',')
        .map((x) => x.trim().replace(/^'|'$/g, ''))
        .filter(Boolean)
        .join(', ')
    }
  }
  return s
}

export default function HomePage() {
  const [health, setHealth] = useState(null)
  const [healthErr, setHealthErr] = useState(null)
  const [tracks, setTracks] = useState(null)
  const [tracksErr, setTracksErr] = useState(null)

  useEffect(() => {
    fetch('/health')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setHealth)
      .catch((e) => setHealthErr(e.message))
  }, [])

  useEffect(() => {
    fetch('/api/galaxy/tracks?limit=20000')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setTracks)
      .catch((e) => setTracksErr(e.message))
  }, [])

  return (
    <section className="panel panel-wide">
      <h1>Music Trends Galaxy</h1>
      <p className="muted">
        Маршрут <code>/map</code> — визуализация. Ниже — треки из{' '}
        <code>storage/embeded_data.csv</code> через <code>GET /api/galaxy/tracks</code>.
      </p>
      <div className="status">
        <span className="label">Бэкенд</span>
        {healthErr && <span className="err">недоступен: {healthErr}</span>}
        {!healthErr && health && <span className="ok">{health.status ?? 'ok'}</span>}
        {!healthErr && !health && <span className="muted">проверка…</span>}
      </div>

      <h2 className="h2">Треки (embeded_data)</h2>
      {tracksErr && (
        <p className="err">
          Не удалось загрузить список: {tracksErr}. Проверьте том <code>./storage</code> и файл{' '}
          <code>embeded_data.csv</code>.
        </p>
      )}
      {!tracksErr && tracks === null && <p className="muted">Загрузка…</p>}
      {!tracksErr && tracks && tracks.count === 0 && <p className="muted">Список пуст.</p>}
      {!tracksErr && tracks && tracks.count > 0 && (
        <>
          <p className="muted galaxy-tracks-meta">
            Показано: {tracks.count.toLocaleString()}
            {tracks.source_csv && (
              <>
                {' '}
                · <code className="galaxy-tracks-path">{tracks.source_csv}</code>
              </>
            )}
          </p>
          <ul className="song-list">
            {tracks.tracks.map((t) => (
              <li key={t.id || `${t.name}-${t.x}`} className="song-item">
                <span className="song-id" title="id">
                  {t.id ? String(t.id).slice(0, 8) + (String(t.id).length > 8 ? '…' : '') : '—'}
                </span>
                <div className="song-body">
                  <div className="song-title">{t.name || '—'}</div>
                  <div className="song-meta">
                    {formatArtists(t.artists)}
                    {t.album ? (
                      <>
                        {' '}
                        — {t.album}
                      </>
                    ) : null}
                    <span className="muted galaxy-xy">
                      {' '}
                      · x={t.x?.toFixed?.(3) ?? t.x}, y={t.y?.toFixed?.(3) ?? t.y}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
