import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getClusterAnalyticsData } from './clusterAnalyticsCache';
import './ClustersPage.css';

const METRIC_KEYS = [
  { key: 'energy', label: 'Energy' },
  { key: 'valence', label: 'Valence' },
  { key: 'lyrical_mood', label: 'Lyrical mood' },
  { key: 'lyrical_intensity', label: 'Lyrical intensity' },
];

function normCode(v) {
  if (v == null || v === '') return '-1';
  return String(v);
}

function to01(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(1, n));
}

function clusterColor(c) {
  return c?.color || c?.metrics_json?.color || '#8ab4ff';
}

export default function ClustersPage() {
  const [clusters, setClusters] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [points, setPoints] = useState([]);
  const [selected, setSelected] = useState([]);
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
      .catch((e) => setError(e?.message || 'Failed to load clusters'))
      .finally(() => setLoading(false));
  }, []);

  const statsByCode = useMemo(() => {
    const pointByTrack = new Map(points.map((p) => [p.track_id, p]));
    const acc = new Map();
    for (const t of tracks) {
      const p = pointByTrack.get(t.id);
      const code = normCode(t.cluster_code ?? p?.cluster_code);
      if (!acc.has(code)) {
        acc.set(code, {
          code,
          count: 0,
          sums: { energy: 0, valence: 0, lyrical_mood: 0, lyrical_intensity: 0 },
          ns: { energy: 0, valence: 0, lyrical_mood: 0, lyrical_intensity: 0 },
        });
      }
      const row = acc.get(code);
      row.count += 1;
      for (const m of METRIC_KEYS) {
        const v = to01(p?.[m.key]);
        if (v != null) {
          row.sums[m.key] += v;
          row.ns[m.key] += 1;
        }
      }
    }
    return acc;
  }, [tracks, points]);

  const clusterRows = useMemo(() => {
    const rows = (clusters || []).map((c) => {
      const code = normCode(c.code);
      const st = statsByCode.get(code);
      const means = {};
      for (const m of METRIC_KEYS) {
        means[m.key] = st && st.ns[m.key] ? st.sums[m.key] / st.ns[m.key] : null;
      }
      return {
        code,
        name: code === '-1' ? 'unclustered' : c.name || code,
        description: c.description || '',
        color: clusterColor(c),
        trackCount: st?.count ?? c.track_count ?? 0,
        means,
      };
    });
    rows.sort((a, b) => b.trackCount - a.trackCount);
    return rows;
  }, [clusters, statsByCode]);

  const selectedRows = useMemo(
    () => clusterRows.filter((r) => selected.includes(r.code)),
    [clusterRows, selected]
  );

  const dumbbellRows = useMemo(
    () =>
      METRIC_KEYS.map((m) => ({
        key: m.key,
        label: m.label,
        values: selectedRows
          .map((r) => ({ code: r.code, name: r.name, color: r.color, value: r.means[m.key] }))
          .filter((x) => x.value != null),
      })),
    [selectedRows]
  );

  const countHistogramData = useMemo(
    () =>
      selectedRows.map((r) => ({
        name: r.name,
        count: r.trackCount,
        color: r.color,
      })),
    [selectedRows]
  );

  const bubbleData = useMemo(
    () =>
      clusterRows
        .filter((r) => r.means.energy != null && r.means.valence != null)
        .map((r) => ({
          x: r.means.energy,
          y: r.means.valence,
          z: Math.max(40, Math.min(260, r.trackCount * 2.2)),
          name: r.name,
          count: r.trackCount,
          color: r.color,
        })),
    [clusterRows]
  );

  const toggleCluster = (code) => {
    setSelected((prev) => (prev.includes(code) ? prev.filter((x) => x !== code) : [...prev, code]));
  };

  if (loading) return <div className="clusters-page">Loading clusters…</div>;
  if (error) return <div className="clusters-page">Could not load clusters: {error}</div>;

  return (
    <main className="clusters-page">
      <section className="clusters-hero">
        <h1>Clusters</h1>
        <p>Select clusters to compare aggregate behavior and inspect descriptions.</p>
      </section>

      <section className="clusters-grid">
        {clusterRows.map((c) => (
          <article key={c.code} className={`cluster-card ${selected.includes(c.code) ? 'is-selected' : ''}`}>
            <label className="cluster-card-head">
              <input
                type="checkbox"
                checked={selected.includes(c.code)}
                onChange={() => toggleCluster(c.code)}
              />
              <span className="cluster-dot" style={{ background: c.color }} />
              <span className="cluster-name">{c.name}</span>
            </label>
            <p className="cluster-meta">{c.trackCount.toLocaleString()} tracks</p>
            <Link className="cluster-link" to={`/clusters/${encodeURIComponent(c.code)}`}>
              Open cluster details →
            </Link>
          </article>
        ))}
      </section>

      <section className="clusters-panel">
        <h2>Global cluster over musical energy and valence</h2>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 30 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="x" name="Energy" type="number" domain={[0, 1]} tick={{ fill: '#9fa8c6' }} />
              <YAxis dataKey="y" name="Valence" type="number" domain={[0, 1]} tick={{ fill: '#9fa8c6' }} />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  const d = active && payload?.[0]?.payload;
                  if (!d) return null;
                  return (
                    <div className="clusters-tooltip">
                      <strong>{d.name}</strong>
                      <div>Tracks: {d.count}</div>
                      <div>Energy: {d.x.toFixed(2)}</div>
                      <div>Valence: {d.y.toFixed(2)}</div>
                    </div>
                  );
                }}
              />
              <Scatter data={bubbleData} fill="#8ab4ff">
                {bubbleData.map((e) => (
                  <Cell key={e.name} fill={e.color} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>

      {selectedRows.length > 0 && (
        <>
          <section className="clusters-panel">
            <h2>Selected clusters: dumbbell metrics</h2>
            <div className="dumbbell-list">
              {dumbbellRows.map((row) => (
                <div key={row.key} className="dumbbell-row">
                  <div className="dumbbell-label">{row.label}</div>
                  <div className="dumbbell-track">
                    <div className="dumbbell-line" />
                    {row.values.map((v) => (
                      <span
                        key={v.code}
                        className="dumbbell-dot"
                        style={{ left: `${v.value * 100}%`, background: v.color }}
                        title={`${v.name}: ${v.value.toFixed(2)}`}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="clusters-panel">
            <h2>Selected clusters: track count histogram</h2>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={countHistogramData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="name" tick={{ fill: '#b8c0dc', fontSize: 12 }} interval={0} angle={-10} textAnchor="end" height={56} />
                  <YAxis tick={{ fill: '#b8c0dc' }} />
                  <Tooltip />
                  <Bar dataKey="count">
                    {countHistogramData.map((x) => (
                      <Cell key={x.name} fill={x.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="clusters-panel">
            <h2>Descriptions of selected clusters</h2>
            <div className="desc-list">
              {selectedRows.map((r) => (
                <article key={r.code} className="desc-card">
                  <h3>{r.name}</h3>
                  <p>{r.description || 'No description provided yet.'}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

