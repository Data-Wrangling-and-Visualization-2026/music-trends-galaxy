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
            <h2>3. Text Embeddings</h2>
            <p>Each song's lyrics are converted into a high‑dimensional vector (embedding) using <code>sentence-transformers/all-MiniLM-L6-v2</code>. This model encodes the semantic meaning of the text, so lyrically similar songs get similar vectors.</p>
            <p>Embeddings are generated in batches, producing a 384‑dimensional vector per track. These vectors capture themes, emotions, and style without the need for manual feature engineering.</p>
          </div>
          <div className="step">
            <h2>4. Dimensionality Reduction & Clustering</h2>
            <p>We first reduce the 384‑dimensional embeddings to 15 dimensions using <strong>UMAP</strong>, preserving both local and global structure. Then <strong>HDBSCAN</strong> discovers clusters (“constellations”) of semantically similar songs. Two levels of clustering are available:</p>
            <ul>
              <li><strong>Deep clusters</strong> – smaller, more specific groups (min_cluster_size=50).</li>
              <li><strong>Wide clusters</strong> – larger, broader genres (min_cluster_size=500).</li>
            </ul>
            <p>Finally, <strong>t‑SNE</strong> projects the 15‑dimensional points onto a 2D canvas for interactive visualisation. The resulting coordinates (x, y) are stored together with cluster labels.</p>
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