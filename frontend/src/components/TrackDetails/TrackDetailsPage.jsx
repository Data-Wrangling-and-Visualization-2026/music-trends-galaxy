import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { fetchTrackDetails } from '../../services/tracksApi.js';
import './TrackDetailsPage.css';

const RADAR_KEYS = [
  { key: 'danceability', label: 'Danceability' },
  { key: 'energy', label: 'Energy' },
  { key: 'valence', label: 'Valence' },
  { key: 'speechiness', label: 'Speechiness' },
  { key: 'acousticness', label: 'Acousticness' },
  { key: 'liveness', label: 'Liveness' },
  { key: 'instrumentalness', label: 'Instrumental' },
];

const DUMBBELL_KEYS = [
  { key: 'energy', label: 'Energy' },
  { key: 'valence', label: 'Valence' },
  { key: 'lyrical_mood', label: 'Lyrical mood' },
  { key: 'lyrical_intensity', label: 'Lyrical intensity' },
];

function safeNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function clamp01(v) {
  if (v == null) return null;
  return Math.max(0, Math.min(1, v));
}

function keyToName(v) {
  const n = safeNum(v);
  if (n == null) return 'Unknown key';
  return ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][n] || `Key ${n}`;
}

function modeToName(v) {
  const n = safeNum(v);
  if (n == null) return 'Unknown mode';
  return n === 1 ? 'Major' : 'Minor';
}

function meanMetric(entity, metricKey) {
  const maybe = entity?.metrics?.[metricKey];
  if (maybe && typeof maybe === 'object' && maybe.mean != null) {
    return clamp01(safeNum(maybe.mean));
  }
  return null;
}

function dumbbellRows(primaryArtist, album, cluster) {
  return DUMBBELL_KEYS.map(({ key, label }) => {
    const artist = meanMetric(primaryArtist, key);
    const albumV = meanMetric(album, key);
    const clusterV = meanMetric(cluster, key);
    return { key, label, artist, album: albumV, cluster: clusterV };
  }).filter((r) => r.artist != null || r.album != null || r.cluster != null);
}

