import React, { useMemo, useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import './ComparisonChart.css';

/** Same keys as backend ``fact_track_audio_features`` / ``_pick_audio``. */
/** Radar axes only (0–1 continuous-style). Mode is shown separately below the chart. */
const AUDIO_FEATURE_ORDER = [
  'danceability',
  'energy',
  'key',
  'loudness',
  'speechiness',
  'acousticness',
  'liveness',
  'valence',
  'tempo',
  'time_signature',
];

const FEATURE_LABELS = {
  danceability: 'Danceability',
  energy: 'Energy',
  key: 'Key',
  loudness: 'Loudness',
  speechiness: 'Speechiness',
  acousticness: 'Acousticness',
  liveness: 'Liveness',
  valence: 'Valence',
  tempo: 'Tempo',
  time_signature: 'Time signature',
};

const FEATURE_DESCRIPTIONS = {
  danceability:
    'How suitable the track is for dancing (0 = not at all, 1 = very danceable).',
  energy:
    'Perceived intensity and activity — fast, loud, noisy tracks score higher.',
  key:
    'Estimated musical key (0–11, C=0 … B=11), shown on the chart as 0–1 for comparison.',
  loudness:
    'Overall loudness in dB (typically negative); mapped to 0–1 for the radar.',
  speechiness:
    'Presence of spoken words; high values indicate speech-like tracks (e.g. podcasts, rap).',
  acousticness:
    'Confidence that the track is acoustic (not electric / synthetic).',
  liveness:
    'Audience presence — higher values suggest a live recording.',
  valence:
    'Musical positiveness — high values sound happier or more euphoric.',
  tempo:
    'Estimated tempo in BPM; mapped to 0–1 for the chart (≈0–200 BPM).',
  time_signature:
    'Estimated meter (e.g. 4/4); normalized for comparison across tracks.',
};

const LYRICAL_COPY = {
  mood: {
    title: 'Lyrical mood',
    body:
      'Derived score for the emotional tone of the lyrics (e.g. brighter vs darker). Higher values lean toward more positive or uplifted sentiment in the text.',
  },
  intensity: {
    title: 'Lyrical intensity',
    body:
      'How dense, urgent, or “loaded” the lyrics feel — repetition, emphasis, and emotional charge. Higher values mean a more intense lyrical delivery or content.',
  },
};

/** Map raw audio analysis value to 0–1 for a shared radar scale. */
function normalizeRadarValue(key, raw) {
  if (raw == null || raw === '') return null;
  const n = Number(raw);
  if (Number.isNaN(n)) return null;
  switch (key) {
    case 'key':
      return Math.max(0, Math.min(1, n / 11));
    case 'loudness':
      return Math.max(0, Math.min(1, (n + 60) / 60));
    case 'tempo':
      return Math.max(0, Math.min(1, n / 200));
    case 'time_signature':
      return Math.max(0, Math.min(1, (n - 3) / 5));
    default:
      return Math.max(0, Math.min(1, n));
  }
}

function getAudioField(track, key) {
  const af = track.audio_features;
  if (af && af[key] != null && af[key] !== '') return af[key];
  const mf = track.musical_features;
  if (mf && mf[key] != null && mf[key] !== '') return mf[key];
  return null;
}

function buildRadarRows(tracks) {
  const keys = AUDIO_FEATURE_ORDER.filter((k) =>
    tracks.some((t) => getAudioField(t, k) != null && getAudioField(t, k) !== '')
  );

  if (!keys.length) return { rows: [], activeKeys: [] };

  const rows = keys.map((key) => {
    const row = {
      subject: FEATURE_LABELS[key] || key,
      _key: key,
      fullMark: 1,
    };
    for (const t of tracks) {
      const raw = getAudioField(t, key);
      const norm = normalizeRadarValue(key, raw);
      row[t.track_id] = norm != null ? norm : 0;
    }
    return row;
  });

  return { rows, activeKeys: keys };
}

function formatTooltipValue(featureKey, tracks, dataKey) {
  const t = tracks.find((x) => x.track_id === dataKey);
  if (!t) return null;
  const raw = getAudioField(t, featureKey);
  if (raw == null) return '—';
  if (featureKey === 'key') return `Pitch class ${raw}`;
  if (featureKey === 'loudness') return `${Number(raw).toFixed(1)} dB`;
  if (featureKey === 'tempo') return `${Number(raw).toFixed(0)} BPM`;
  return typeof raw === 'number' ? raw.toFixed(3) : String(raw);
}

function formatModeRaw(raw) {
  if (raw == null || raw === '') return '—';
  const n = Number(raw);
  if (Number.isNaN(n)) return '—';
  return n ? 'Major' : 'Minor';
}

export default function ComparisonChart({ tracks }) {
  const [hoveredId, setHoveredId] = useState(null);

  const { rows, activeKeys } = useMemo(() => buildRadarRows(tracks || []), [tracks]);

  const hasLyric =
    tracks?.length &&
    tracks.some(
      (t) =>
        (t.musical_features?.lyrical_mood != null && !Number.isNaN(Number(t.musical_features.lyrical_mood))) ||
        (t.musical_features?.lyrical_intensity != null &&
          !Number.isNaN(Number(t.musical_features.lyrical_intensity)))
    );

  if (!tracks?.length) {
    return <p className="comparison-empty">Select tracks on the map to compare.</p>;
  }

  return (
    <div className="comparison-chart-root">
      <h4 className="comparison-subtitle">Audio features</h4>
      {!rows.length ? (
        <p className="comparison-empty subtle">
          No Spotify-style audio metrics on these points. Sync audio features or use mock data with
          preprocessed_tracks.
        </p>
      ) : (
        <>
          <div className="radar-chart-box">
            <ResponsiveContainer width="100%" height={380}>
              <RadarChart cx="50%" cy="52%" outerRadius="68%" data={rows}>
                <PolarGrid stroke="rgba(255,255,255,0.12)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 10 }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 1]}
                  tick={false}
                  axisLine={false}
                />
                {tracks.map((track) => {
                  const dim =
                    hoveredId && hoveredId !== track.track_id ? true : false;
                  return (
                    <Radar
                      key={track.track_id}
                      name={track.title}
                      dataKey={track.track_id}
                      stroke={track.color}
                      fill={track.color}
                      fillOpacity={dim ? 0.05 : 0.22}
                      strokeOpacity={dim ? 0.14 : 1}
                      strokeWidth={hoveredId === track.track_id ? 2.4 : 1.2}
                      isAnimationActive={false}
                      onMouseEnter={() => setHoveredId(track.track_id)}
                      onMouseLeave={() => setHoveredId(null)}
                    />
                  );
                })}
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    const row = payload[0]?.payload;
                    const fk = row?._key;
                    return (
                      <div className="radar-tooltip">
                        <div className="radar-tooltip-title">{label}</div>
                        {payload.map((item) => (
                          <div key={item.dataKey} className="radar-tooltip-row">
                            <span
                              className="radar-tooltip-swatch"
                              style={{ background: item.color }}
                            />
                            <span className="radar-tooltip-name">{item.name}</span>
                            <span className="radar-tooltip-val">
                              {fk ? formatTooltipValue(fk, tracks, item.dataKey) : item.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    );
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="audio-mode-highlights" aria-label="Mode per track">
            <div className="audio-mode-highlights-label">Mode</div>
            <div className="audio-mode-highlights-grid">
              {tracks.map((t) => (
                <div
                  key={`mode-${t.track_id}`}
                  className="audio-mode-pill"
                  style={{ borderColor: `${t.color}55` }}
                >
                  <span className="audio-mode-pill-dot" style={{ background: t.color }} />
                  <div className="audio-mode-pill-body">
                    <span className="audio-mode-pill-value">{formatModeRaw(getAudioField(t, 'mode'))}</span>
                    <span className="audio-mode-pill-title" title={t.title}>
                      {t.title}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="comparison-legend-chips" aria-label="Highlight track on chart">
            {tracks.map((t) => (
              <button
                key={t.track_id}
                type="button"
                className={`legend-chip ${hoveredId === t.track_id ? 'is-active' : ''}`}
                style={{ borderColor: t.color }}
                onMouseEnter={() => setHoveredId(t.track_id)}
                onFocus={() => setHoveredId(t.track_id)}
                onMouseLeave={() => setHoveredId(null)}
                onBlur={() => setHoveredId(null)}
              >
                <span className="legend-chip-dot" style={{ background: t.color }} />
                <span className="legend-chip-label">{t.title}</span>
              </button>
            ))}
          </div>

          <div className="radar-glossary">
            <div className="radar-glossary-title">What these axes mean</div>
            <ul>
              {activeKeys.map((k) => (
                <li key={k}>
                  <span className="glossary-label">{FEATURE_LABELS[k]}</span>
                  <span className="glossary-text">{FEATURE_DESCRIPTIONS[k]}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      {hasLyric && (
        <div className="lyrical-compare-block">
          <h4 className="comparison-subtitle">Lyrical scores</h4>
          <p className="lyrical-lead">
            Same track colors as above. Bars show 0–1 scores from the galaxy pipeline.
          </p>

          <div className="lyrical-metric">
            <div className="lyrical-metric-head">
              <span className="lyrical-metric-title">{LYRICAL_COPY.mood.title}</span>
            </div>
            <p className="lyrical-desc">{LYRICAL_COPY.mood.body}</p>
            <div
              className="lyrical-columns"
              style={{ '--lyrical-cols': Math.max(1, tracks.length) }}
            >
              {tracks.map((t) => {
                const v = Number(t.musical_features?.lyrical_mood ?? 0.5);
                const h = Math.max(4, Math.min(100, v * 100));
                return (
                  <div key={`m-${t.track_id}`} className="lyrical-col">
                    <div className="lyrical-bar-track">
                      <div
                        className="lyrical-bar-fill"
                        style={{ height: `${h}%`, background: t.color }}
                      />
                    </div>
                    <span className="lyrical-bar-value">{v.toFixed(2)}</span>
                    <span className="lyrical-bar-title" title={t.title}>
                      {t.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="lyrical-metric">
            <div className="lyrical-metric-head">
              <span className="lyrical-metric-title">{LYRICAL_COPY.intensity.title}</span>
            </div>
            <p className="lyrical-desc">{LYRICAL_COPY.intensity.body}</p>
            <div
              className="lyrical-columns"
              style={{ '--lyrical-cols': Math.max(1, tracks.length) }}
            >
              {tracks.map((t) => {
                const v = Number(t.musical_features?.lyrical_intensity ?? 0.5);
                const h = Math.max(4, Math.min(100, v * 100));
                return (
                  <div key={`i-${t.track_id}`} className="lyrical-col">
                    <div className="lyrical-bar-track">
                      <div
                        className="lyrical-bar-fill"
                        style={{ height: `${h}%`, background: t.color }}
                      />
                    </div>
                    <span className="lyrical-bar-value">{v.toFixed(2)}</span>
                    <span className="lyrical-bar-title" title={t.title}>
                      {t.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
