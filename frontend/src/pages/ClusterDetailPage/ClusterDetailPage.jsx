import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchTrackDetails } from '../../services/tracksApi';
import { getClusterAnalyticsData } from '../ClustersPage/clusterAnalyticsCache';
import './ClusterDetailPage.css';

const METRICS = [
  { key: 'energy', label: 'Energy' },
  { key: 'valence', label: 'Valence' },
  { key: 'lyrical_mood', label: 'Lyrical mood' },
  { key: 'lyrical_intensity', label: 'Lyrical intensity' },
];

function normCode(v) {
  if (v == null || v === '') return '-1';
  return String(v);
}

function toNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function topNCountMap(entries, n = 12) {
  const sorted = [...entries].sort((a, b) => b.count - a.count);
  const top = sorted.slice(0, n);
  const rest = sorted.slice(n).reduce((s, x) => s + x.count, 0);
  if (rest > 0) top.push({ name: 'Other', count: rest });
  return top;
}

export default function ClusterDetailPage() {
  const { clusterCode } = useParams();
  const code = decodeURIComponent(clusterCode || '-1');
  const navigate = useNavigate();
  const [clusters, setClusters] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [points, setPoints] = useState([]);
  const [idealTrack, setIdealTrack] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getClusterAnalyticsData()
      .then(({ clusters: cl, tracks: tr, points: pt }) => {
        setClusters(cl);
        setTracks(tr);
        setPoints(pt);
      })
      .catch((e) => setError(e?.message || 'Failed to load cluster details'))
      .finally(() => setLoading(false));
  }, [code]);

  const data = useMemo(() => {
    const pointByTrack = new Map(points.map((p) => [p.track_id, p]));
    const members = tracks.filter((t) => normCode(t.cluster_code ?? pointByTrack.get(t.id)?.cluster_code) === code);
    const memberPoints = members
      .map((t) => pointByTrack.get(t.id))
      .filter(Boolean);
    const cluster = clusters.find((c) => normCode(c.code) === code) || null;

    const albumMap = new Map();
    const artistMap = new Map();
    for (const t of members) {
      const an = t.album || t.album_id || 'Unknown album';
      albumMap.set(an, (albumMap.get(an) || 0) + 1);
      const artistsLine = String(t.artists || '').trim();
      const names = artistsLine
        ? artistsLine.split(',').map((x) => x.trim()).filter(Boolean)
        : ['Unknown artist'];
      for (const n of names) {
        artistMap.set(n, (artistMap.get(n) || 0) + 1);
      }
    }

    const total = Math.max(1, members.length);
    const albumAbs = topNCountMap([...albumMap.entries()].map(([name, count]) => ({ name, count })));
    const artistAbs = topNCountMap([...artistMap.entries()].map(([name, count]) => ({ name, count })));
    const albumPct = albumAbs.map((x) => ({ ...x, percent: (x.count / total) * 100 }));
    const artistPct = artistAbs.map((x) => ({ ...x, percent: (x.count / total) * 100 }));

    let idealTrackId = null;
    if (memberPoints.length) {
      const means = {};
      for (const m of METRICS) {
        const vals = memberPoints.map((p) => toNum(p[m.key])).filter((x) => x != null);
        means[m.key] = vals.length ? vals.reduce((s, x) => s + x, 0) / vals.length : null;
      }
      let best = null;
      for (const t of members) {
        const p = pointByTrack.get(t.id);
        if (!p) continue;
        let d = 0;
        let n = 0;
        for (const m of METRICS) {
          if (means[m.key] == null) continue;
          const v = toNum(p[m.key]);
          if (v == null) continue;
          d += (v - means[m.key]) ** 2;
          n += 1;
        }
        if (!n) continue;
        const score = d / n;
        if (!best || score < best.score) best = { id: t.id, score };
      }
      idealTrackId = best?.id || null;
    }

    return {
      cluster,
      members,
      albumAbs,
      albumPct,
      artistAbs,
      artistPct,
      uniqueAlbumCount: albumMap.size,
      uniqueArtistCount: artistMap.size,
      idealTrackId,
    };
  }, [tracks, points, clusters, code]);

  useEffect(() => {
    if (!data.idealTrackId) {
      setIdealTrack(null);
      return;
    }
    fetchTrackDetails(data.idealTrackId)
      .then(setIdealTrack)
      .catch(() => setIdealTrack(null));
  }, [data.idealTrackId]);

  if (loading) return <div className="cluster-detail-page">Loading cluster details…</div>;
  if (error) return <div className="cluster-detail-page">Could not load cluster: {error}</div>;

  const title = data.cluster?.name || (code === '-1' ? 'unclustered' : code);

  return (
    <main className="cluster-detail-page">
      <div className="cluster-detail-topbar">
        <button type="button" onClick={() => navigate(-1)} className="cluster-back-btn">
          ← Back
        </button>
        <Link to="/clusters" className="cluster-back-link">
          All clusters
        </Link>
      </div>

      <section className="cluster-hero">
        <h1>{title}</h1>
        <p>{data.cluster?.description || 'No cluster description available yet.'}</p>
      </section>

      <section className="cluster-panel">
        <h2>Metric distribution</h2>
        <div className="distribution-counts">
          <div className="dist-card">
            <span>Different albums</span>
            <strong>{data.uniqueAlbumCount.toLocaleString()}</strong>
          </div>
          <div className="dist-card">
            <span>Different artists</span>
            <strong>{data.uniqueArtistCount.toLocaleString()}</strong>
          </div>
        </div>
      </section>

      <section className="cluster-panel charts-grid">
        <article>
          <h3>Albums (absolute)</h3>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={data.albumAbs}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" tick={{ fill: '#b8c0dc', fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={72} />
              <YAxis tick={{ fill: '#b8c0dc' }} />
              <Tooltip />
              <Bar dataKey="count" fill="#8ab4ff" />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article>
          <h3>Albums (percent)</h3>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={data.albumPct}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" tick={{ fill: '#b8c0dc', fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={72} />
              <YAxis tick={{ fill: '#b8c0dc' }} />
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
              <Bar dataKey="percent" fill="#76e39f" />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article>
          <h3>Artists (absolute)</h3>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={data.artistAbs}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" tick={{ fill: '#b8c0dc', fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={72} />
              <YAxis tick={{ fill: '#b8c0dc' }} />
              <Tooltip />
              <Bar dataKey="count" fill="#ffb669" />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article>
          <h3>Artists (percent)</h3>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={data.artistPct}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" tick={{ fill: '#b8c0dc', fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={72} />
              <YAxis tick={{ fill: '#b8c0dc' }} />
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
              <Bar dataKey="percent" fill="#da9cff" />
            </BarChart>
          </ResponsiveContainer>
        </article>
      </section>

      <section className="cluster-panel">
        <h2>Representative track (closest to cluster mean)</h2>
        {!idealTrack ? (
          <p className="cluster-muted">No representative track found.</p>
        ) : (
          <article className="ideal-track-card">
            <h3>{idealTrack.name}</h3>
            <p>
              <strong>Artist:</strong> {idealTrack.artist_name}
            </p>
            <p>
              <strong>Album:</strong> {idealTrack.album_title}
            </p>
            <p className="ideal-lyrics">{idealTrack.lyrics || 'No lyrics for this track.'}</p>
          </article>
        )}
      </section>
    </main>
  );
}

