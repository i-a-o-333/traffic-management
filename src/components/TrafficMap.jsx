import { useEffect, useRef } from 'react';
import './TrafficMap.css';

const MAP_PADDING = 60;
const MAX_TRAFFIC_VOLUME = 900;

function buildGridNodePositions(width, height, nodes) {
  const nodePositions = {};
  const gridWidth = Math.max(2, Math.ceil(Math.sqrt(nodes.length)));
  const gridHeight = Math.max(2, Math.ceil(nodes.length / gridWidth));
  const cellWidth = (width - MAP_PADDING * 2) / (gridWidth - 1);
  const cellHeight = (height - MAP_PADDING * 2) / (gridHeight - 1);

  nodes.forEach((nodeName, index) => {
    const x = index % gridWidth;
    const y = Math.floor(index / gridWidth);
    nodePositions[nodeName] = {
      x: MAP_PADDING + x * cellWidth,
      y: MAP_PADDING + y * cellHeight,
    };
  });

  return nodePositions;
}

function buildGeoNodePositions(width, height, positions) {
  const nodePositions = {};
  const values = Object.values(positions).filter(({ x, y }) => x !== undefined && y !== undefined);
  if (!values.length) {
    return {};
  }

  const minX = Math.min(...values.map(({ x }) => x));
  const maxX = Math.max(...values.map(({ x }) => x));
  const minY = Math.min(...values.map(({ y }) => y));
  const maxY = Math.max(...values.map(({ y }) => y));
  const scaleX = maxX - minX || 1;
  const scaleY = maxY - minY || 1;

  Object.entries(positions).forEach(([nodeName, point]) => {
    if (point.x === undefined || point.y === undefined) return;
    nodePositions[nodeName] = {
      x: MAP_PADDING + ((point.x - minX) / scaleX) * (width - MAP_PADDING * 2),
      y: MAP_PADDING + (1 - (point.y - minY) / scaleY) * (height - MAP_PADDING * 2),
    };
  });

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

function TrafficMap({ trafficData, nodes, edges, positions }) {
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

    const nodePositions = Object.keys(positions || {}).length
      ? buildGeoNodePositions(canvas.width, canvas.height, positions)
      : buildGridNodePositions(canvas.width, canvas.height, nodes);
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
