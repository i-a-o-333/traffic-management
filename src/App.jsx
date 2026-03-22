import { useState, useEffect, useRef } from 'react';
import TrafficMap from './components/TrafficMap';
import ControlPanel from './components/ControlPanel';
import MetricsPanel from './components/MetricsPanel';
import AIAssistant from './components/AIAssistant';
import LiveChart from './components/LiveChart';
import './App.css';

function App() {
  const [trafficData, setTrafficData] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedOrigin, setSelectedOrigin] = useState('');
  const [selectedDest, setSelectedDest] = useState('');
  const [aiEnabled, setAiEnabled] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    fetch('/api/nodes')
      .then(res => res.json())
      .then(data => {
        setNodes(data.nodes);
        if (data.nodes.length > 0) {
          setSelectedOrigin(data.nodes[0]);
          setSelectedDest(data.nodes[Math.min(4, data.nodes.length - 1)]);
        }
      });

    fetch('/api/edges')
      .then(res => res.json())
      .then(data => setEdges(data.edges));
  }, []);

  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/traffic`);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setTrafficData(data);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        setTimeout(connectWebSocket, 3000);
      };

      wsRef.current = ws;
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleRouteChange = async () => {
    const response = await fetch('/api/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: selectedOrigin, end: selectedDest }),
    });
    const result = await response.json();
    console.log('Route calculated:', result);
  };

  const handleBlockEdge = async (node1, node2, duration = 30) => {
    await fetch('/api/block', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node1, node2, duration }),
    });
  };

  const toggleAI = async () => {
    const newState = !aiEnabled;
    await fetch('/api/ai/toggle', {
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
          <h1 className="title">Traffic Control System</h1>
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
              onBlockEdge={handleBlockEdge}
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
