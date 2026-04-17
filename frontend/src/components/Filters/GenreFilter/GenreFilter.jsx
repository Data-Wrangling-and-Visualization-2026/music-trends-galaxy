import { useState, useMemo } from 'react';
import '../Filter.css';

/**
 * Multi-select tags (e.g. from dim_artists / dim_albums ``metrics_json.genres``).
 */
export default function GenreFilter({ genres, selectedGenreTags, onSelect, onRemove }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const filteredAvailable = useMemo(() => {
    const selected = new Set((selectedGenreTags || []).map(String));
    return (genres || []).filter((g) => {
      const id = String(g.id);
      const isNotSelected = !selected.has(id);
      const label = (g.name || g.id || '').toLowerCase();
      const matchesSearch = label.includes(searchQuery.toLowerCase());
      return isNotSelected && matchesSearch;
    });
  }, [genres, selectedGenreTags, searchQuery]);

  const handlePick = (id) => {
    onSelect(id);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  return (
    <div className="artist-filter-wrapper" style={{ marginBottom: '20px' }}>
      <label>Genres</label>

      <div
        className={`searchable-select-container ${isDropdownOpen ? 'is-open' : ''}`}
      >
        <input
          type="text"
          className="filter-input"
          placeholder="Search genre..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsDropdownOpen(true);
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
        />

        {isDropdownOpen && filteredAvailable.length > 0 && (
          <ul className="custom-dropdown" role="listbox">
            {filteredAvailable.map((g) => (
              <li
                key={g.id}
                role="option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handlePick(g.id);
                }}
              >
                {g.name || g.id}
              </li>
            ))}
          </ul>
        )}
        {isDropdownOpen && (genres || []).length === 0 && (
          <ul className="custom-dropdown">
            <li className="no-results">No genre tags in metadata</li>
          </ul>
        )}
        {isDropdownOpen &&
          (genres || []).length > 0 &&
          filteredAvailable.length === 0 &&
          searchQuery.trim() && (
            <ul className="custom-dropdown">
              <li className="no-results">No genres match</li>
            </ul>
          )}
      </div>

      <div className="active-filters">
        {selectedGenreTags.map((tag) => (
          <div key={tag} className="filter-chip">
            <span>{tag}</span>
            <button type="button" onClick={() => onRemove(tag)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
