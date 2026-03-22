import './MetricsPanel.css';

function MetricsPanel({ trafficData }) {
  const aiStatus = trafficData?.ai?.status || 'INITIALIZING';
  const trend = trafficData?.ai?.trend || 'stable';
  const anomalies = trafficData?.ai?.anomalies || 0;
  const priorityNodes = trafficData?.ai?.priority_nodes || [];

  const getStatusColor = (status) => {
    const colors = {
      'ONLINE': '#10b981',
      'ANALYZING': '#06b6d4',
      'ALERT': '#ef4444',
      'OPTIMIZING': '#f59e0b',
      'INITIALIZING': '#94a3b8',
    };
    return colors[status] || '#94a3b8';
  };

  const getTrendIcon = (trend) => {
    if (trend === 'increasing') return '↗';
    if (trend === 'decreasing') return '↘';
    return '→';
  };

  return (
    <div className="metrics-panel">
      <div className="panel-header">
        <h2>System Metrics</h2>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">AI Status</div>
          <div className="metric-value" style={{ color: getStatusColor(aiStatus) }}>
            {aiStatus}
          </div>
          <div className="metric-bar">
            <div
              className="metric-bar-fill"
              style={{
                width: aiStatus === 'ALERT' ? '100%' : aiStatus === 'OPTIMIZING' ? '70%' : '40%',
                background: getStatusColor(aiStatus),
              }}
            ></div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Traffic Trend</div>
          <div className="metric-value trend">
            <span className="trend-icon">{getTrendIcon(trend)}</span>
            {trend}
          </div>
          <div className="metric-detail">
            Current pattern analysis
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Active Anomalies</div>
          <div className="metric-value" style={{ color: anomalies > 0 ? '#ef4444' : '#10b981' }}>
            {anomalies}
          </div>
          <div className="metric-detail">
            {anomalies > 0 ? 'Incidents detected' : 'All clear'}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Priority Nodes</div>
          <div className="metric-value priority-nodes">
            {priorityNodes.slice(0, 3).join(', ') || 'N/A'}
          </div>
          <div className="metric-detail">
            Highest traffic volume
          </div>
        </div>
      </div>

      <div className="action-card">
        <div className="action-header">
          <div className="action-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="action-title">AI Action</span>
        </div>
        <div className="action-message">
          {trafficData?.ai?.action || 'Monitoring traffic conditions...'}
        </div>
      </div>
    </div>
  );
}

export default MetricsPanel;
