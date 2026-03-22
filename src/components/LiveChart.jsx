import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import './LiveChart.css';

function LiveChart({ trafficData, selectedNode }) {
  const [chartData, setChartData] = useState([]);
  const [maxPoints] = useState(60);

  useEffect(() => {
    if (!trafficData?.volumes || !selectedNode) return;

    const volume = trafficData.volumes[selectedNode] || 0;
    const timestamp = new Date().toLocaleTimeString();

    setChartData(prev => {
      const newData = [...prev, { time: timestamp, volume: Math.round(volume) }];
      if (newData.length > maxPoints) {
        return newData.slice(-maxPoints);
      }
      return newData;
    });
  }, [trafficData, selectedNode, maxPoints]);

  const currentVolume = chartData.length > 0 ? chartData[chartData.length - 1].volume : 0;
  const avgVolume = chartData.length > 0
    ? Math.round(chartData.reduce((sum, d) => sum + d.volume, 0) / chartData.length)
    : 0;

  const getVolumeStatus = (vol) => {
    if (vol > 700) return { label: 'Heavy', color: '#ef4444' };
    if (vol > 500) return { label: 'Moderate', color: '#f59e0b' };
    return { label: 'Light', color: '#10b981' };
  };

  const status = getVolumeStatus(currentVolume);

  return (
    <div className="live-chart">
      <div className="chart-header">
        <div>
          <h2>Live Traffic Monitor</h2>
          <div className="chart-subtitle">Node: {selectedNode}</div>
        </div>
        <div className="chart-stats">
          <div className="stat-item">
            <span className="stat-label">Current</span>
            <span className="stat-value" style={{ color: status.color }}>
              {currentVolume}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Average</span>
            <span className="stat-value">{avgVolume}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Status</span>
            <span className="stat-badge" style={{ background: status.color }}>
              {status.label}
            </span>
          </div>
        </div>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="volumeGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#667eea" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#667eea" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="time"
              stroke="#94a3b8"
              style={{ fontSize: '0.75rem' }}
              tick={{ fill: '#64748b' }}
            />
            <YAxis
              stroke="#94a3b8"
              style={{ fontSize: '0.75rem' }}
              tick={{ fill: '#64748b' }}
              domain={[0, 900]}
            />
            <Tooltip
              contentStyle={{
                background: 'white',
                border: 'none',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              }}
            />
            <Area
              type="monotone"
              dataKey="volume"
              stroke="#667eea"
              strokeWidth={3}
              fill="url(#volumeGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="volume-indicator">
        <div className="indicator-label">Congestion Level</div>
        <div className="indicator-bar">
          <div
            className="indicator-fill"
            style={{
              width: `${(currentVolume / 900) * 100}%`,
              background: `linear-gradient(to right, #10b981, #f59e0b, #ef4444)`,
            }}
          ></div>
        </div>
        <div className="indicator-values">
          <span>0</span>
          <span>450</span>
          <span>900</span>
        </div>
      </div>
    </div>
  );
}

export default LiveChart;
