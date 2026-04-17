import { useState, useMemo } from 'react';
import '../Filter.css';

export default function YearFilter({ years, selectedYearIds, onSelect, onRemove }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const filteredAvailableYears = useMemo(() => {
    const q = searchQuery;
    return (years || []).filter((year) => {
      const isNotSelected = !selectedYearIds.map(String).includes(String(year.id));
      const label = String(year.name ?? year.id ?? '');
      const matchesSearch = label.includes(q);
      return isNotSelected && matchesSearch;
    });
  }, [years, selectedYearIds, searchQuery]);

  const handleSelect = (id) => {
    onSelect(id);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  return (
    <div className="artist-filter-wrapper" style={{ marginBottom: '20px' }}>
      <label>Filter by Release Year:</label>
      
      <div
        className={`searchable-select-container ${isDropdownOpen ? 'is-open' : ''}`}
      >
        <input 
          type="text"
          className="filter-input"
          placeholder="Type year..."
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsDropdownOpen(true);
          }}
          onFocus={() => setIsDropdownOpen(true)}
          onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
        />

        {isDropdownOpen && filteredAvailableYears.length > 0 && (
          <ul className="custom-dropdown" role="listbox">
            {filteredAvailableYears.map((year) => (
              <li
                key={year.id}
                role="option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleSelect(year.id);
                }}
              >
                {year.name ?? year.id}
              </li>
            ))}
          </ul>
        )}
        {isDropdownOpen && (years || []).length === 0 && (
          <ul className="custom-dropdown">
            <li className="no-results">No years in loaded tracks</li>
          </ul>
        )}
        {isDropdownOpen &&
          (years || []).length > 0 &&
          filteredAvailableYears.length === 0 &&
          searchQuery && (
            <ul className="custom-dropdown">
              <li className="no-results">No years match</li>
            </ul>
          )}
      </div>

      <div className="active-filters">
        {selectedYearIds.map(id => (
          <div key={id} className="filter-chip">
            <span>{id}</span>
            <button type="button" onClick={() => onRemove(id)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}