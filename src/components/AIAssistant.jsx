import { useState, useEffect } from 'react';
import './AIAssistant.css';

function AIAssistant({ trafficData }) {
  const [logs, setLogs] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch('/api/ai/status');
        const data = await response.json();
        if (data.logs) {
          setLogs(data.logs.slice(0, 8));
        }
      } catch (error) {
        console.error('Failed to fetch AI logs:', error);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  const getLogColor = (log) => {
    if (log.includes('ALERT') || log.includes('INCIDENT')) return '#ef4444';
    if (log.includes('ACTION')) return '#10b981';
    if (log.includes('OPTIMIZING')) return '#f59e0b';
    if (log.includes('ROUTING')) return '#06b6d4';
    return '#64748b';
  };

  return (
    <div className={`ai-assistant ${expanded ? 'expanded' : ''}`}>
      <div className="assistant-header" onClick={() => setExpanded(!expanded)}>
        <div className="assistant-title">
          <div className="assistant-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </div>
          <div>
            <h3>AI Assistant</h3>
            <span className="assistant-status">Active</span>
          </div>
        </div>
        <div className="expand-icon">
          {expanded ? '−' : '+'}
        </div>
      </div>

      <div className="assistant-content">
        <div className="logs-container">
          {logs.map((log, index) => (
            <div key={index} className="log-entry" style={{ borderLeftColor: getLogColor(log) }}>
              <div className="log-text">{log}</div>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="log-empty">Initializing AI system...</div>
          )}
        </div>

        <div className="assistant-insights">
          <div className="insight-item">
            <div className="insight-icon">📊</div>
            <div className="insight-text">
              <div className="insight-label">Traffic Pattern</div>
              <div className="insight-value">
                {trafficData?.ai?.trend || 'Analyzing...'}
              </div>
            </div>
          </div>

          <div className="insight-item">
            <div className="insight-icon">🎯</div>
            <div className="insight-text">
              <div className="insight-label">Active Nodes</div>
              <div className="insight-value">
                {trafficData?.ai?.priority_nodes?.length || 0} priority
              </div>
            </div>
          </div>

          <div className="insight-item">
            <div className="insight-icon">⚡</div>
            <div className="insight-text">
              <div className="insight-label">System Status</div>
              <div className="insight-value">
                {trafficData?.ai?.status || 'INITIALIZING'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AIAssistant;
