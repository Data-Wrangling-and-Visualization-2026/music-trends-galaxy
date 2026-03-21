import { Link } from 'react-router-dom';

export default function DataPipelinePage() {
  return (
    <div className="pipeline-page">
      <div className="container">
        <Link to="/" className="back-link">← Back to Home</Link>
        <h1>Data Collection Pipeline</h1>
        <div className="pipeline-steps">
          <div className="step">
            <h2>1. Data Sources</h2>
            <p>We aggregate music data from multiple public sources:</p>
            <ul>
              <li><strong>Spotify Web API</strong> – audio features, track metadata, popularity.</li>
              <li><strong>Genius API & LRCLIB</strong> – lyrics for over 200k tracks.</li>
              <li><strong>MusicBrainz</strong> – artist and release metadata.</li>
              <li><strong>Last.fm API</strong> – user tags, play counts, social listening data.</li>
              <li><strong>Kaggle datasets</strong> – pre‑collected audio features and metadata.</li>
            </ul>
          </div>
          <div className="step">
            <h2>2. Data Cleaning & Unification</h2>
            <p>We merge all sources into a single unified dataset. The pipeline handles missing values, normalises artist names, and resolves duplicates using fuzzy matching.</p>
            <p>All tracks are enriched with:</p>
            <ul>
              <li>Audio features: danceability, energy, valence, loudness, etc.</li>
              <li>Lyrics (where available)</li>
              <li>Release year and genre tags</li>
              <li>Social signals from Last.fm</li>
            </ul>
          </div>
          <div className="step">
            <h2>3. AI‑Driven Lyric Analysis</h2>
            <p>We use a local LLM (DeepSeek / Llama‑3) to analyse lyrics and generate:</p>
            <ul>
              <li><strong>Lyrical intensity</strong> (0–1): how aggressive / confrontational the words are.</li>
              <li><strong>Lyrical mood</strong> (0–1): positivity of the lyrics.</li>
              <li><strong>Theme extraction</strong> (e.g., love, protest, party).</li>
            </ul>
            <p>These features are combined with audio features to create a rich representation of each track.</p>
          </div>
          <div className="step">
            <h2>4. Embedding & Clustering</h2>
            <p>Lyrics are converted into semantic vectors using <code>all‑MiniLM‑L6‑v2</code> (or a larger model). We then apply <strong>UMAP</strong> to reduce dimensionality to 15, followed by <strong>HDBSCAN</strong> clustering to discover “constellations”. Finally, <strong>t‑SNE</strong> projects everything into 2D coordinates for visualisation.</p>
          </div>
          <div className="step">
            <h2>5. Backend & API</h2>
            <p>The processed data is stored in a SQLite database and served by a FastAPI backend. The frontend fetches points, metadata, and album covers through REST endpoints.</p>
          </div>
        </div>
      </div>
    </div>
  );
}