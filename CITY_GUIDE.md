# City Network Configuration Guide

This application can simulate traffic in real city networks or use a generic grid layout.

## Quick Start

### Use a Real City Network

1. Edit the `.env` file:
```bash
USE_REAL_CITY=true
CITY_NAME=San Francisco
```

2. Restart the backend server
3. The app will now use real San Francisco landmarks and distances

### Available Cities

#### San Francisco
- 15 major landmarks including Downtown, Mission, SOMA, Marina, Castro, Haight
- Real geographic coordinates
- Road networks calculated using actual distances
- Typical distance range: 0.5-5 km between connected nodes

#### New York
- 15 major landmarks including Midtown, Times Square, Wall Street, Central Park
- Covers Manhattan and parts of Brooklyn/Queens
- High-density urban network
- Mix of arterial roads and local streets

#### London
- 15 major landmarks including Westminster, City, Camden, Shoreditch
- Central London coverage
- Historic city layout with modern arterials
- Ring roads and local connections

### Switch Between Cities

Just update the `.env` file:

```bash
# For New York
USE_REAL_CITY=true
CITY_NAME=New York

# For London
USE_REAL_CITY=true
CITY_NAME=London

# For simulated grid
USE_REAL_CITY=false
```

## How Real Cities Work

### Geographic Accuracy
- Uses actual latitude/longitude coordinates
- Haversine formula calculates real distances in kilometers
- Road classifications based on distance:
  - Arterial: < 1.2 km (major roads)
  - Collector: 1.2-2.0 km (medium roads)
  - Local: > 2.0 km (minor roads)

### Network Generation
- Landmarks are connected based on proximity
- Each landmark connects to its 4 nearest neighbors
- Roads only created if distance < 5 km
- Ensures realistic urban connectivity

### Traffic Simulation
- Same realistic traffic patterns as grid mode
- Time-of-day multipliers (morning/evening peaks)
- Weather and event impacts
- Sensor degradation simulation
- All AI features work identically

## Visualization

### Grid Mode
- Clean 8x6 grid layout
- Nodes named N0_0, N1_0, etc.
- Evenly spaced positions

### Real City Mode
- Landmarks shown with actual names
- Automatic graph layout algorithm
- Positions based on connectivity
- Maintains geographic relationships

## API Integration

The system is designed to integrate with real traffic APIs:
- TomTom Flow API for live speed factors
- HERE Incident API for road closures
- Google Maps Directions for ETA validation
- X (Twitter) API for social incident detection

Simply add API keys to `.env` to enable live data feeds.
