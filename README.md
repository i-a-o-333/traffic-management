# Traffic Control System

A full-stack traffic operations demo that combines a simulated city network, AI-assisted routing logic, and a live React dashboard. The project showcases how a modern frontend can stay synchronized with a Python backend over REST and WebSockets while exposing simulation, anomaly detection, route planning, and operator controls in one place.

## What this project showcases

This repository is more than a simple UI mockup. It demonstrates:

- **A FastAPI backend** serving traffic network metadata, route-planning endpoints, AI status endpoints, prediction endpoints, and a real-time WebSocket stream.
- **A simulation engine** that models changing traffic demand over an 8x6 road grid with peak-hour multipliers, weather/event effects, and sensor degradation.
- **An AI decision layer** that monitors congestion, detects anomalies, identifies high-priority nodes, and can automatically take mitigation actions.
- **An online neural predictor** built with PyTorch and LSTM layers to learn from node traffic history and forecast future traffic values.
- **A React + Vite frontend** that visualizes traffic state, route overlays, AI insights, and live node trends in a responsive dashboard.
- **Interactive operator controls** for route selection, autonomous AI toggling, and road blocking.

## Tech stack

### Frontend
- **React 18** for component-based UI rendering.
- **Vite 5** for development server and bundling.
- **Recharts** for live traffic trend visualization.
- **Custom CSS** for the glassmorphism / gradient dashboard styling.

### Backend
- **FastAPI** for REST and WebSocket APIs.
- **Pydantic** for request validation.
- **NetworkX** for graph modeling and shortest-path routing.
- **PyTorch** for the LSTM-based traffic predictor.
- **NumPy** for simulation math and trend analysis.
- **Uvicorn** as the ASGI server.

## System architecture

```text
React/Vite dashboard
   ├─ fetch /api/nodes, /api/edges, /api/route, /api/block, /api/ai/*
   └─ subscribe ws://localhost:8000/ws/traffic

FastAPI application
   ├─ Router: graph generation + weighted routing + edge blocking
   ├─ TrafficSim: simulated traffic volumes + context effects + sensor health
   ├─ NeuralPredictor: online LSTM training + node forecasts
   ├─ AIDecisionEngine: anomaly detection + optimization suggestions/actions
   └─ LiveTrafficIntegrator: placeholder live-provider integration state
```

## Core capabilities

### 1. Simulated road network
The backend creates a synthetic **8 columns × 6 rows** city grid named with nodes like `N0_0` and `N7_5`. Roads are categorized as:

- **arterial**
- **collector**
- **local**
- **ring**

Each edge carries metadata such as free-flow travel time, capacity, lane count, road length, and speed limit. That makes the graph realistic enough for weighted route calculations instead of simple shortest-hop pathfinding.

### 2. Dynamic traffic simulation
Traffic values are not static. Each simulation step blends:

- base cyclical demand
- time-of-day multipliers
- weekday/weekend adjustments
- randomized weather impact
- randomized event surges
- sensor quality / dropout behavior
- exponential smoothing for stable displayed values

This gives the UI a continuously changing network rather than a frozen demo dataset.

### 3. AI-assisted traffic management
The AI layer evaluates the latest traffic snapshot and can:

- rank the highest-volume nodes
- detect anomaly spikes and drops
- identify degraded sensors
- evaluate route efficiency impact
- recommend or trigger adaptive actions
- automatically block nearby road segments when isolating incidents

When autonomous mode is enabled, the system can perform mitigation actions without waiting for manual operator input.

### 4. Real-time dashboard behavior
The frontend subscribes to a WebSocket feed and updates every second with:

- latest node volumes
- blocked road segments
- active route and ETA
- AI status and current action
- anomaly count and traffic trend
- per-node health summaries

This keeps the visualization and KPI panels synchronized with the backend simulation loop.

### 5. Online forecasting
For each node, the predictor stores recent observations and incrementally trains an LSTM model. Once enough history exists, the API can return:

- predicted mean traffic
- forecast standard deviation
- prediction horizon samples
- confidence score
- current node value

## Frontend experience

The React app is organized around a dashboard layout with five main views/components:

### Control Panel
Used for route planning and AI control.

- Select origin and destination nodes.
- Trigger route calculation via the API.
- Enable or disable autonomous AI control.
- View a simple AI activity status card.

### Traffic Map
Canvas-based network visualization that shows:

- all road connections in the city graph
- blocked roads in red
- active route segments in cyan
- node markers colored by relative traffic volume
- a live ETA label for the selected route

### Metrics Panel
Operational KPI summary for:

- AI status
- network trend direction
- active anomaly count
- priority nodes
- latest AI-generated action message

### AI Assistant
A collapsible activity feed that periodically polls AI logs and surfaces:

