import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';

export default function MiniTrackCard({ track, onClose }) {
  return (
    <motion.div 
      layout
      initial={{ opacity: 0, scale: 0.9, x: 20 }}
      animate={{ opacity: 1, scale: 1, x: 0 }}
      exit={{ opacity: 0, scale: 0.5, y: -20 }}
      className="track-card mini"
      style={{ borderLeft: `4px solid ${track.color}` }}
    >
      <button
        type="button"
        onClick={onClose}
        className="mini-close-btn"
        aria-label="Remove from comparison"
      >
        <X size={18} strokeWidth={2.25} />
      </button>
      <div className="mini-card-content">
        <h4 className="mini-track-title">{track.title}</h4>
        <p className="mini-track-artist">{track.artist}</p>
        <Link
          className="mini-track-link"
          to={`/track-details/${encodeURIComponent(track.track_id)}`}
        >
          Full details →
        </Link>
      </div>
    </motion.div>
  );
}