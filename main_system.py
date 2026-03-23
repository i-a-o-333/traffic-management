import os
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import networkx as nx
import numpy as np
import requests
import torch
import torch.nn as nn

ROAD_SPECS = {
    "arterial": {"speed": 55, "lanes": 3, "class_weight": 1.0},
    "collector": {"speed": 42, "lanes": 2, "class_weight": 1.12},
    "local": {"speed": 30, "lanes": 1, "class_weight": 1.3},
    "ring": {"speed": 48, "lanes": 2, "class_weight": 0.95},
}
HISTORY_LENGTH = 120
DEFAULT_VOLUME = 200.0
MAX_VOLUME = 890
SENSOR_DROPOUT_PROBABILITY = 0.015


@dataclass
class DemandConfig:
    morning_peak: tuple[int, int] = (7, 10)
    evening_peak: tuple[int, int] = (16, 20)
    weekend_drop: float = 0.82
    rain_prob: float = 0.14
    event_prob: float = 0.03


@dataclass
class SensorHealth:
    quality: float = 1.0
    dropouts: int = 0
    degraded: bool = False


class TrafficLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(1, 32, batch_first=True)
        self.fc = nn.Linear(32, 1)

    def forward(self, x):
        o, _ = self.lstm(x)
        return self.fc(o[:, -1])


class NeuralPredictor:
    def __init__(self, seq: int = 20):
        self.seq = seq
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = TrafficLSTM().to(self.device)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        self.loss_fn = nn.MSELoss()
        self.buffers: dict[str, list[float]] = {}

    def update(self, node: str, value: float):
        buf = self.buffers.setdefault(node, [])
        buf.append(float(value))
        if len(buf) < self.seq + 1:
            return

        x = torch.tensor(buf[-self.seq - 1 : -1], dtype=torch.float32).view(1, -1, 1).to(self.device)
        y = torch.tensor([buf[-1]], dtype=torch.float32).to(self.device)
        pred = self.model(x).squeeze()
        loss = self.loss_fn(pred, y)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()

        if len(buf) > self.seq * 4:
            self.buffers[node] = buf[-(self.seq + 1) :]

    def predict(self, node: str, steps: int = 12):
        buf = self.buffers.get(node, [])
        if len(buf) < self.seq:
            return None, None, [], 0.0

        x = torch.tensor(buf[-self.seq :], dtype=torch.float32).view(1, -1, 1).to(self.device)
        preds = []
        with torch.no_grad():
            for _ in range(steps):
                pred = self.model(x).item()
                preds.append(pred)
                x = torch.cat([x[:, 1:], torch.tensor([[[pred]]], device=self.device)], dim=1)

        conf = max(0.05, 1.0 - min(1.0, float(np.std(preds) / 250.0)))
        return float(np.mean(preds)), float(np.std(preds) + 1e-3), preds, conf


