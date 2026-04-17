import { useState, useMemo } from 'react';
import '../Filter.css';

/**
 * Filter points by ``cluster_code`` (dim_clusters / embeded_data cluster).
 */
export default function ClusterFilter({ clusters, selectedClusterCodes, onSelect, onRemove }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const nameByCode = useMemo(() => {
    const m = new Map();
    (clusters || []).forEach((c) => {
      const id = String(c.id);
      const name = id === '-1' ? 'unclustered' : c.name || id;
      m.set(id, name);
    });
    return m;
  }, [clusters]);

  const filteredAvailable = useMemo(() => {
    const selected = new Set((selectedClusterCodes || []).map(String));
    return (clusters || []).filter((c) => {
      const id = String(c.id);
      const isNotSelected = !selected.has(id);
      const label = (nameByCode.get(id) || id || '').toLowerCase();
      const matchesSearch = label.includes(searchQuery.toLowerCase());
      return isNotSelected && matchesSearch;
    });
  }, [clusters, selectedClusterCodes, searchQuery, nameByCode]);

  const handlePick = (id) => {
    onSelect(id);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  return (
    <div className="artist-filter-wrapper" style={{ marginBottom: '20px' }}>
      <label>Clusters</label>

      <div
        className={`searchable-select-container ${isDropdownOpen ? 'is-open' : ''}`}
      >
        <input
          type="text"
          className="filter-input"
          placeholder="Search cluster..."
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
            {filteredAvailable.map((c) => (
              <li
                key={c.id}
                role="option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handlePick(c.id);
                }}
              >
                {c.name || c.id}
              </li>
            ))}
          </ul>
        )}
        {isDropdownOpen && filteredAvailable.length === 0 && searchQuery && (
          <ul className="custom-dropdown">
            <li className="no-results">No clusters match</li>
          </ul>
        )}
      </div>

      <div className="active-filters">
        {selectedClusterCodes.map((code) => (
          <div key={code} className="filter-chip">
            <span>
              {String(code) === '-1'
                ? 'unclustered'
                : nameByCode.get(String(code)) || code}
            </span>
            <button type="button" onClick={() => onRemove(code)}>
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
