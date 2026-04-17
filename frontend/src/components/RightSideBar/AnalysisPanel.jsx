import React from 'react';
import { AnimatePresence } from 'framer-motion';
import MiniTrackCard from './MiniTrackCard';
import ComparisonChart from './ComparisonChart';

export default function AnalysisPanel({ selectedTracks, onCloseTrack, onCloseAll }) {
  return (
    <aside className="analysis-panel">
      <header className="panel-header">
        <div className="panel-selected-stat" aria-live="polite">
          <span className="panel-selected-label">Selected</span>
          <span className="panel-selected-count">{selectedTracks.length}</span>
        </div>
        <button type="button" className="clear-all-btn" onClick={onCloseAll}>
          Clear all
        </button>
      </header>

      <section className="panel-section-top">
        <div className="horizontal-cards-stack">
          <AnimatePresence mode="popLayout">
            {selectedTracks.map(track => (
              <MiniTrackCard 
                key={track.track_id} 
                track={track} 
                onClose={() => onCloseTrack(track.track_id)} 
              />
            ))}
          </AnimatePresence>
        </div>
      </section>

      <section className="panel-section-bottom">
        <h3 className="section-title">Musical Profile Analytics</h3>
        <div className="chart-wrapper">
          <ComparisonChart tracks={selectedTracks} />
        </div>
      </section>
    </aside>
  );
}