class LiveTrafficIntegrator:
    """Live data from TomTom/X/HERE/Google with resilient fallbacks."""

    def __init__(self):
        self.tomtom_key = os.getenv("TOMTOM_API_KEY")
        self.here_key = os.getenv("HERE_API_KEY")
        self.google_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.x_bearer = os.getenv("X_BEARER_TOKEN")

        self.last_poll = 0.0
        self.next_poll_s = 35
        self.last_success = 0.0
        self.live_mode = False
        self.last_error = ""

        self.speed_factor = 1.0
        self.incident_points: list[tuple[float, float]] = []
        self.social_incidents: list[str] = []
        self.google_eta_s = None
        self.provider_status = {"TomTom": "idle", "HERE": "idle", "X": "idle", "Google": "idle"}
        self.last_latency_ms = 0

    def should_poll(self):
        return time.time() - self.last_poll >= self.next_poll_s

    def poll_all(self, origin_xy: tuple[float, float] | None, dest_xy: tuple[float, float] | None):
        self.last_poll = time.time()
        self.next_poll_s = random.randint(30, 60)
        started = time.time()
        self.last_error = ""

        success = False

        try:
            self.speed_factor = self.fetch_tomtom_speed_factor()
            self.provider_status["TomTom"] = "ok"
            success = True
        except Exception as exc:
            self.provider_status["TomTom"] = "degraded"
            self.last_error = f"TomTom: {exc}"
            self.speed_factor = 1.0

        try:
            self.incident_points = self.fetch_here_incidents(origin_xy)
            self.provider_status["HERE"] = "ok"
            success = True
        except Exception as exc:
            self.provider_status["HERE"] = "degraded"
            self.last_error = f"{self.last_error} | HERE: {exc}".strip(" |")
            self.incident_points = []

        try:
            self.social_incidents = self.fetch_x_incidents()
            self.provider_status["X"] = "ok" if self.social_incidents is not None else "degraded"
            success = True
        except Exception as exc:
            self.provider_status["X"] = "degraded"
            self.last_error = f"{self.last_error} | X: {exc}".strip(" |")
            self.social_incidents = []

        try:
            self.google_eta_s = self.fetch_google_eta(origin_xy, dest_xy)
            self.provider_status["Google"] = "ok"
            success = True
        except Exception as exc:
            self.provider_status["Google"] = "degraded"
            self.last_error = f"{self.last_error} | Google: {exc}".strip(" |")
            self.google_eta_s = None

        self.live_mode = success
        if success:
            self.last_success = time.time()
        self.last_latency_ms = int((time.time() - started) * 1000)

    def fetch_tomtom_speed_factor(self) -> float:
        if not self.tomtom_key:
            raise RuntimeError("TOMTOM_API_KEY missing")
        lat, lon = 12.9716, 77.5946
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={self.tomtom_key}"
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json().get("flowSegmentData", {})
        current = float(data.get("currentSpeed", 0) or 0)
        freeflow = max(1.0, float(data.get("freeFlowSpeed", 1) or 1))
        if current <= 0:
            raise RuntimeError("TomTom missing currentSpeed")
        jam_factor = np.clip(1.0 - (current / freeflow), 0.0, 1.0)
        return float(np.clip(1.0 - jam_factor * 0.65, 0.2, 1.0))

    def fetch_here_incidents(self, origin_xy: tuple[float, float] | None):
        if not self.here_key or not origin_xy:
            return []
        lon, lat = origin_xy
        bbox = f"{lat-0.08},{lon-0.08},{lat+0.08},{lon+0.08}"
        url = f"https://data.traffic.hereapi.com/v7/incidents?in=bbox:{bbox}&apiKey={self.here_key}"
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        points = []
        for item in data.get("results", [])[:20]:
            loc = item.get("location", {})
            lat_ = loc.get("lat")
            lon_ = loc.get("lng")
            if lat_ is not None and lon_ is not None:
                points.append((lat_, lon_))
        return points

    def fetch_x_incidents(self):
        if not self.x_bearer:
            return []
        query = '("traffic jam Bengaluru" OR "accident Bengaluru highway") filter:news since:2025-02-01'
        url = "https://api.x.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.x_bearer}"}
        params = {"query": query, "max_results": 10}
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        return [item.get("text", "") for item in data.get("data", [])]

    def fetch_google_eta(self, origin_xy: tuple[float, float] | None, dest_xy: tuple[float, float] | None):
        if not self.google_key or not origin_xy or not dest_xy:
            return None
        origin = f"{origin_xy[1]},{origin_xy[0]}"
        dest = f"{dest_xy[1]},{dest_xy[0]}"
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {"origin": origin, "destination": dest, "departure_time": "now", "key": self.google_key}
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        legs = routes[0].get("legs", [])
        if not legs:
            return None
        return legs[0].get("duration_in_traffic", {}).get("value") or legs[0].get("duration", {}).get("value")

    def live_badge(self):
        if self.live_mode:
            age = int(time.time() - self.last_success)
            return f"Live: TomTom • Updated {age}s ago"
        return "Live: Simulation only"

    def provider_badge(self):
        parts = [f"{name}:{'OK' if status == 'ok' else 'WARN'}" for name, status in self.provider_status.items()]
        return " | ".join(parts) + f" | Latency:{self.last_latency_ms}ms"


