import { useEffect, useRef } from 'react';
import './TrafficMap.css';

function TrafficMap({ trafficData, nodes, edges, onBlockEdge }) {
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

    const nodePositions = {};
    const gridW = 8;
    const gridH = 6;
    const padding = 60;
    const cellWidth = (canvas.width - padding * 2) / (gridW - 1);
    const cellHeight = (canvas.height - padding * 2) / (gridH - 1);

    for (let y = 0; y < gridH; y++) {
      for (let x = 0; x < gridW; x++) {
        const nodeName = `N${x}_${y}`;
        nodePositions[nodeName] = {
          x: padding + x * cellWidth,
          y: padding + y * cellHeight,
        };
      }
    }

    const blockedSet = new Set(
      trafficData.blocked_edges?.map(e => `${e.u}-${e.v}`) || []
    );

    edges.forEach(edge => {
      const start = nodePositions[edge.source];
      const end = nodePositions[edge.target];
      if (!start || !end) return;

      const isBlocked = blockedSet.has(`${edge.source}-${edge.target}`) ||
                       blockedSet.has(`${edge.target}-${edge.source}`);

      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.strokeStyle = isBlocked ? '#ef4444' : 'rgba(148, 163, 184, 0.3)';
      ctx.lineWidth = isBlocked ? 3 : 2;
      ctx.stroke();
    });

    const routeEdges = trafficData.route?.edges || [];
    routeEdges.forEach(([source, target]) => {
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

    nodes.forEach(node => {
      const pos = nodePositions[node];
      if (!pos) return;

      const volume = trafficData.volumes?.[node] || 0;
      const normalizedVolume = Math.min(volume / 900, 1);

      const red = Math.round(normalizedVolume * 239 + (1 - normalizedVolume) * 34);
      const green = Math.round((1 - normalizedVolume) * 211 + normalizedVolume * 68);
      const blue = Math.round((1 - normalizedVolume) * 234 + normalizedVolume * 64);

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
      ctx.fillStyle = `rgb(${red}, ${green}, ${blue})`;
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
