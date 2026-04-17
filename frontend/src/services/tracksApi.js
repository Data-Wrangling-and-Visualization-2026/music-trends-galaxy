/**
 * Data access for the map and track views.
 *
 * Mock mode: reads /mock/galaxy-data.json — updated to match normalized DB models
 * (dim_albums, dim_artists, preprocessed_tracks, dim_clusters, fact_galaxy_points).
 * API mode: GET /api/galaxy/points, /api/galaxy/tracks, GET /api/tracks/:id
 *
 * Real API by default. Set VITE_USE_MOCK=true in .env to use static JSON only.
 */
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
//const USE_MOCK = true;

async function getMockData() {
  const res = await fetch('/mock/galaxy-data.json');
  if (!res.ok) throw new Error('Failed to load mock data');
  return res.json();
}

/**
 * Safe parsing of artist_ids, since in the DB (and mock) it is a string '[ "ar_001" ]'
 */
function _parseArtistIds(rawIds) {
  if (!rawIds) return [];
  if (typeof rawIds === 'string') {
    try {
      const parsed = JSON.parse(rawIds);
      if (Array.isArray(parsed)) {
        return parsed.map((x) => String(x).trim()).filter(Boolean);
      }
    } catch {
      let s = rawIds.trim();
      if (s.startsWith('[') && s.endsWith(']')) s = s.slice(1, -1);
      return s
        .split(',')
        .map((x) => x.trim().replace(/^['"]|['"]$/g, ''))
        .filter((x) => x && x.toLowerCase() !== 'none');
    }
  }
  return Array.isArray(rawIds)
    ? rawIds.map((x) => String(x).trim()).filter(Boolean)
    : [];
}

/** Galaxy /tracks row: ensure ``artist_ids`` is always a string[] for filters. */
function normalizeGalaxyTrackRow(t) {
  if (!t || typeof t !== 'object') return t;
  return {
    ...t,
    artist_ids: _parseArtistIds(t.artist_ids),
  };
}

function _albumTitle(data, albumId) {
  const al = (data.dim_albums || []).find((a) => a.id === albumId);
  return al?.title || 'Unknown Album';
}

function _artistNames(data, rawIds) {
  const ids = _parseArtistIds(rawIds);
  if (!ids.length) return '';
  return ids
    .map((id) => (data.dim_artists || []).find((a) => a.id === id)?.name)
    .filter(Boolean)
    .join(', ');
}

/** Mirrors backend ``fact_track_audio_features`` / ``_pick_audio`` (mock: preprocessed_tracks columns). */
function audioFeaturesFromPreprocessedTrack(t) {
  if (!t) return null;
  return {
    danceability: t.danceability ?? null,
    energy: t.energy ?? null,
    key: t.key ?? null,
    loudness: t.loudness ?? null,
    mode: t.mode ?? null,
    speechiness: t.speechiness ?? null,
    acousticness: t.acousticness ?? null,
    instrumentalness: t.instrumentalness ?? null,
    liveness: t.liveness ?? null,
    valence: t.valence ?? null,
    tempo: t.tempo ?? null,
    time_signature: t.time_signature ?? null,
  };
}

/**
 * Align mock galaxy points with backend GalaxyPoint + normalizeApiGalaxyPoint.
 */
function buildMockGalaxyPointsList(data) {
  const trackById = new Map((data.preprocessed_tracks || []).map((t) => [t.id, t]));

  return (data.fact_galaxy_points || []).map((pt) => {
    const tid = pt.track_id;
    const t = trackById.get(tid);

    const base = {
      ...pt,
      id: tid,
      name: t?.name,
      album: t?.album || (t ? _albumTitle(data, t.album_id) : undefined),
      artists: t?.artists || (t ? _artistNames(data, t.artist_ids) : undefined),
      danceability: t?.danceability,
      acousticness: t?.acousticness,
      audio_features: audioFeaturesFromPreprocessedTrack(t),
    };
    return normalizeApiGalaxyPoint(base);
  });
}

/**
 * Mock track list shaped like GET /api/galaxy/tracks (merge tracks + galaxy point coords).
 */
function buildMockTracksList(data) {
  const pointById = new Map((data.fact_galaxy_points || []).map((p) => [p.track_id, p]));
  return (data.preprocessed_tracks || []).map((t) => {
    const gp = pointById.get(t.id);
    return {
      id: t.id,
      name: t.name || '',
      album: t.album || _albumTitle(data, t.album_id),
      album_id: t.album_id,
      artists: t.artists || _artistNames(data, t.artist_ids) || undefined,
      artist_ids: _parseArtistIds(t.artist_ids),
      year: t.year,
      x: gp ? Number(gp.x) : 0,
      y: gp ? Number(gp.y) : 0,
      z: gp ? Number(gp.z) : 0,
      cluster_code: gp?.cluster_code ?? null,
    };
  });
}

function _mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher–Yates shuffle of indices with seeded RNG (matches “random N” intent for mock data). */
function _shuffledFirstKIndices(n, k, seed) {
  const idx = Array.from({ length: n }, (_, i) => i);
  const rnd = _mulberry32(seed >>> 0);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return idx.slice(0, k);
}

function _mockSubsetPoints(fullPoints, limit, sample, seed) {
  const n = fullPoints.length;
  if (n <= limit) return fullPoints;
  if (sample === 'first') return fullPoints.slice(0, limit);
  const order = _shuffledFirstKIndices(n, limit, seed);
  return order.map((i) => fullPoints[i]);
}

/** Default map load: 10k points, random sample (same as backend defaults). */
export const DEFAULT_GALAXY_LOAD = { limit: 5000, sample: 'random', seed: 42 };

/**
 * HSL → RGB (h in degrees 0–360, s/l in 0–1). Returns r,g,b in 0–1.
 * Wider gamut than linear RGB mix — used for valence/energy star colors.
 */
function hslToRgb01(h, s, l) {
  const hn = (((h % 360) + 360) % 360) / 360;
  if (s === 0) return [l, l, l];
  const hue2rgb = (p, q, t) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return [hue2rgb(p, q, hn + 1 / 3), hue2rgb(p, q, hn), hue2rgb(p, q, hn - 1 / 3)];
}

/**
 * Map valence × energy to hue/sat/light so colors span most of the hue wheel with strong saturation.
 * Cross-terms separate nearby (v,e) pairs for clearer visual boundaries between tracks.
 */
function valenceEnergyToHsl(v, e) {
  const hue = (v * 312 + e * 108 + 180 * v * (1 - e) + 90 * e * (1 - v)) % 360;
  const sat = 0.62 + 0.36 * Math.abs(v - e);
  const light = 0.4 + 0.28 * (0.35 + 0.65 * e) * (0.5 + 0.5 * v);
  return [hue, Math.min(1, Math.max(0, sat)), Math.min(1, Math.max(0, light))];
}

/** RGB 0–1 from valence/energy — same math as backend `generate_rgb.rgb_from_valence_energy`. */
export function rgb01FromValenceEnergy(valence, energy) {
  const v = valence == null ? 0.5 : Math.max(0, Math.min(1, Number(valence)));
  const e = energy == null ? 0.5 : Math.max(0, Math.min(1, Number(energy)));
  const [h, s, l] = valenceEnergyToHsl(v, e);
  return hslToRgb01(h, s, l);
}

/** Match backend `rgb_from_valence_energy` — hex when API has no explicit color. */
function rgbFromValenceEnergy(valence, energy) {
  return rgb01ToHex(rgb01FromValenceEnergy(valence, energy));
}

function rgb01ToHex(rgb) {
  const x = (t) =>
    Math.round(Math.max(0, Math.min(255, t * 255)))
      .toString(16)
      .padStart(2, '0');
  return `#${x(rgb[0])}${x(rgb[1])}${x(rgb[2])}`;
}

function parseHexToRgb01(hex) {
  if (!hex || typeof hex !== 'string') return null;
  let h = hex.replace('#', '').trim();
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  }
  if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

/**
 * UI color on dim_clusters: column `color` or legacy `metrics_json.color` (mock).
 */
export function resolveClusterHex(clusters, code) {
  if (!clusters?.length) return null;
  const key =
    code == null || code === '' ? '-1' : String(code);
  const row = clusters.find((c) => String(c.code) === key);
  if (!row) return null;
  return row.color || row.metrics_json?.color || null;
}

/**
 * Final map color: mostly cluster, valence/energy only tints variation inside the cluster.
 * @param clusterWeight — how much cluster dominates (default 0.78)
 */
export function blendClusterAndTrackColor(clusterHex, valence, energy, clusterWeight = 0.78) {
  const v = valence == null ? 0.5 : Math.max(0, Math.min(1, Number(valence)));
  const e = energy == null ? 0.5 : Math.max(0, Math.min(1, Number(energy)));
  const pointRgb = rgb01FromValenceEnergy(v, e);
  const clusterRgb = parseHexToRgb01(clusterHex);
  const w = Math.min(0.92, Math.max(0.55, clusterWeight));
  if (!clusterRgb) return rgb01ToHex(pointRgb);
  const mix = (i) => clusterRgb[i] * w + pointRgb[i] * (1 - w);
  return rgb01ToHex([mix(0), mix(1), mix(2)]);
}

/**
 * Конвертирует HEX в HSL.
 * Возвращает объект: { h: 0-360, s: 0-100, l: 0-100 }
 */
function hexToHsl(hex) {
  const cleanHex = hex.replace('#', '');
  const r = parseInt(cleanHex.substring(0, 2), 16) / 255;
  const g = parseInt(cleanHex.substring(2, 4), 16) / 255;
  const b = parseInt(cleanHex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;

  if (max === min) {
    h = s = 0; // Оттенки серого
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
  };
}

/**
 * Ideal color for text on top of the background (based on perceptual brightness)
 */
function getContrastTextColor(hex) {
  const cleanHex = hex.replace('#', '');
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);
  
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000000' : '#FFFFFF';
}

/**
 * Backend GalaxyPoint uses `id` as track id; canvas expects track_id, color, title, artist, musical_features.
 */
function normalizeApiGalaxyPoint(p) {
  const track_id = p.track_id ?? p.id;
  const valence = p.valence ?? 0.5;
  const energy = p.energy ?? 0.5;
  const color = p.color || rgbFromValenceEnergy(valence, energy);
  
  const title = p.name || 'Unknown Track';
  const artist =
    typeof p.artists === 'string' && p.artists.trim()
      ? p.artists.split(',')[0]?.trim() || p.artists
      : 'Unknown Artist';
  const album = p.album || 'Unknown Album';

  const audio =
    p.audio_features && typeof p.audio_features === 'object' ? { ...p.audio_features } : {};
  if (p.danceability != null && audio.danceability == null) audio.danceability = p.danceability;
  if (p.acousticness != null && audio.acousticness == null) audio.acousticness = p.acousticness;

  const musical_features = {
    ...audio,
    energy: p.energy ?? audio.energy ?? 0,
    valence: p.valence ?? audio.valence ?? 0,
    danceability: p.danceability ?? audio.danceability ?? 0,
    acousticness: p.acousticness ?? audio.acousticness ?? 0,
    lyrical_intensity: p.lyrical_intensity,
    lyrical_mood: p.lyrical_mood,
  };

  return {
    ...p,
    track_id,
    color,
    title,
    artist,
    album,
    audio_features: audio,
    musical_features,
  };
}

/**
 * @param {{ limit?: number, sample?: 'first'|'random', seed?: number }} [options]
 */
export async function fetchGalaxyPoints(options = {}) {
  const limit = options.limit ?? DEFAULT_GALAXY_LOAD.limit;
  const sample = options.sample ?? DEFAULT_GALAXY_LOAD.sample;
  const seed = options.seed ?? DEFAULT_GALAXY_LOAD.seed;
  if (USE_MOCK) {
    const data = await getMockData();
    const full = buildMockGalaxyPointsList(data);
    const list = _mockSubsetPoints(full, limit, sample, seed);
    return list.map(normalizeApiGalaxyPoint);
  }
  const params = new URLSearchParams({
    limit: String(limit),
    sample,
    seed: String(seed),
  });
  const res = await fetch(`/api/galaxy/points?${params}`);
  if (!res.ok) throw new Error('Failed to load galaxy points');
  const data = await res.json();
  const list = data.points ?? [];
  return list.map(normalizeApiGalaxyPoint);
}

export async function fetchArtists() {
  if (USE_MOCK) {
    const data = await getMockData();
    return data.dim_artists || [];
  }
  try {
    const res = await fetch('/api/galaxy/artists');
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchAlbums() {
  if (USE_MOCK) {
    const data = await getMockData();
    return data.dim_albums || [];
  }
  try {
    const res = await fetch('/api/galaxy/albums');
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

/**
 * Track rows aligned with ``fetchGalaxyPoints`` when given the same options.
 * @param {{ limit?: number, sample?: 'first'|'random', seed?: number }} [options]
 */
export async function fetchAllTracks(options = {}) {
  const limit = options.limit ?? DEFAULT_GALAXY_LOAD.limit;
  const sample = options.sample ?? DEFAULT_GALAXY_LOAD.sample;
  const seed = options.seed ?? DEFAULT_GALAXY_LOAD.seed;
  if (USE_MOCK) {
    const data = await getMockData();
    const fullPts = buildMockGalaxyPointsList(data);
    const pts = _mockSubsetPoints(fullPts, limit, sample, seed);
    const idSet = new Set(pts.map((p) => p.track_id));
    return buildMockTracksList(data).filter((t) => idSet.has(t.id));
  }
  const params = new URLSearchParams({
    limit: String(limit),
    sample,
    seed: String(seed),
  });
  const res = await fetch(`/api/galaxy/tracks?${params}`);
  if (!res.ok) throw new Error('Failed to load galaxy tracks');
  const data = await res.json();
  const rows = data.tracks ?? [];
  return rows.map(normalizeGalaxyTrackRow);
}

export async function fetchTrackDetails(trackId) {
  if (USE_MOCK) {
    const data = await getMockData();

    const track = data.preprocessed_tracks.find((t) => t.id === trackId);
    if (!track) throw new Error('Track not found');

    const artistLine = track.artists || _artistNames(data, track.artist_ids) || 'Unknown Artist';
    const album = data.dim_albums.find((al) => al.id === track.album_id);
    const point = data.fact_galaxy_points.find((p) => p.track_id === trackId);
    
    let clusterColor = null;
    if (point && point.cluster_code) {
      const code = point.cluster_code;
      const cluster = data.dim_clusters.find((c) => c.code === code);
      if (cluster && cluster.metrics_json?.color) {
        clusterColor = cluster.metrics_json.color;
      }
    }

    const v = point?.valence ?? track.valence ?? 0.5;
    const e = point?.energy ?? track.energy ?? 0.5;
    const color = clusterColor || rgbFromValenceEnergy(v, e);

    const artistIdsArray = _parseArtistIds(track.artist_ids);
    const clusterCode = point?.cluster_code ?? null;
    const clusterRow =
      clusterCode != null
        ? (data.dim_clusters || []).find((c) => String(c.code) === String(clusterCode))
        : null;
    const artistRows = artistIdsArray
      .map((id) => (data.dim_artists || []).find((a) => String(a.id) === String(id)))
      .filter(Boolean);

    return {
      id: track.id,
      name: track.name,
      artist_name: artistLine,
      album_title: album?.title || track.album || 'Single',
      album_id: track.album_id,
      year: track.year,
      release_date: track.release_date,
      duration_ms: track.duration_ms,
      lyrics: track.lyrics || '',
      lyrics_source: track.lyrics_source || 'mock',
      artists: artistIdsArray
        .map((id) => data.dim_artists.find((a) => a.id === id)?.name)
        .filter(Boolean),
      artist_ids: artistIdsArray,
      artists_detail: artistRows.map((a) => ({
        id: a.id,
        name: a.name,
        track_count: a.track_count ?? null,
        color: a.color ?? a.metrics_json?.cover_color ?? null,
        metrics: a.metrics_json ?? null,
        description: a.description ?? null,
      })),
      album: album
        ? {
            id: album.id,
            title: album.title,
            track_count: album.track_count ?? null,
            color: album.color ?? album.metrics_json?.theme_color ?? null,
            metrics: album.metrics_json ?? null,
            description: album.description ?? null,
            cover_image_id: album.cover_image_id ?? null,
          }
        : null,
      cluster: clusterRow
        ? {
            code: String(clusterRow.code),
            name: clusterRow.name ?? String(clusterRow.code),
            description: clusterRow.description ?? null,
            track_count: clusterRow.track_count ?? null,
            color: clusterRow.color ?? clusterRow.metrics_json?.color ?? null,
            metrics: clusterRow.metrics_json ?? null,
          }
        : null,
      musical_features: {
        energy: track.energy,
        valence: track.valence,
        danceability: track.danceability,
        acousticness: track.acousticness,
        lyrical_intensity: point?.lyrical_intensity,
        lyrical_mood: point?.lyrical_mood,
      },
      color,
      galaxy: point
        ? {
            x: point.x,
            y: point.y,
            z: point.z,
            cluster_code: point.cluster_code,
            cluster_name: clusterRow?.name ?? null,
          }
        : null,
    };
  }

  const res = await fetch(`/api/tracks/${encodeURIComponent(trackId)}`);
  if (!res.ok) throw new Error('Failed to fetch track details');
  return res.json();
}

export async function fetchClusters() {
  if (USE_MOCK) {
    const data = await getMockData();
    return data.dim_clusters || [];
  }

  try {
    const res = await fetch('/api/galaxy/clusters');
    if (!res.ok) {
      console.warn('[tracksApi] GET /api/galaxy/clusters failed:', res.status, res.statusText);
      return [];
    }
    const data = await res.json();
    return data.clusters || [];
  } catch (error) {
    console.warn('[tracksApi] fetchClusters:', error);
    return [];
  }
}

export { USE_MOCK, rgbFromValenceEnergy };