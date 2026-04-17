import { useState, useMemo } from 'react';
import '../Filter.css';

export default function ArtistFilter({ artists, selectedArtistIds, onSelect, onRemove }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const filteredAvailableArtists = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return (artists || []).filter((artist) => {
      const isNotSelected = !selectedArtistIds.map(String).includes(String(artist.id));
      const label = String(artist.name ?? artist.id ?? '');
      const matchesSearch = label.toLowerCase().includes(q);
      return isNotSelected && matchesSearch;
    });
  }, [artists, selectedArtistIds, searchQuery]);

  const handleSelect = (id) => {
    onSelect(id);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  return (
    <div className="artist-filter-wrapper">
      <label>Search And Add Artists:</label>
      
      <div
        className={`searchable-select-container ${isDropdownOpen ? 'is-open' : ''}`}
      >
        <input 
          type="text"
          className="filter-input"
          placeholder="Type artist name..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsDropdownOpen(true);
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
        />
        
        {isDropdownOpen && filteredAvailableArtists.length > 0 && (
          <ul className="custom-dropdown" role="listbox">
            {filteredAvailableArtists.map((artist) => (
              <li
                key={artist.id}
                role="option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(artist.id);
                }}
              >
                {artist.name ?? artist.id}
              </li>
            ))}
          </ul>
        )}
        {isDropdownOpen && (artists || []).length === 0 && (
          <ul className="custom-dropdown">
            <li className="no-results">No artists in loaded data</li>
          </ul>
        )}
        {isDropdownOpen &&
          (artists || []).length > 0 &&
          filteredAvailableArtists.length === 0 &&
          searchQuery.trim() && (
            <ul className="custom-dropdown">
              <li className="no-results">No artists match</li>
            </ul>
          )}
      </div>

      <div className="active-filters">
        {selectedArtistIds.map((id) => {
          const artist = (artists || []).find((a) => String(a.id) === String(id));
          if (!artist) return null;
          return (
            <div key={id} className="filter-chip">
              <span>{artist.name ?? artist.id}</span>
              <button type="button" onClick={() => onRemove(id)}>
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}