export default function TrackDetailsPage() {
  const navigate = useNavigate();
  const { trackId } = useParams();
  const [trackInfo, setTrackInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [coverFailed, setCoverFailed] = useState(false);

  useEffect(() => {
    if (!trackId) return;
    setLoading(true);
    setError(null);
    setCoverFailed(false);
    fetchTrackDetails(trackId)
      .then(setTrackInfo)
      .catch((err) => {
        console.error(err);
        setError(err?.message || 'Failed to load track');
        setTrackInfo(null);
      })
      .finally(() => setLoading(false));
  }, [trackId]);

  const mf = trackInfo?.musical_features || {};
  const primaryArtist = trackInfo?.artists_detail?.[0] || null;
  const cluster = trackInfo?.cluster || trackInfo?.musical_features?.cluster || null;
  const album = trackInfo?.album || null;

  const radarData = useMemo(
    () =>
      RADAR_KEYS.map(({ key, label }) => ({
        subject: label,
        value: clamp01(safeNum(mf[key])) ?? 0,
        raw: mf[key],
      })).filter((r) => r.raw != null),
    [mf]
  );

  const dumbbell = useMemo(() => dumbbellRows(primaryArtist, album, cluster), [primaryArtist, album, cluster]);

  const tonalKey = keyToName(mf.key);
  const tonalMode = modeToName(mf.mode);
  const coverUrl = trackInfo?.album_id ? `/api/cover/storage/album/${encodeURIComponent(trackInfo.album_id)}.jpg` : null;

  if (loading) return <div className="details-container details-state">Loading extended data...</div>;
  if (error) return <div className="details-container details-state">Could not load track: {error}</div>;
  if (!trackInfo) return <div className="details-container details-state">Data lost in space...</div>;

  return (
    <div className="details-container">
      <button type="button" className="details-back-btn" onClick={() => navigate(-1)}>
        ← Back
      </button>

      <header className="details-hero" style={{ '--track-accent': trackInfo.color ?? '#8ab4ff' }}>
        <div className="details-cover-wrap">
          {!coverFailed && coverUrl ? (
            <img
              className="details-cover"
              src={coverUrl}
              alt={`Album cover: ${trackInfo.album_title}`}
              onError={() => setCoverFailed(true)}
            />
          ) : (
            <div className="details-cover details-cover--fallback">No cover</div>
          )}
        </div>
        <div className="details-hero-copy">
          <h1>{trackInfo.name}</h1>
          <p className="details-subtitle">
            {trackInfo.artist_name} · {trackInfo.album_title} · {trackInfo.year ?? '—'}
          </p>
          <div className="details-chip-row">
            <span className="details-chip">Tonality: {tonalKey} {tonalMode}</span>
            <span className="details-chip">Tempo: {mf.tempo != null ? `${Math.round(mf.tempo)} BPM` : '—'}</span>
            <span className="details-chip">Cluster: {cluster?.name || trackInfo?.galaxy?.cluster_name || 'Unclustered'}</span>
          </div>
        </div>
      </header>

      <div className="details-layout">
        <section className="details-panel details-panel--radar">
          <h3>Track audio profile</h3>
          {radarData.length ? (
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.12)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 11 }} />
                <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
                <Radar
                  name={trackInfo.name}
                  dataKey="value"
                  stroke={trackInfo.color || '#8ab4ff'}
                  fill={trackInfo.color || '#8ab4ff'}
                  fillOpacity={0.28}
                  strokeWidth={2}
                />
                <Tooltip
                  formatter={(v) => Number(v).toFixed(2)}
                  contentStyle={{
                    background: 'rgba(12,12,20,0.95)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    borderRadius: '10px',
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <p className="details-muted">No audio features available for this track.</p>
          )}
        </section>

        <section className="details-panel">
          <h3>Track text & tonality</h3>
          <div className="details-kv-grid">
            <div className="details-kv"><span>Lyrical mood</span><strong>{mf.lyrical_mood != null ? Number(mf.lyrical_mood).toFixed(3) : '—'}</strong></div>
            <div className="details-kv"><span>Lyrical intensity</span><strong>{mf.lyrical_intensity != null ? Number(mf.lyrical_intensity).toFixed(3) : '—'}</strong></div>
            <div className="details-kv"><span>Key</span><strong>{tonalKey}</strong></div>
            <div className="details-kv"><span>Mode</span><strong>{tonalMode}</strong></div>
          </div>
        </section>

        <section className="details-panel">
          <h3>Context</h3>
          <div className="details-context">
            <div><span>Artist</span><strong>{primaryArtist?.name || trackInfo.artist_name}</strong></div>
            <div><span>Album</span><strong>{album?.title || trackInfo.album_title}</strong></div>
            <div><span>Cluster</span><strong>{cluster?.name || trackInfo?.galaxy?.cluster_name || 'Unclustered'}</strong></div>
          </div>
          <div className="cluster-box">
            <h4>{cluster?.name || 'Unclustered'}</h4>
            <p>{cluster?.description || 'No cluster description available for this track yet.'}</p>
          </div>
        </section>

        <section className="details-panel details-panel--full">
          <h3>Artist vs album vs cluster (Dumbbell)</h3>
          {!dumbbell.length ? (
            <p className="details-muted">No aggregate metric means available for artist / album / cluster.</p>
          ) : (
            <div className="dumbbell-list">
              {dumbbell.map((row) => (
                <div className="dumbbell-row" key={row.key}>
                  <div className="dumbbell-label">{row.label}</div>
                  <div className="dumbbell-track">
                    <div className="dumbbell-line" />
                    {row.artist != null && (
                      <span className="dot dot-artist" style={{ left: `${row.artist * 100}%` }} title={`Artist: ${row.artist.toFixed(2)}`} />
                    )}
                    {row.album != null && (
                      <span className="dot dot-album" style={{ left: `${row.album * 100}%` }} title={`Album: ${row.album.toFixed(2)}`} />
                    )}
                    {row.cluster != null && (
                      <span className="dot dot-cluster" style={{ left: `${row.cluster * 100}%` }} title={`Cluster: ${row.cluster.toFixed(2)}`} />
                    )}
                  </div>
                </div>
              ))}
              <div className="dumbbell-legend">
                <span><i className="dot dot-artist" /> Artist</span>
                <span><i className="dot dot-album" /> Album</span>
                <span><i className="dot dot-cluster" /> Cluster</span>
              </div>
            </div>
          )}
        </section>

        <section className="details-panel details-panel--full">
          <h3>Lyrics</h3>
          <p className="full-lyrics">{trackInfo.lyrics || 'No lyrics available.'}</p>
        </section>
      </div>
    </div>
  );
}