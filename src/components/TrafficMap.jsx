import { useEffect, useRef } from 'react';
import './TrafficMap.css';

const MAP_PADDING = 60;
const MAX_TRAFFIC_VOLUME = 900;

function buildNodePositions(width, height, edges, nodes) {
  const nodePositions = {};

  if (nodes.length === 0) return nodePositions;

  const firstEdge = edges[0];
  const isGridFormat = firstEdge && firstEdge.source.startsWith('N') && firstEdge.source.includes('_');

  if (isGridFormat) {
    const gridNodes = {};
    let maxX = 0, maxY = 0;

    nodes.forEach(node => {
      const match = node.match(/N(\d+)_(\d+)/);
      if (match) {
        const x = parseInt(match[1]);
        const y = parseInt(match[2]);
        gridNodes[node] = { gridX: x, gridY: y };
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    });

    const cellWidth = (width - MAP_PADDING * 2) / maxX;
    const cellHeight = (height - MAP_PADDING * 2) / maxY;

    nodes.forEach(node => {
      if (gridNodes[node]) {
        nodePositions[node] = {
          x: MAP_PADDING + gridNodes[node].gridX * cellWidth,
          y: MAP_PADDING + gridNodes[node].gridY * cellHeight,
        };
      }
    });
  } else {
    const positions = {};
    nodes.forEach(node => {
      positions[node] = { x: 0, y: 0 };
    });

    const graph = {};
    nodes.forEach(node => { graph[node] = []; });
    edges.forEach(edge => {
      if (!graph[edge.source]) graph[edge.source] = [];
      if (!graph[edge.target]) graph[edge.target] = [];
      graph[edge.source].push(edge.target);
      graph[edge.target].push(edge.source);
    });

    const visited = new Set();
    const queue = [nodes[0]];
    positions[nodes[0]] = { x: 0, y: 0 };
    visited.add(nodes[0]);

    while (queue.length > 0) {
      const current = queue.shift();
      const neighbors = graph[current] || [];

      neighbors.forEach((neighbor, idx) => {
        if (!visited.has(neighbor)) {
          const angle = (idx / neighbors.length) * 2 * Math.PI;
          const distance = 100 + Math.random() * 50;
          positions[neighbor] = {
            x: positions[current].x + Math.cos(angle) * distance,
            y: positions[current].y + Math.sin(angle) * distance,
          };
          visited.add(neighbor);
          queue.push(neighbor);
        }
      });
    }

    const xCoords = Object.values(positions).map(p => p.x);
    const yCoords = Object.values(positions).map(p => p.y);
    const minX = Math.min(...xCoords);
    const maxX = Math.max(...xCoords);
    const minY = Math.min(...yCoords);
    const maxY = Math.max(...yCoords);

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    nodes.forEach(node => {
      if (positions[node]) {
        nodePositions[node] = {
          x: MAP_PADDING + ((positions[node].x - minX) / rangeX) * (width - MAP_PADDING * 2),
          y: MAP_PADDING + ((positions[node].y - minY) / rangeY) * (height - MAP_PADDING * 2),
        };
      }
    });
  }

  return nodePositions;
}

function createBlockedEdgeSet(blockedEdges = []) {
  return new Set(blockedEdges.flatMap(({ u, v }) => [`${u}-${v}`, `${v}-${u}`]));
}

function getNodeColor(volume) {
  const normalizedVolume = Math.min(volume / MAX_TRAFFIC_VOLUME, 1);
  const red = Math.round(normalizedVolume * 239 + (1 - normalizedVolume) * 34);
  const green = Math.round((1 - normalizedVolume) * 211 + normalizedVolume * 68);
  const blue = Math.round((1 - normalizedVolume) * 234 + normalizedVolume * 64);
  return `rgb(${red}, ${green}, ${blue})`;
}

function TrafficMap({ trafficData, nodes, edges }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!trafficData || !canvasRef.current || !containerRef.current) return;

    const canvas = canvasRef.current;
    const container = containerRef.current;
    const ctx = canvas.getContext('2d');

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const nodePositions = buildNodePositions(canvas.width, canvas.height, edges, nodes);
    const blockedSet = createBlockedEdgeSet(trafficData.blocked_edges);

    edges.forEach((edge) => {
      const start = nodePositions[edge.source];
      const end = nodePositions[edge.target];
      if (!start || !end) return;

      const isBlocked = blockedSet.has(`${edge.source}-${edge.target}`);

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.strokeStyle = isBlocked ? '#ef4444' : 'rgba(148, 163, 184, 0.3)';
      ctx.lineWidth = isBlocked ? 3 : 2;
      ctx.stroke();
    });

    (trafficData.route?.edges || []).forEach(([source, target]) => {
      const start = nodePositions[source];
      const end = nodePositions[target];
      if (!start || !end) return;

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 4;
      ctx.stroke();

      const arrowSize = 8;
      const angle = Math.atan2(end.y - start.y, end.x - start.x);
      ctx.save();
      ctx.translate(end.x, end.y);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(-arrowSize, -arrowSize / 2);
      ctx.lineTo(0, 0);
      ctx.lineTo(-arrowSize, arrowSize / 2);
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.restore();
    });

    nodes.forEach((node) => {
      const pos = nodePositions[node];
      if (!pos) return;

      const volume = trafficData.volumes?.[node] || 0;

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
      ctx.fillStyle = getNodeColor(volume);
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = '#1e293b';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(node, pos.x, pos.y - 15);
    });
  }, [trafficData, nodes, edges]);

  return (
    <div className="traffic-map" ref={containerRef}>
      <div className="map-header">
        <h2>Network Visualization</h2>
        {trafficData?.route && (
          <div className="route-info">
            <span className="route-label">ETA:</span>
            <span className="route-value">{trafficData.route.eta_minutes?.toFixed(1)} min</span>
          </div>
        )}
      </div>
      <canvas ref={canvasRef} />
      <div className="legend">
        <div className="legend-item">
          <div className="legend-color" style={{ background: 'linear-gradient(to right, #22d3ee, #ef4444)' }}></div>
          <span>Traffic Volume: Low to High</span>
        </div>
        <div className="legend-item">
          <div className="legend-line blocked"></div>
          <span>Blocked Road</span>
        </div>
        <div className="legend-item">
          <div className="legend-line route"></div>
          <span>Active Route</span>
        </div>
      </div>
    </div>
  );
}

export default TrafficMap;