class TrafficSim:
    def __init__(self, nodes):
        self.cfg = DemandConfig()
        self.nodes = nodes
        self.phase = np.random.rand(len(nodes)) * 10
        self.hist = self._build_history_buffers()
        self.hist_sim = self._build_history_buffers()
        self.hist_real = self._build_history_buffers()
        self.ema = {n: DEFAULT_VOLUME for n in self.nodes}
        self.health = {n: SensorHealth() for n in self.nodes}
        self.last_context = "Clear"

    def _build_history_buffers(self):
        return {node: deque([DEFAULT_VOLUME] * HISTORY_LENGTH, maxlen=HISTORY_LENGTH) for node in self.nodes}

    def calibrate_from_historical(self, traffic_integrator: LiveTrafficIntegrator):
        if traffic_integrator.tomtom_key:
            self.cfg.morning_peak = (7, 11)
            self.cfg.evening_peak = (16, 21)
            self.cfg.weekend_drop = 0.78

    def _update_sensor_health(self, node: str, effective_volume: float):
        health = self.health[node]
        if random.random() < SENSOR_DROPOUT_PROBABILITY:
            effective_volume = self.ema[node]
            health.dropouts += 1
            health.quality = max(0.2, health.quality - 0.08)
        else:
            health.quality = min(1.0, health.quality + 0.01)
        health.degraded = health.quality < 0.55
        return effective_volume

    def _hour_multiplier(self, now: datetime) -> float:
        hour = now.hour + now.minute / 60.0
        demand_multiplier = 1.0
        if self.cfg.morning_peak[0] <= hour <= self.cfg.morning_peak[1]:
            demand_multiplier *= 1.35
        if self.cfg.evening_peak[0] <= hour <= self.cfg.evening_peak[1]:
            demand_multiplier *= 1.45
        if now.weekday() >= 5:
            demand_multiplier *= self.cfg.weekend_drop
        return demand_multiplier

    def _context(self):
        weather_factor = 1.0
        event_factor = 1.0
        cause = "Clear"
        if random.random() < self.cfg.rain_prob:
            weather_factor *= random.uniform(0.86, 0.95)
            cause = "Rain impact"
        if random.random() < self.cfg.event_prob:
            event_factor *= random.uniform(1.08, 1.30)
            cause = "City event surge"
        return weather_factor, event_factor, cause

    def step(self, speed_factor: float = 1.0):
        now = datetime.now()
        t = time.monotonic()
        demand_multiplier = self._hour_multiplier(now)
        weather_factor, event_factor, cause = self._context()
        self.last_context = cause

        output = {}
        simulated_only = {}
        for index, node in enumerate(self.nodes):
            base = 220 + 40 * np.sin(t / 60)
            wave = 120 * np.sin(t / 10 + self.phase[index])
            noise = np.random.normal(0, 15)
            simulated_volume = np.clip((base + wave + noise) * demand_multiplier * weather_factor * event_factor, 30, MAX_VOLUME)
            effective_volume = simulated_volume * speed_factor
            effective_volume = self._update_sensor_health(node, effective_volume)

            self.ema[node] = 0.2 * effective_volume + 0.8 * self.ema[node]
            smoothed_volume = float(self.ema[node])
            self.hist[node].append(smoothed_volume)
            self.hist_sim[node].append(float(simulated_volume))
            self.hist_real[node].append(float(effective_volume))
            output[node] = smoothed_volume
            simulated_only[node] = float(simulated_volume)
        return output, simulated_only


