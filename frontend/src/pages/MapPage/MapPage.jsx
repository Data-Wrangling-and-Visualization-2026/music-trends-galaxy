import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Filter } from 'lucide-react';
import {
  fetchGalaxyPoints,
  fetchArtists,
  fetchAllTracks,
  fetchAlbums,
  fetchClusters,
  blendClusterAndTrackColor,
  resolveClusterHex,
  DEFAULT_GALAXY_LOAD,
} from '../../services/tracksApi';

import Sidebar from '../../components/MapSidebar/Sidebar';
import GalaxyCanvas from '../../components/GalaxyCanvas/GalaxyCanvas';
import AnalysisPanel from '../../components/RightSideBar/AnalysisPanel';
import ArtistFilter from '../../components/Filters/ArtistFilter/ArtistFilter';
import AlbumFilter from '../../components/Filters/AlbumFilter/AlbumFilter';
import GenreFilter from '../../components/Filters/GenreFilter/GenreFilter';
import ClusterFilter from '../../components/Filters/ClusterFilter/ClusterFilter';
import YearFilter from '../../components/Filters/YearFilter/YearFilter';

import './MapPage.css';
import {
  logMapFetch,
  logMapCompute,
  logMapFirstFrames,
} from '../../utils/mapPerf';

const MAP_PAGE_CACHE = {
  didLoad: false,
  loadSpec: null,
  formLimit: null,
  formSample: null,
  points: [],
  artists: [],
  tracks: [],
  albums: [],
  clusters: [],
  loadError: null,
  selectedTrackIds: [],
  isSidebarOpen: false,
  selectedArtistIds: [],
  selectedAlbumIds: [],
  selectedGenreTags: [],
  selectedClusterCodes: [],
  selectedYearIds: [],
};

function clampInt(n, min, max) {
  const x = Number.parseInt(String(n), 10);
  if (Number.isNaN(x)) return min;
  return Math.min(max, Math.max(min, x));
}

/** Stable string for cluster filter (null/empty → unclustered bucket ``-1``). */
function normalizedClusterCode(raw) {
  if (raw == null || raw === '') return '-1';
  return String(raw);
}

function extractGenres(row) {
  const direct = Array.isArray(row?.genres) ? row.genres.filter(Boolean) : [];
  if (direct.length > 0) return direct;
  const fromMetrics = Array.isArray(row?.metrics_json?.genres)
    ? row.metrics_json.genres.filter(Boolean)
    : [];
  if (fromMetrics.length > 0) return fromMetrics;
  const nested = Array.isArray(row?.metrics_json?.metrics?.genres)
    ? row.metrics_json.metrics.genres.filter(Boolean)
    : [];
  return nested;
}

function normalizeGenreTag(v) {
  return String(v ?? '')
    .trim()
    .toLowerCase();
}

function isSameLoadSpec(a, b) {
  if (!a || !b) return false;
  return (
    Number(a.limit) === Number(b.limit) &&
    String(a.sample) === String(b.sample) &&
    Number(a.seed) === Number(b.seed)
  );
}

/** Genre tags from dim rows (API ``genres`` or mock ``metrics_json.genres``). */
function genresForTrack(tr, artistsList, albumsList) {
  if (!tr) return new Set();
  const out = new Set();
  const al = albumsList.find((x) => String(x.id) === String(tr.album_id));
  extractGenres(al).forEach((x) => {
    const g = normalizeGenreTag(x);
    if (g) out.add(g);
  });
  const aids = tr.artist_ids;
  if (Array.isArray(aids)) {
    aids.forEach((aid) => {
      const ar = artistsList.find((x) => String(x.id) === String(aid));
      extractGenres(ar).forEach((x) => {
        const g = normalizeGenreTag(x);
        if (g) out.add(g);
      });
    });
  }
  return out;
}

