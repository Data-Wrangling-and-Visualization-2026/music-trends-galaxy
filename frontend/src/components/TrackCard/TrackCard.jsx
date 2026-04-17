import { useEffect, useState } from 'react';
import { fetchTrackDetails } from '../../services/tracksApi';
import { useNavigate } from 'react-router-dom';
import './TrackCard.css';

export default function TrackCard({ trackId, onClose }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    fetchTrackDetails(trackId)
      .then(setInfo)
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [trackId]);

  if (loading) return <div className="track-card">Loading...</div>;
  if (!info) return <div className="track-card">Data lost in space...</div>;;

  return (
    <div className="track-card">
      <button className="track-card-close" onClick={onClose}>✕</button>
      
      <header>
        <h2 className="track-title">{info.name}</h2>
        <p className="track-artist">{info.artist_name}</p>
        <p className="track-album">{info.album_title} ({info.year})</p>
      </header>

      <section className="track-section">
        <h3>Lyrics Snippet</h3>
        <p className="track-lyrics">"{info.lyrics}"</p>
      </section>

      <section className="track-section">
        <h3>Musical Profile</h3>
        <div className="feature-bar">
          <span>Energy</span>
          <div className="bar-bg"><div className="bar-fill" style={{ width: `${(info.musical_features?.energy ?? 0) * 100}%` }}></div></div>
        </div>
        <div className="feature-bar">
          <span>Danceability</span>
          <div className="bar-bg"><div className="bar-fill" style={{ width: `${(info.musical_features?.danceability ?? 0) * 100}%` }}></div></div>
        </div>
        <div className="feature-bar">
          <span>Valence (Mood)</span>
          <div className="bar-bg"><div className="bar-fill" style={{ width: `${(info.musical_features?.valence ?? 0) * 100}%` }}></div></div>
        </div>
      </section>

      <button className="detail-btn" style={{ backgroundColor: info.color }} onClick={() => {console.log("Navigating to:", `/track-details/${trackId}`); navigate(`/track-details/${trackId}`)}}>
        Open Extended Info
      </button>
    </div>
  );
}