class Router:
    def __init__(self, city="SimCity Grid", grid_w=8, grid_h=6, spacing_km=0.7):
        self.city = city
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.spacing_km = spacing_km
        self.G = nx.Graph()
        self.blocked_edges = {}
        self._build_simulated_city()
        self.nodes = list(self.G.nodes())

    def _node_name(self, x, y):
        return f"N{x}_{y}"

    def normalize_edge(self, u, v):
        return tuple(sorted((u, v)))

    def _add_road(self, u, v, length_km, road_type):
        spec = ROAD_SPECS[road_type]
        speed = spec["speed"]
        lanes = spec["lanes"]
        freeflow_s = max(8.0, (length_km / max(speed, 5)) * 3600.0)
        capacity = max(220.0, lanes * speed * 12.0)
        self.G.add_edge(
            u,
            v,
            freeflow_s=freeflow_s,
            capacity=capacity,
            w=freeflow_s,
            road_type=road_type,
            length_km=length_km,
            lanes=lanes,
            speed_kmh=speed,
        )

    def _build_simulated_city(self):
        base_lon, base_lat = 77.56, 12.93

        for y in range(self.grid_h):
            for x in range(self.grid_w):
                node = self._node_name(x, y)
                self.G.add_node(
                    node,
                    x=base_lon + x * 0.01,
                    y=base_lat + y * 0.01,
                    zone=("CBD" if 2 <= x <= 5 and 2 <= y <= 4 else "URBAN"),
                )

        for y in range(self.grid_h):
            for x in range(self.grid_w - 1):
                road_type = "arterial" if y in (2, 3) else "collector"
                self._add_road(self._node_name(x, y), self._node_name(x + 1, y), self.spacing_km, road_type)

        for x in range(self.grid_w):
            for y in range(self.grid_h - 1):
                road_type = "arterial" if x in (3, 4) else "collector"
                self._add_road(self._node_name(x, y), self._node_name(x, y + 1), self.spacing_km, road_type)

        for x in range(1, self.grid_w - 1, 2):
            for y in range(1, self.grid_h - 1, 2):
                self._add_road(self._node_name(x, y), self._node_name(x + 1, y + 1), self.spacing_km * 1.35, "local")

        ring_inner = [
            self._node_name(x, 1) for x in range(1, self.grid_w - 1)
        ] + [
            self._node_name(self.grid_w - 2, y) for y in range(2, self.grid_h - 1)
        ] + [
            self._node_name(x, self.grid_h - 2) for x in range(self.grid_w - 3, 0, -1)
        ] + [
            self._node_name(1, y) for y in range(self.grid_h - 3, 1, -1)
        ]
        for index in range(len(ring_inner)):
            self._add_road(ring_inner[index], ring_inner[(index + 1) % len(ring_inner)], self.spacing_km, "ring")

        for x in range(self.grid_w - 1):
            self._add_road(self._node_name(x, 0), self._node_name(x + 1, 0), self.spacing_km * 1.15, "ring")
            self._add_road(self._node_name(x, self.grid_h - 1), self._node_name(x + 1, self.grid_h - 1), self.spacing_km * 1.15, "ring")

        for y in range(self.grid_h - 1):
            self._add_road(self._node_name(0, y), self._node_name(0, y + 1), self.spacing_km * 1.15, "ring")
            self._add_road(self._node_name(self.grid_w - 1, y), self._node_name(self.grid_w - 1, y + 1), self.spacing_km * 1.15, "ring")

    def block_edge(self, u, v, duration=30):
        self.blocked_edges[self.normalize_edge(u, v)] = time.time() + duration

    def block_incident_near(self, lat: float, lon: float, duration=45):
        nearest = None
        nearest_distance = 1e9
        for u, v in self.G.edges():
            ux, uy = self.G.nodes[u]["x"], self.G.nodes[u]["y"]
            vx, vy = self.G.nodes[v]["x"], self.G.nodes[v]["y"]
            cx, cy = (ux + vx) / 2.0, (uy + vy) / 2.0
            distance = (cx - lon) ** 2 + (cy - lat) ** 2
            if distance < nearest_distance:
                nearest_distance = distance
                nearest = (u, v)
        if nearest:
            self.block_edge(nearest[0], nearest[1], duration)
            return nearest
        return None

    def check_blocks(self):
        now = time.time()
        expired = [edge for edge, expiry in self.blocked_edges.items() if expiry < now]
        for edge in expired:
            del self.blocked_edges[edge]
        return self.blocked_edges

    def update(self, vols, signal_boost=0.0):
        alpha, beta = 0.2, 3.2
        for u, v in self.G.edges():
            edge = self.G[u][v]
            if self.normalize_edge(u, v) in self.blocked_edges:
                edge["w"] = 1e9
                continue

            class_weight = ROAD_SPECS[edge["road_type"]]["class_weight"]
            flow = max(1.0, (vols[u] + vols[v]) / 2.0) * class_weight
            capacity = edge["capacity"] * (1.0 + signal_boost)
            ratio = flow / capacity
            delay = edge["freeflow_s"] * (1 + alpha * (ratio**beta))
            edge["w"] = max(edge["freeflow_s"], delay)

    def route(self, a, b):
        try:
            path = nx.dijkstra_path(self.G, a, b, weight="w")
            cost = nx.path_weight(self.G, path, weight="w")
            if cost >= 1e8:
                return [], None
            return list(zip(path, path[1:])), cost
        except nx.NetworkXNoPath:
            return [], None