export default function MapPage() {
  const [points, setPoints] = useState(() => MAP_PAGE_CACHE.points || []);
  const [artists, setArtists] = useState(() => MAP_PAGE_CACHE.artists || []);
  const [tracks, setTracks] = useState(() => MAP_PAGE_CACHE.tracks || []);
  const [albums, setAlbums] = useState(() => MAP_PAGE_CACHE.albums || []);
  const [clusters, setClusters] = useState(() => MAP_PAGE_CACHE.clusters || []);
  const [loadError, setLoadError] = useState(() => MAP_PAGE_CACHE.loadError || null);
  const [dataLoading, setDataLoading] = useState(() => !MAP_PAGE_CACHE.didLoad);

  const [selectedTrackIds, setSelectedTrackIds] = useState(() => MAP_PAGE_CACHE.selectedTrackIds || []);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => MAP_PAGE_CACHE.isSidebarOpen || false);

  const [selectedArtistIds, setSelectedArtistIds] = useState(() => MAP_PAGE_CACHE.selectedArtistIds || []);
  const [selectedAlbumIds, setSelectedAlbumIds] = useState(() => MAP_PAGE_CACHE.selectedAlbumIds || []);
  const [selectedGenreTags, setSelectedGenreTags] = useState(() => MAP_PAGE_CACHE.selectedGenreTags || []);
  const [selectedClusterCodes, setSelectedClusterCodes] = useState(() => MAP_PAGE_CACHE.selectedClusterCodes || []);
  const [selectedYearIds, setSelectedYearIds] = useState(() => MAP_PAGE_CACHE.selectedYearIds || []);

  const [loadSpec, setLoadSpec] = useState(() => MAP_PAGE_CACHE.loadSpec || { ...DEFAULT_GALAXY_LOAD });
  const [formLimit, setFormLimit] = useState(() => MAP_PAGE_CACHE.formLimit ?? DEFAULT_GALAXY_LOAD.limit);
  const [formSample, setFormSample] = useState(() => MAP_PAGE_CACHE.formSample ?? DEFAULT_GALAXY_LOAD.sample);

  const applyDataset = useCallback(() => {
    setLoadSpec((prev) => {
      const next = {
        limit: clampInt(formLimit, 1, 120_000),
        sample: formSample,
        seed:
          formSample === 'random'
            ? prev.seed ?? DEFAULT_GALAXY_LOAD.seed
            : DEFAULT_GALAXY_LOAD.seed,
      };
      return isSameLoadSpec(prev, next) ? prev : next;
    });
  }, [formLimit, formSample]);

  const reshuffleRandom = useCallback(() => {
    setFormSample('random');
    setLoadSpec((prev) => ({
      ...prev,
      sample: 'random',
      seed: (prev.seed ?? DEFAULT_GALAXY_LOAD.seed) + 1,
    }));
  }, []);

  useEffect(() => {
    if (MAP_PAGE_CACHE.didLoad && isSameLoadSpec(MAP_PAGE_CACHE.loadSpec, loadSpec)) {
      setPoints(MAP_PAGE_CACHE.points || []);
      setArtists(MAP_PAGE_CACHE.artists || []);
      setTracks(MAP_PAGE_CACHE.tracks || []);
      setAlbums(MAP_PAGE_CACHE.albums || []);
      setClusters(MAP_PAGE_CACHE.clusters || []);
      setLoadError(MAP_PAGE_CACHE.loadError || null);
      setDataLoading(false);
      return;
    }

    setLoadError(null);
    setDataLoading(true);
    const tLoad = performance.now();
    Promise.all([
      fetchGalaxyPoints(loadSpec),
      fetchArtists(),
      fetchAllTracks(loadSpec),
      fetchAlbums(),
      fetchClusters(),
    ])
      .then(([p, art, t, alb, cl]) => {
        const msNet = performance.now() - tLoad;
        logMapFetch('Promise.all (5 запросов: сеть + JSON.parse)', msNet, {
          points: p.length,
          tracks: t.length,
          clusters: cl.length,
        });
        setPoints(p);
        setArtists(art);
        setTracks(t);
        setAlbums(alb);
        setClusters(cl);
        MAP_PAGE_CACHE.didLoad = true;
        MAP_PAGE_CACHE.loadSpec = { ...loadSpec };
        MAP_PAGE_CACHE.points = p;
        MAP_PAGE_CACHE.artists = art;
        MAP_PAGE_CACHE.tracks = t;
        MAP_PAGE_CACHE.albums = alb;
        MAP_PAGE_CACHE.clusters = cl;
        MAP_PAGE_CACHE.loadError = null;
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            logMapFirstFrames(performance.now() - tLoad);
          });
        });
      })
      .catch((err) => {
        console.error(err);
        const msg = err?.message || 'Failed to load map data. Is the API running?';
        setLoadError(msg);
        MAP_PAGE_CACHE.didLoad = false;
        MAP_PAGE_CACHE.loadError = msg;
      })
      .finally(() => setDataLoading(false));
  }, [loadSpec]);

  useEffect(() => {
    MAP_PAGE_CACHE.loadSpec = { ...loadSpec };
    MAP_PAGE_CACHE.formLimit = formLimit;
    MAP_PAGE_CACHE.formSample = formSample;
    MAP_PAGE_CACHE.selectedTrackIds = selectedTrackIds;
    MAP_PAGE_CACHE.isSidebarOpen = isSidebarOpen;
    MAP_PAGE_CACHE.selectedArtistIds = selectedArtistIds;
    MAP_PAGE_CACHE.selectedAlbumIds = selectedAlbumIds;
    MAP_PAGE_CACHE.selectedGenreTags = selectedGenreTags;
    MAP_PAGE_CACHE.selectedClusterCodes = selectedClusterCodes;
    MAP_PAGE_CACHE.selectedYearIds = selectedYearIds;
  }, [
    loadSpec,
    formLimit,
    formSample,
    selectedTrackIds,
    isSidebarOpen,
    selectedArtistIds,
    selectedAlbumIds,
    selectedGenreTags,
    selectedClusterCodes,
    selectedYearIds,
  ]);

  const artistsForPicker = useMemo(() => {
    if (artists.length > 0) {
      return artists.map((a) => ({ id: String(a.id), name: a.name ?? a.id }));
    }
    const m = new Map();
    for (const t of tracks) {
      const aids = t.artist_ids;
      if (!Array.isArray(aids)) continue;
      const parts =
        typeof t.artists === 'string'
          ? t.artists.split(',').map((s) => s.trim())
          : [];
      aids.forEach((id, i) => {
        const sid = String(id);
        if (!m.has(sid)) {
          m.set(sid, { id: sid, name: parts[i] || sid });
        }
      });
    }
    return [...m.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)));
  }, [artists, tracks]);

  const albumsForPicker = useMemo(() => {
    if (albums.length > 0) {
      return albums.map((a) => ({
        id: String(a.id),
        title: a.title ?? a.id,
      }));
    }
    const m = new Map();
    for (const t of tracks) {
      if (t.album_id == null) continue;
      const id = String(t.album_id);
      if (!m.has(id)) {
        m.set(id, { id, title: t.album || id });
      }
    }
    return [...m.values()].sort((a, b) => String(a.title).localeCompare(String(b.title)));
  }, [albums, tracks]);

  const pointsWithMetadata = useMemo(() => {
    const t0 = performance.now();
    const trackMap = new Map(tracks.map((t) => [t.id, t]));
    const artistMap = new Map(artistsForPicker.map((a) => [a.id, a.name]));
    const albumMap = new Map(albumsForPicker.map((a) => [a.id, a.title]));

    const rows = points.map((p) => {
      const track = trackMap.get(p.track_id);
      const title = p.title ?? track?.name ?? 'Unknown Track';

      let artist = p.artist;
      if (!artist && track) {
        if (Array.isArray(track.artist_ids) && track.artist_ids.length) {
          artist = track.artist_ids
            .map((id) => artistMap.get(String(id)))
            .filter(Boolean)
            .join(', ');
        }
        if (!artist && typeof track.artists === 'string' && track.artists.trim()) {
          artist = track.artists;
        }
      }
      if (!artist) artist = 'Unknown Artist';

      let album = p.album;
      if ((!album || album === 'Unknown Album') && track) {
        album =
          albumMap.get(String(track?.album_id)) ||
          track?.album ||
          'Unknown Album';
      }
      if (!album) album = 'Unknown Album';

      const musical_features =
        p.musical_features ??
        track?.musical_features ?? {
          energy: p.energy ?? 0,
          danceability: p.danceability ?? 0,
          valence: p.valence ?? 0,
          acousticness: p.acousticness ?? 0,
        };

      const v = p.valence ?? musical_features.valence ?? 0.5;
      const e = p.energy ?? musical_features.energy ?? 0.5;
      const clusterHex = resolveClusterHex(clusters, p.cluster_code);
      const color = blendClusterAndTrackColor(clusterHex, v, e, 0.78);

      return {
        ...p,
        title,
        artist,
        album,
        musical_features,
        color,
      };
    });
    logMapCompute('pointsWithMetadata', performance.now() - t0, { n: points.length });
    return rows;
  }, [points, tracks, artistsForPicker, albumsForPicker, clusters]);

  const genreTagOptions = useMemo(() => {
    const byNorm = new Map();
    for (const a of artists) {
      extractGenres(a).forEach((x) => {
        const norm = normalizeGenreTag(x);
        if (norm && !byNorm.has(norm)) byNorm.set(norm, String(x).trim());
      });
    }
    for (const b of albums) {
      extractGenres(b).forEach((x) => {
        const norm = normalizeGenreTag(x);
        if (norm && !byNorm.has(norm)) byNorm.set(norm, String(x).trim());
      });
    }
    return [...byNorm.entries()]
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([id, name]) => ({ id, name }));
  }, [artists, albums]);

  const clusterOptions = useMemo(
    () =>
      clusters.map((c) => {
        const codeStr = normalizedClusterCode(c.code);
        const isUnclustered = codeStr === '-1';
        return {
          id: codeStr,
          name: isUnclustered ? 'unclustered' : c.name || codeStr,
        };
      }),
    [clusters]
  );

  const yearOptions = useMemo(() => {
    const years = [...new Set(tracks.map((t) => t.year).filter((y) => y != null))].sort(
      (a, b) => a - b
    );
    return years.map((y) => ({ id: String(y), name: String(y) }));
  }, [tracks]);

  const filteredPoints = useMemo(() => {
    const trackMap = new Map(tracks.map((t) => [t.id, t]));
    let list = pointsWithMetadata;

    if (selectedArtistIds.length) {
      const want = new Set(selectedArtistIds.map((x) => String(x)));
      list = list.filter((p) => {
        const tr = trackMap.get(p.track_id);
        const ids = tr?.artist_ids;
        return (
          Array.isArray(ids) && ids.some((id) => want.has(String(id)))
        );
      });
    }
    if (selectedAlbumIds.length) {
      const want = new Set(selectedAlbumIds.map((x) => String(x)));
      list = list.filter((p) => {
        const tr = trackMap.get(p.track_id);
        return tr?.album_id != null && want.has(String(tr.album_id));
      });
    }
    if (selectedGenreTags.length) {
      const wantGenres = new Set(selectedGenreTags.map(normalizeGenreTag).filter(Boolean));
      list = list.filter((p) => {
        const tr = trackMap.get(p.track_id);
        const gs = genresForTrack(tr, artists, albums);
        for (const tag of wantGenres) {
          if (gs.has(tag)) return true;
        }
        return false;
      });
    }
    if (selectedClusterCodes.length) {
      const want = new Set(selectedClusterCodes.map((x) => String(x)));
      list = list.filter((p) => want.has(normalizedClusterCode(p.cluster_code)));
    }
    if (selectedYearIds.length) {
      list = list.filter((p) => {
        const tr = trackMap.get(p.track_id);
        return tr?.year != null && selectedYearIds.includes(String(tr.year));
      });
    }
    return list;
  }, [
    pointsWithMetadata,
    tracks,
    selectedArtistIds,
    selectedAlbumIds,
    selectedGenreTags,
    artists,
    albums,
    selectedClusterCodes,
    selectedYearIds,
  ]);

  const filtersActive = useMemo(
    () =>
      selectedArtistIds.length > 0 ||
      selectedAlbumIds.length > 0 ||
      selectedGenreTags.length > 0 ||
      selectedClusterCodes.length > 0 ||
      selectedYearIds.length > 0,
    [
      selectedArtistIds,
      selectedAlbumIds,
      selectedGenreTags,
      selectedClusterCodes,
      selectedYearIds,
    ]
  );

  const emphasizedTrackIds = useMemo(() => {
    if (!filtersActive) return null;
    return new Set(filteredPoints.map((p) => p.track_id));
  }, [filtersActive, filteredPoints]);

  const selectedTracksData = useMemo(() => 
    selectedTrackIds.map(id => pointsWithMetadata.find(p => p.track_id === id)).filter(Boolean)
  , [selectedTrackIds, pointsWithMetadata]);

  const handlePointClick = (id) => {
    setSelectedTrackIds(prev => prev.includes(id) ? prev : [id, ...prev]);
  };

  return (
    <div className={`map-page-layout ${selectedTrackIds.length > 0 ? 'panel-active' : ''}`}>
      <aside
        id="map-filters-aside"
        className={`map-filters-aside ${isSidebarOpen ? 'open' : ''}`}
        aria-hidden={!isSidebarOpen}
      >
        <Sidebar
          variant="docked"
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          title="Filters"
        >
          <ArtistFilter
            artists={artistsForPicker}
            selectedArtistIds={selectedArtistIds}
            onSelect={(id) =>
              setSelectedArtistIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
            }
            onRemove={(id) => setSelectedArtistIds((prev) => prev.filter((x) => x !== id))}
          />
          <AlbumFilter
            albums={albumsForPicker}
            selectedAlbumIds={selectedAlbumIds}
            onSelect={(id) =>
              setSelectedAlbumIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
            }
            onRemove={(id) => setSelectedAlbumIds((prev) => prev.filter((x) => x !== id))}
          />
          <GenreFilter
            genres={genreTagOptions}
            selectedGenreTags={selectedGenreTags}
            onSelect={(tag) =>
              setSelectedGenreTags((prev) => (prev.includes(tag) ? prev : [...prev, tag]))
            }
            onRemove={(tag) => setSelectedGenreTags((prev) => prev.filter((x) => x !== tag))}
          />
          <ClusterFilter
            clusters={clusterOptions}
            selectedClusterCodes={selectedClusterCodes}
            onSelect={(id) =>
              setSelectedClusterCodes((prev) => (prev.includes(id) ? prev : [...prev, id]))
            }
            onRemove={(id) => setSelectedClusterCodes((prev) => prev.filter((x) => x !== id))}
          />
          <YearFilter
            years={yearOptions}
            selectedYearIds={selectedYearIds}
            onSelect={(id) =>
              setSelectedYearIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
            }
            onRemove={(id) => setSelectedYearIds((prev) => prev.filter((x) => x !== id))}
          />
        </Sidebar>
      </aside>

      <main className={`map-viewport ${dataLoading ? 'map-viewport--loading' : ''}`}>
        {loadError && (
          <div
            style={{
              position: 'absolute',
              zIndex: 10,
              top: 12,
              left: '50%',
              transform: 'translateX(-50%)',
              maxWidth: 'min(90vw, 480px)',
              padding: '10px 14px',
              background: '#3a1515',
              border: '1px solid #a44',
              borderRadius: 8,
              color: '#fcc',
              fontSize: 14,
            }}
          >
            {loadError}
          </div>
        )}

        <div className="map-controls-stack">
          <button
            type="button"
            className="map-filters-btn"
            onClick={() => setIsSidebarOpen((v) => !v)}
            aria-expanded={isSidebarOpen}
            aria-controls="map-filters-aside"
          >
            <Filter size={18} strokeWidth={2} aria-hidden />
            <span>Filters</span>
          </button>

          <div className="map-dataset-panel">
            <div className="map-dataset-panel__title">Load stars</div>
            <label className="map-dataset-field">
              <span>Count</span>
              <input
                type="number"
                min={1000}
                max={120000}
                step={1000}
                value={formLimit}
                onChange={(e) => setFormLimit(e.target.value)}
              />
            </label>
            <label className="map-dataset-field">
              <span>Order</span>
              <select
                value={formSample}
                onChange={(e) => setFormSample(e.target.value === 'random' ? 'random' : 'first')}
              >
                <option value="random">Random sample</option>
                <option value="first">First by id</option>
              </select>
            </label>
            <div className="map-dataset-actions">
              <button type="button" className="map-dataset-apply" onClick={applyDataset}>
                Apply
              </button>
              <button type="button" className="map-dataset-shuffle" onClick={reshuffleRandom}>
                New random
              </button>
            </div>
            <p className="map-dataset-hint">
              Loaded {points.length.toLocaleString()} points (max {loadSpec.limit.toLocaleString()}).
            </p>
          </div>
        </div>

        {dataLoading && <div className="map-loading-indicator" role="status" aria-live="polite" />}

        <GalaxyCanvas
          points={pointsWithMetadata}
          emphasizedTrackIds={emphasizedTrackIds}
          onPointClick={handlePointClick}
        />
      </main>

      <AnimatePresence initial={false}>
        {selectedTrackIds.length > 0 && (
          <motion.div
            key="analysis-shell"
            className="analysis-panel-shell"
            initial={{ width: 0 }}
            animate={{ width: 500 }}
            exit={{ width: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          >
            <AnalysisPanel
              selectedTracks={selectedTracksData}
              onCloseTrack={(id) => setSelectedTrackIds((prev) => prev.filter((t) => t !== id))}
              onCloseAll={() => setSelectedTrackIds([])}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}