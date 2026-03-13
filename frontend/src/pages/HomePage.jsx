import { useEffect, useState } from 'react'

export default function HomePage() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/health')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setHealth)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <section className="panel">
      <h1>Music Trends Galaxy</h1>
      <p className="muted">Минимальная оболочка: маршрут <code>/map</code> под визуализацию.</p>
      <div className="status">
        <span className="label">Бэкенд</span>
        {error && <span className="err">недоступен: {error}</span>}
        {!error && health && <span className="ok">{health.status ?? 'ok'}</span>}
        {!error && !health && <span className="muted">проверка…</span>}
      </div>
    </section>
  )
}
