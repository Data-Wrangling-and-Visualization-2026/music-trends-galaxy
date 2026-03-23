import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';

function formatArtists(raw) {
  if (raw == null || raw === '') return '—';
  const s = String(raw).trim();
  if (s.startsWith('[') && s.endsWith(']')) {
    try {
      const arr = JSON.parse(s.replace(/'/g, '"'));
      if (Array.isArray(arr)) return arr.filter(Boolean).join(', ');
    } catch {
      return s
        .slice(1, -1)
        .split(',')
        .map((x) => x.trim().replace(/^'|'$/g, ''))
        .filter(Boolean)
        .join(', ');
    }
  }
  return s;
}

export default function HomePage() {
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [healthErr, setHealthErr] = useState(null);
  const [tracks, setTracks] = useState(null);
  const [tracksErr, setTracksErr] = useState(null);
  const [clusterStats, setClusterStats] = useState(null);

  useEffect(() => {
    fetch('/health')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setHealth)
      .catch((e) => setHealthErr(e.message));
  }, []);

  useEffect(() => {
    fetch('/api/galaxy/tracks?limit=100')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setTracks)
      .catch((e) => setTracksErr(e.message));
  }, []);

  useEffect(() => {
    // Optional: fetch cluster stats if endpoint exists
    fetch('/api/galaxy/clusters')
      .then((r) => (r.ok ? r.json() : null))
      .then(setClusterStats)
      .catch(() => {});
  }, []);

  const totalSongs = tracks?.count ?? 0;
  const sampleSongs = tracks?.tracks ?? [];

  return (
    <div className="home-page">
      {/* Hero section */}
      <section className="hero">
        <div className="hero-content">
          <h1>Music Trends Galaxy</h1>
          <p className="hero-subtitle">
            Explore the evolution of musical genres and moods in a 3D galaxy built from lyrics,
            audio features, and state‑of‑the‑art clustering algorithms.
          </p>
          <div className="hero-buttons">
            <button className="btn btn-primary" onClick={() => navigate('/map')}>
              Open Map
            </button>
            <button className="btn btn-secondary" onClick={() => window.open('#pipeline', '_self')}>
              How It Works
            </button>
          </div>
        </div>
        <div className="hero-glow" />
      </section>

      {/* Statistics */}
      <section className="stats">
        <div className="stats-card">
          <div className="stats-number">100,000+</div>
          <div className="stats-label">tracks in database</div>
        </div>
        <div className="stats-card">
          <div className="stats-number">{clusterStats?.clusters || '—'}</div>
          <div className="stats-label">constellations</div>
        </div>
        <div className="stats-card">
          <div className="stats-number">{clusterStats?.dimensions || '2D'}</div>
          <div className="stats-label">space</div>
        </div>
        <div className="stats-card">
          <div className="stats-number">✨</div>
          <div className="stats-label">interactive navigation</div>
        </div>
      </section>

      {/* Data pipeline description */}
      <section className="pipeline">
        <h2>How It Works</h2>
        <p className="pipeline-intro">
          We combine Spotify audio features, lyrics from Genius, and social signals from Last.fm.
          Using AI and clustering, we map every track to a point in a 2D galaxy.
        </p>
        <div className="pipeline-cta">
          <Link to="/pipeline" className="btn btn-secondary">Learn more about our data pipeline →</Link>
        </div>
      </section>
      

      {/* Map description */}
      <section className="map-description">
        <div className="map-description-text">
          <h2>Galaxy Visualization</h2>
          <p>
            Every star is a track. Its color reflects lyrical intensity (red = aggressive, blue = calm),
            and its position is determined by semantic similarity, audio features, and clustering.
            Zoom, pan, filter by genre, year, or emotion — explore the musical universe.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/map')}>
            Explore the Galaxy
          </button>
        </div>
        <div className="map-description-preview">
          <div className="preview-placeholder">
            <span>🌌</span> interactive 3D galaxy
          </div>
        </div>
      </section>

      {/* Sample tracks */}
      {/*<section className="sample-tracks">
        <h2>Sample Tracks in the Galaxy</h2>
        {tracksErr && <p className="err">Failed to load samples: {tracksErr}</p>}
        {!tracksErr && tracks === null && <p>Loading…</p>}
        {!tracksErr && tracks && totalSongs === 0 && <p>No data available.</p>}
        {!tracksErr && tracks && totalSongs > 0 && (
          <ul className="song-list">
            {sampleSongs.slice(0, 6).map((t) => (
              <li key={t.id || `${t.name}-${t.x}`} className="song-item">
                <span className="song-id" title="id">
                  {t.id ? String(t.id).slice(0, 8) + (String(t.id).length > 8 ? '…' : '') : '—'}
                </span>
                <div className="song-body">
                  <div className="song-title">{t.name || '—'}</div>
                  <div className="song-meta">
                    {formatArtists(t.artists)}
                    {t.album ? <> — {t.album}</> : null}
                    <span className="muted galaxy-xy"> · {t.x?.toFixed(2)}, {t.y?.toFixed(2)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <button className="btn btn-secondary" onClick={() => navigate('/map')}>
          All Tracks on Map
        </button>
      </section>*/}
    </div>
  );
}