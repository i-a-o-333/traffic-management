import { useEffect, useRef, useState } from 'react';
import TrafficMap from './components/TrafficMap';
import ControlPanel from './components/ControlPanel';
import MetricsPanel from './components/MetricsPanel';
import AIAssistant from './components/AIAssistant';
import LiveChart from './components/LiveChart';
import './App.css';

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  return response.json();
}

function App() {
  const [trafficData, setTrafficData] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [positions, setPositions] = useState({});
  const [cityInfo, setCityInfo] = useState(null);
  const [selectedOrigin, setSelectedOrigin] = useState('');
  const [selectedDest, setSelectedDest] = useState('');
  const [aiEnabled, setAiEnabled] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [cityConfig, setCityConfig] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    async function loadInitialData() {
      const [nodesData, edgesData, configData] = await Promise.all([
        fetchJson('/api/nodes'),
        fetchJson('/api/edges'),
        fetchJson('/api/config'),
      ]);

      setNodes(nodesData.nodes);
      setEdges(edgesData.edges);
      setCityConfig(configData);

      if (nodesData.nodes.length > 0) {
        setSelectedOrigin(nodesData.nodes[0]);
        setSelectedDest(nodesData.nodes[Math.min(4, nodesData.nodes.length - 1)]);
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    let active = true;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${protocol}://${window.location.hostname}:8000/ws/traffic`);

      ws.onopen = () => {
        if (!active) return;
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        if (!active) return;
        setTrafficData(JSON.parse(event.data));
      };

      ws.onerror = () => {
        if (!active) return;
        setIsConnected(false);
      };

      ws.onclose = () => {
        if (!active) return;
        setIsConnected(false);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      active = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleRouteChange = async () => {
    await fetchJson('/api/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: selectedOrigin, end: selectedDest }),
    });
  };

  const toggleAI = async () => {
    const newState = !aiEnabled;
    await fetchJson('/api/ai/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newState }),
    });
    setAiEnabled(newState);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div>
            <h1 className="title">Traffic Control System</h1>
            {cityConfig && (
              <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                {cityConfig.use_real_city ? `${cityConfig.city_name} Network` : 'Simulated City Grid'}
                {' '} • {cityConfig.node_count} nodes • {cityConfig.edge_count} roads
              </p>
            )}
          </div>
          <div className="connection-status">
            <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></div>
            <span>{isConnected ? 'Live' : 'Disconnected'}</span>
          </div>
        </div>
      </header>

      <div className="main-container">
        <aside className="sidebar">
          <ControlPanel
            nodes={nodes}
            selectedOrigin={selectedOrigin}
            selectedDest={selectedDest}
            onOriginChange={setSelectedOrigin}
            onDestChange={setSelectedDest}
            onRouteCalculate={handleRouteChange}
            aiEnabled={aiEnabled}
            onToggleAI={toggleAI}
          />
          <AIAssistant trafficData={trafficData} />
        </aside>

        <main className="content">
          <div className="map-container">
            <TrafficMap
              trafficData={trafficData}
              nodes={nodes}
              edges={edges}
            />
          </div>

          <div className="bottom-panel">
            <MetricsPanel trafficData={trafficData} />
            <LiveChart trafficData={trafficData} selectedNode={selectedDest} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
