import './ControlPanel.css';

function ControlPanel({
  nodes,
  selectedOrigin,
  selectedDest,
  onOriginChange,
  onDestChange,
  onRouteCalculate,
  aiEnabled,
  onToggleAI,
}) {
  return (
    <div className="control-panel">
      <div className="panel-header">
        <h2>Route Planning</h2>
      </div>

      <div className="control-section">
        <label className="control-label">Origin</label>
        <select
          className="control-select"
          value={selectedOrigin}
          onChange={(e) => onOriginChange(e.target.value)}
        >
          {nodes.map(node => (
            <option key={node} value={node}>{node}</option>
          ))}
        </select>
      </div>

      <div className="control-section">
        <label className="control-label">Destination</label>
        <select
          className="control-select"
          value={selectedDest}
          onChange={(e) => onDestChange(e.target.value)}
        >
          {nodes.map(node => (
            <option key={node} value={node}>{node}</option>
          ))}
        </select>
      </div>

      <button className="btn btn-primary" onClick={onRouteCalculate}>
        Calculate Route
      </button>

      <div className="divider"></div>

      <div className="panel-header">
        <h2>AI Control</h2>
      </div>

      <div className="toggle-section">
        <div className="toggle-info">
          <span className="toggle-label">Autonomous AI</span>
          <span className="toggle-status">{aiEnabled ? 'Active' : 'Inactive'}</span>
        </div>
        <button
          className={`toggle-btn ${aiEnabled ? 'active' : ''}`}
          onClick={onToggleAI}
        >
          <div className="toggle-slider"></div>
        </button>
      </div>

      <div className={`ai-status-card ${aiEnabled ? 'active' : 'inactive'}`}>
        <div className="status-icon">
          {aiEnabled ? (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <path d="M8 12l2 2 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <path d="M8 8l8 8M16 8l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          )}
        </div>
        <div className="status-text">
          {aiEnabled ? 'AI monitoring traffic and optimizing routes' : 'Manual control mode'}
        </div>
      </div>
    </div>
  );
}

export default ControlPanel;
