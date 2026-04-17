import './Sidebar.css';

export default function Sidebar({
  isOpen,
  onClose,
  title = 'Settings',
  children,
  variant = 'overlay',
}) {
  const docked = variant === 'docked';

  return (
    <>
      <div className={`sidebar ${docked ? 'sidebar--docked' : ''} ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h3>{title}</h3>
          <button type="button" className="close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="sidebar-content">{children}</div>
      </div>

      {isOpen && !docked && <div className="overlay" onClick={onClose} aria-hidden="true" />}
    </>
  );
}
