import { useState, useMemo } from 'react';
import '../Filter.css';

export default function AlbumFilter({ albums, selectedAlbumIds, onSelect, onRemove }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const filteredAvailableAlbums = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return (albums || []).filter((album) => {
      const isNotSelected = !selectedAlbumIds.map(String).includes(String(album.id));
      const label = String(album.title ?? album.id ?? '');
      const matchesSearch = label.toLowerCase().includes(q);
      return isNotSelected && matchesSearch;
    });
  }, [albums, selectedAlbumIds, searchQuery]);

  const handleSelect = (id) => {
    onSelect(id);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  return (
    <div className="album-filter-wrapper">
      <label>Search And Add Albums:</label>
      
      <div
        className={`searchable-select-container ${isDropdownOpen ? 'is-open' : ''}`}
      >
        <input 
          type="text"
          className="filter-input"
          placeholder="Type album name..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsDropdownOpen(true);
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
        />
        
        {isDropdownOpen && filteredAvailableAlbums.length > 0 && (
          <ul className="custom-dropdown" role="listbox">
            {filteredAvailableAlbums.map((album) => (
              <li
                key={album.id}
                role="option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(album.id);
                }}
              >
                {album.title ?? album.id}
              </li>
            ))}
          </ul>
        )}
        {isDropdownOpen && (albums || []).length === 0 && (
          <ul className="custom-dropdown">
            <li className="no-results">No albums in loaded data</li>
          </ul>
        )}
        {isDropdownOpen &&
          (albums || []).length > 0 &&
          filteredAvailableAlbums.length === 0 &&
          searchQuery.trim() && (
            <ul className="custom-dropdown">
              <li className="no-results">No albums match</li>
            </ul>
          )}
      </div>

      <div className="active-filters">
        {selectedAlbumIds.map((id) => {
          const album = (albums || []).find((a) => String(a.id) === String(id));
          if (!album) return null;
          return (
            <div key={id} className="filter-chip">
              <span>{album.title ?? album.id}</span>
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