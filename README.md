# Traffic Control System

A real-time AI-powered traffic control and monitoring system with a modern web interface.

## Features

- Real-time traffic simulation with AI decision engine
- Interactive network visualization
- WebSocket-based live updates
- Route planning and optimization
- Traffic anomaly detection
- Minimalist gradient UI design (white, red, blue palette)

## Architecture

### Backend (Python)
- FastAPI REST API and WebSocket server
- Neural network traffic prediction (LSTM)
- Graph-based routing with NetworkX
- Real-time traffic simulation

### Frontend (React)
- Real-time data visualization
- Interactive traffic map
- Live metrics dashboard
- AI assistant panel
- Responsive gradient design

## Setup

### Backend

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start the backend server:
```bash
python backend.py
```

The backend runs on http://localhost:8000

### Frontend

1. Install Node dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend runs on http://localhost:5173

## Usage

1. Start both backend and frontend servers
2. Open http://localhost:5173 in your browser
3. Select origin and destination nodes
4. Click "Calculate Route" to see optimal paths
5. Toggle AI autonomous control
6. Monitor real-time traffic metrics and predictions

## API Endpoints

- `GET /api/nodes` - Get all network nodes
- `GET /api/edges` - Get all network edges
- `GET /api/traffic` - Get current traffic volumes
- `POST /api/route` - Calculate optimal route
- `POST /api/block` - Block a road segment
- `POST /api/ai/toggle` - Enable/disable AI control
- `GET /api/ai/status` - Get AI system status
- `GET /api/predictions/{node}` - Get traffic predictions
- `WS /ws/traffic` - WebSocket for real-time updates

## Technology Stack

- **Backend**: Python, FastAPI, PyTorch, NetworkX
- **Frontend**: React, Vite, Recharts
- **Communication**: REST API, WebSocket
- **Styling**: CSS with gradients (white, red, blue palette)
