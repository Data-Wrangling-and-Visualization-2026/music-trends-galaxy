import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

export default function HomePage() {
  const [galaxyTrackCount, setGalaxyTrackCount] = useState(null);

  useEffect(() => {
    fetch('/api/galaxy/tracks?limit=100000&sample=first&seed=42')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.count === 'number') setGalaxyTrackCount(d.count);
      })
      .catch(() => {});
  }, []);

  const countLabel =
    galaxyTrackCount != null
      ? galaxyTrackCount.toLocaleString()
      : '—';

  const countHint =
    galaxyTrackCount != null
      ? 'Loaded from the API'
      : 'Start the backend to show live stats';

  return (
    <main className="home-page">
      <section className="home-hero" aria-labelledby="home-heading">
        <div className="home-hero-bg" aria-hidden />
        <div className="home-hero-content">
          <p className="home-kicker">Explore · compare · discover</p>
          <h1 id="home-heading" className="home-title">
            Music Trends Galaxy
          </h1>
          <p className="home-lead">
            Navigate a three‑dimensional map of tracks: embeddings and audio features shape the
            constellations; color follows mood and energy. Pick stars, compare profiles, and follow
            threads into detail pages.
          </p>
          <div className="home-cta">
            <Link to="/map" className="home-btn home-btn-primary">
              Open galaxy map
            </Link>
            <a href="#pipeline" className="home-btn home-btn-ghost">
              How it works
            </a>
          </div>
        </div>
      </section>

      <section className="home-stats" aria-label="Dataset stats">
        <div className="home-stats-grid">
          <article className="home-stat-card">
            <div className="home-stat-value">{countLabel}</div>
            <p className="home-stat-label">
              Tracks on the map · {countHint}
            </p>
          </article>
          <article className="home-stat-card">
            <div className="home-stat-value">3D</div>
            <p className="home-stat-label">
              UMAP / projection into coordinates you explore as a star field
            </p>
          </article>
          <article className="home-stat-card">
            <div className="home-stat-value">AI</div>
            <p className="home-stat-label">
              Clusters &amp; lyrical scores from the pipeline — not just raw playlists
            </p>
          </article>
        </div>
      </section>

      <section className="home-section" id="pipeline">
        <p className="home-section-title">Pipeline</p>
        <h2>How it works</h2>
        <p className="home-section-lead">
          Roughly: lyrics and audio become vectors → dimensionality reduction → clustering → 3D
          layout for the browser. The database backs the API your map talks to.
        </p>

        <div className="home-steps">
          <article className="home-step">
            <span className="home-step-num" aria-hidden>
              1
            </span>
            <div>
              <h3>Ingest &amp; features</h3>
              <p>
                Tracks arrive with metadata, audio features (Spotify‑style), and lyrics when
                available — the foundation for both the embedding space and the comparison panels.
              </p>
            </div>
          </article>
          <article className="home-step">
            <span className="home-step-num" aria-hidden>
              2
            </span>
            <div>
              <h3>Embedding &amp; clusters</h3>
              <p>
                Text (and optional audio fusion) is embedded, reduced, and clustered so similar
                tracks sit nearby; each point knows its cluster for filters and tinting.
              </p>
            </div>
          </article>
          <article className="home-step">
            <span className="home-step-num" aria-hidden>
              3
            </span>
            <div>
              <h3>Galaxy in the browser</h3>
              <p>
                The frontend renders the cloud in WebGL, blends cluster color with track energy /
                valence, and loads detail on demand when you focus a star.
              </p>
            </div>
          </article>
        </div>

        <p className="home-section-cta">
          <Link to="/map" className="home-link-inline">
            Enter the map →
          </Link>
        </p>
      </section>
    </main>
  );
}
