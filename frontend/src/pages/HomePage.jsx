import { useEffect, useState } from 'react'

export default function HomePage() {
  const [health, setHealth] = useState(null)
  const [healthErr, setHealthErr] = useState(null)
  const [songs, setSongs] = useState(null)
  const [songsErr, setSongsErr] = useState(null)

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
    fetch('/api/songs')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setSongs)
      .catch((e) => setSongsErr(e.message))
  }, [])

  return (
    <section className="panel panel-wide">
      <h1>Music Trends Galaxy</h1>
      <p className="muted">
        Маршрут <code>/map</code> — под визуализацию. Ниже — проверка API и SQLite через{' '}
        <code>GET /api/songs</code>.
      </p>
      <div className="status">
        <span className="label">Бэкенд</span>
        {healthErr && <span className="err">недоступен: {healthErr}</span>}
        {!healthErr && health && <span className="ok">{health.status ?? 'ok'}</span>}
        {!healthErr && !health && <span className="muted">проверка…</span>}
      </div>

      <h2 className="h2">Треки из БД</h2>
      {songsErr && <p className="err">Не удалось загрузить список: {songsErr}</p>}
      {!songsErr && songs === null && <p className="muted">Загрузка…</p>}
      {!songsErr && songs && songs.length === 0 && <p className="muted">Список пуст.</p>}
      {!songsErr && songs && songs.length > 0 && (
        <ul className="song-list">
          {songs.map((s) => (
            <li key={s.id} className="song-item">
              <span className="song-id">#{s.id}</span>
              <div className="song-body">
                <div className="song-title">{s.name}</div>
                <div className="song-meta">
                  {s.artists.join(', ')} — {s.album}
                  <span className="muted"> ({s.album_id})</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