- incident messages
- routing warnings
- auto-actions
- current traffic trend
- number of active priority nodes
- system status snapshot

### Live Chart
A live area chart focused on the selected destination node, including:

- rolling traffic history
- current value
- average value
- qualitative traffic status badge
- congestion progress bar

## Backend API reference

### REST endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/nodes` | Return all node IDs in the network. |
| `GET` | `/api/edges` | Return graph edges and road metadata. |
| `GET` | `/api/traffic` | Return current volumes, timestamp, and blocked edges. |
| `POST` | `/api/route` | Calculate the weighted route between two nodes. |
| `POST` | `/api/block` | Block a road segment for a specified duration. |
| `POST` | `/api/ai/toggle` | Enable or disable autonomous AI mode. |
| `GET` | `/api/ai/status` | Return AI status, enabled state, and recent logs. |
| `GET` | `/api/predictions/{node}` | Return node forecast data when enough history exists. |
| `GET` | `/api/live/status` | Return live-provider integration state. |

### WebSocket endpoint

| Endpoint | Purpose |
| --- | --- |
| `/ws/traffic` | Streams traffic volumes, route data, blocked edges, AI metadata, and health snapshots once per second. |

## Example data flow

1. The frontend loads available nodes and edges through REST requests.
2. The frontend opens a WebSocket connection to `/ws/traffic`.
3. The backend simulation advances traffic volumes once per second.
4. The router recalculates edge weights from the current traffic state.
5. The neural predictor updates with the newest node observations.
6. The AI engine analyzes congestion and may trigger an action.
7. The backend pushes the latest snapshot to the frontend.
8. The dashboard redraws the map, metrics, chart, and assistant feed.

## Project structure

```text
traffic-management/
├── backend.py                 # FastAPI app, routes, WebSocket loop
├── main_system.py             # Simulation, routing, prediction, AI engine
├── src/
│   ├── App.jsx                # Dashboard composition + API/WebSocket wiring
│   ├── main.jsx               # React bootstrap
│   └── components/
│       ├── ControlPanel.jsx   # Route controls + AI toggle
│       ├── TrafficMap.jsx     # Canvas network visualization
│       ├── MetricsPanel.jsx   # KPI summary cards
│       ├── AIAssistant.jsx    # AI log feed and insight panel
│       └── LiveChart.jsx      # Historical traffic chart
├── package.json               # Frontend scripts and dependencies
└── requirements.txt           # Backend dependencies
```

## Getting started

### Prerequisites
- **Node.js 18+** recommended
- **Python 3.10+** recommended
- `pip` for Python packages
- `npm` for frontend packages

### 1. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 2. Install frontend dependencies

```bash
npm install
```

### 3. Configure city settings (optional)

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` to choose a city:

```bash
USE_REAL_CITY=true
CITY_NAME=San Francisco
```

Available cities:
- San Francisco (15 landmarks including Downtown, Mission, SOMA, Marina)
- New York (15 landmarks including Midtown, Times Square, Wall Street)
- London (15 landmarks including Westminster, City, Camden)

Leave `USE_REAL_CITY=false` for the original simulated 8x6 grid.

### 4. Start the backend

```bash
python backend.py
```

The API server starts on `http://localhost:8000`.

### 5. Start the frontend

```bash
npm run dev
```

The Vite app starts on `http://localhost:5173`.

## How to use the app

1. Launch the backend and frontend servers.
2. Open `http://localhost:5173`.
3. Wait for the connection indicator to switch to **Live**.
4. Choose an origin and destination in the control panel.
5. Click **Calculate Route** to request a weighted path.
6. Watch the active route render on the map with ETA.
7. Toggle autonomous AI mode on or off.
8. Observe how anomalies, priority nodes, and AI actions change over time.

## Environment variables

The code includes placeholders for external traffic/data providers via environment variables:

- `USE_REAL_CITY` - Set to `true` to use real city networks instead of grid
- `CITY_NAME` - Choose from: San Francisco, New York, London
- `TOMTOM_API_KEY` - TomTom traffic flow API key
- `HERE_API_KEY` - HERE incident reporting API key
- `GOOGLE_MAPS_API_KEY` - Google Maps directions API key
- `X_BEARER_TOKEN` - X (Twitter) API bearer token for social incident detection

The real city mode uses actual landmark coordinates and calculates realistic road networks using the Haversine formula for distances. Each city has 15 major landmarks connected by arterial, collector, and local roads based on actual distances.

## Why this README is useful for showcasing the project

This project uses a combination of:

- graph algorithms for routing
- neural forecasting for prediction
- AI-style decision logic for operations
- WebSockets for real-time updates
- React visualization for operator workflows
- FastAPI for clean service endpoints

That makes it a good portfolio/demo application for showcasing full-stack engineering, simulation-heavy UI behavior, and AI-assisted operational tooling in a single repository.