class AIDecisionEngine:
    def __init__(self, sim: TrafficSim, router: Router):
        self.sim = sim
        self.router = router
        self.status = "ONLINE"
        self.auto_mode = True
        self.response_delay_s = 1.8
        self.last_action_time = 0.0
        self.logs = deque(maxlen=500)

    def log(self, kind, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.appendleft(f"[{ts}] {kind:<10} {msg}")

    def _calculate_efficiency_delta(self, vols, origin, dest, route_cost):
        if not route_cost:
            return 0.0

        self.router.update(vols, signal_boost=0.0)
        _, base_cost = self.router.route(origin, dest)
        self.router.update(vols, signal_boost=0.12)
        _, adaptive_cost = self.router.route(origin, dest)
        self.router.update(vols)

        if not (base_cost and adaptive_cost):
            return 0.0
        return (base_cost - adaptive_cost) / max(base_cost, 1)

    def _determine_trend(self, dest):
        history = list(self.sim.hist[dest])
        if len(history) <= 15:
            return "stable"

        previous_window = np.mean(history[-15:-8])
        current_window = np.mean(history[-7:])
        if current_window - previous_window > 25:
            return "increasing"
        if previous_window - current_window > 25:
            return "decreasing"
        return "stable"

    def analyze(self, vols, origin, dest):
        self.status = "ANALYZING"
        priority = [node for node, _ in sorted(vols.items(), key=lambda item: item[1], reverse=True)[:3]]
        anomalies = []
        for node, volume in vols.items():
            history = list(self.sim.hist[node])
            if len(history) < 12:
                continue
            baseline = float(np.mean(history[-12:-2]))
            delta = volume - baseline
            if delta > 140:
                anomalies.append((node, "surge", delta))
            elif delta < -120:
                anomalies.append((node, "drop", delta))

        health_issues = [node for node, health in self.sim.health.items() if health.degraded]
        _, route_cost = self.router.route(origin, dest)
        efficiency_delta = self._calculate_efficiency_delta(vols, origin, dest, route_cost)
        trend = self._determine_trend(dest)

        if anomalies:
            self.status = "ALERT"
            node, kind, delta = anomalies[0]
            self.log("INCIDENT", f"Anomaly at {node}: {kind} ({delta:+.1f})")
        elif route_cost and route_cost > 850:
            self.status = "OPTIMIZING"
            self.log("ROUTING", "Route optimality degraded significantly; rerouting recommended")

        if health_issues:
            self.log("HEALTH", f"Sensor degraded: {', '.join(health_issues[:4])}")

        return {
            "priority_nodes": priority,
            "anomalies": anomalies,
            "health_issues": health_issues,
            "trend": trend,
            "efficiency_delta": efficiency_delta,
        }

    def maybe_act(self, analysis):
        if not self.auto_mode:
            return "Autonomous mode OFF"
        if time.time() - self.last_action_time < self.response_delay_s:
            return "AI waiting response delay"

        self.last_action_time = time.time()
        if analysis["anomalies"]:
            hot_node = analysis["anomalies"][0][0]
            neighbors = list(self.router.G.neighbors(hot_node))
            if neighbors:
                blocked_u, blocked_v = self.router.normalize_edge(hot_node, neighbors[0])
                self.router.block_edge(blocked_u, blocked_v, duration=12)
                msg = f"Auto-control blocked {blocked_u}-{blocked_v} for incident isolation"
                self.log("ACTION", msg)
                return msg
        if analysis["efficiency_delta"] > 0.03:
            msg = f"Adaptive signal timing applied, efficiency +{analysis['efficiency_delta'] * 100:.1f}%"
            self.log("ACTION", msg)
            return msg
        return "Monitoring"
