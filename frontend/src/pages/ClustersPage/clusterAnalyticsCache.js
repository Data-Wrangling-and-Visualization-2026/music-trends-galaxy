import { fetchAllTracks, fetchClusters, fetchGalaxyPoints } from '../../services/tracksApi';

let _cache = null;
let _inflight = null;

function normCode(v) {
  if (v == null || v === '') return '-1';
  return String(v);
}

export function resetClusterAnalyticsCache() {
  _cache = null;
  _inflight = null;
}

export async function getClusterAnalyticsData() {
  if (_cache) return _cache;
  if (_inflight) return _inflight;

  _inflight = Promise.all([
    fetchClusters(),
    fetchAllTracks({ limit: 100000, sample: 'first', seed: 42 }),
    fetchGalaxyPoints({ limit: 100000, sample: 'first', seed: 42 }),
  ])
    .then(([clusters, tracks, points]) => {
      const pointByTrack = new Map((points || []).map((p) => [p.track_id, p]));
      const tracksByCluster = new Map();
      for (const t of tracks || []) {
        const p = pointByTrack.get(t.id);
        const code = normCode(t.cluster_code ?? p?.cluster_code);
        if (!tracksByCluster.has(code)) tracksByCluster.set(code, []);
        tracksByCluster.get(code).push(t);
      }
      _cache = {
        clusters: clusters || [],
        tracks: tracks || [],
        points: points || [],
        pointByTrack,
        tracksByCluster,
      };
      return _cache;
    })
    .finally(() => {
      _inflight = null;
    });

  return _inflight;
}

