import os
import random
import time
import numpy as np
import torch
import torch.nn as nn
import networkx as nx
from collections import deque
from dataclasses import dataclass
from datetime import datetime


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
                p = self.model(x).item()
                preds.append(p)
                x = torch.cat([x[:, 1:], torch.tensor([[[p]]], device=self.device)], dim=1)

        conf = max(0.05, 1.0 - min(1.0, float(np.std(preds) / 250.0)))
        return float(np.mean(preds)), float(np.std(preds) + 1e-3), preds, conf


class LiveTrafficIntegrator:
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


class TrafficSim:
    def __init__(self, nodes):
        self.cfg = DemandConfig()
        self.nodes = nodes
        self.phase = np.random.rand(len(nodes)) * 10
        self.hist = {n: deque([200.0] * 120, maxlen=120) for n in self.nodes}
        self.hist_sim = {n: deque([200.0] * 120, maxlen=120) for n in self.nodes}
        self.hist_real = {n: deque([200.0] * 120, maxlen=120) for n in self.nodes}
        self.ema = {n: 200.0 for n in self.nodes}
        self.health = {n: SensorHealth() for n in self.nodes}
        self.last_context = "Clear"

    def _hour_multiplier(self, now: datetime) -> float:
        h = now.hour + now.minute / 60.0
        m = 1.0
        if self.cfg.morning_peak[0] <= h <= self.cfg.morning_peak[1]:
            m *= 1.35
        if self.cfg.evening_peak[0] <= h <= self.cfg.evening_peak[1]:
            m *= 1.45
        if now.weekday() >= 5:
            m *= self.cfg.weekend_drop
        return m

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
        demand_mult = self._hour_multiplier(now)
        weather_factor, event_factor, cause = self._context()
        self.last_context = cause

        out = {}
        sim_only = {}
        for i, n in enumerate(self.nodes):
            base = 220 + 40 * np.sin(t / 60)
            wave = 120 * np.sin(t / 10 + self.phase[i])
            noise = np.random.normal(0, 15)
            simulated_vol = np.clip((base + wave + noise) * demand_mult * weather_factor * event_factor, 30, 890)

            live_scaled = simulated_vol * speed_factor
            real_vol = speed_factor * live_scaled + (1 - speed_factor) * simulated_vol

            health = self.health[n]
            if random.random() < 0.015:
                real_vol = self.ema[n]
                health.dropouts += 1
                health.quality = max(0.2, health.quality - 0.08)
            else:
                health.quality = min(1.0, health.quality + 0.01)
            health.degraded = health.quality < 0.55

            self.ema[n] = 0.2 * real_vol + 0.8 * self.ema[n]
            v = float(self.ema[n])
            self.hist[n].append(v)
            self.hist_sim[n].append(float(simulated_vol))
            self.hist_real[n].append(float(real_vol))
            out[n] = v
            sim_only[n] = float(simulated_vol)
        return out, sim_only


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

    def _add_road(self, u, v, length_km, road_type):
        spec = {
            "arterial": {"speed": 55, "lanes": 3},
            "collector": {"speed": 42, "lanes": 2},
            "local": {"speed": 30, "lanes": 1},
            "ring": {"speed": 48, "lanes": 2},
        }[road_type]
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
                n = self._node_name(x, y)
                self.G.add_node(
                    n,
                    x=base_lon + x * 0.01,
                    y=base_lat + y * 0.01,
                    zone=("CBD" if 2 <= x <= 5 and 2 <= y <= 4 else "URBAN"),
                )

        for y in range(self.grid_h):
            for x in range(self.grid_w - 1):
                u, v = self._node_name(x, y), self._node_name(x + 1, y)
                road_type = "arterial" if y in (2, 3) else "collector"
                self._add_road(u, v, self.spacing_km, road_type)

        for x in range(self.grid_w):
            for y in range(self.grid_h - 1):
                u, v = self._node_name(x, y), self._node_name(x, y + 1)
                road_type = "arterial" if x in (3, 4) else "collector"
                self._add_road(u, v, self.spacing_km, road_type)

        for x in range(1, self.grid_w - 1, 2):
            for y in range(1, self.grid_h - 1, 2):
                a = self._node_name(x, y)
                b = self._node_name(x + 1, y + 1)
                self._add_road(a, b, self.spacing_km * 1.35, "local")

        ring_inner = [self._node_name(x, 1) for x in range(1, self.grid_w - 1)] + [self._node_name(self.grid_w - 2, y) for y in range(2, self.grid_h - 1)] + [self._node_name(x, self.grid_h - 2) for x in range(self.grid_w - 3, 0, -1)] + [self._node_name(1, y) for y in range(self.grid_h - 3, 1, -1)]
        for i in range(len(ring_inner)):
            self._add_road(ring_inner[i], ring_inner[(i + 1) % len(ring_inner)], self.spacing_km, "ring")

        for x in range(self.grid_w - 1):
            self._add_road(self._node_name(x, 0), self._node_name(x + 1, 0), self.spacing_km * 1.15, "ring")
            self._add_road(self._node_name(x, self.grid_h - 1), self._node_name(x + 1, self.grid_h - 1), self.spacing_km * 1.15, "ring")

        for y in range(self.grid_h - 1):
            self._add_road(self._node_name(0, y), self._node_name(0, y + 1), self.spacing_km * 1.15, "ring")
            self._add_road(self._node_name(self.grid_w - 1, y), self._node_name(self.grid_w - 1, y + 1), self.spacing_km * 1.15, "ring")

    def block_edge(self, u, v, duration=30):
        self.blocked_edges[tuple(sorted((u, v)))] = time.time() + duration

    def check_blocks(self):
        now = time.time()
        expired = [k for k, expiry in self.blocked_edges.items() if expiry < now]
        for k in expired:
            del self.blocked_edges[k]
        return self.blocked_edges

    def update(self, vols, signal_boost=0.0):
        alpha, beta = 0.2, 3.2
        for u, v in self.G.edges():
            key = tuple(sorted((u, v)))
            edge = self.G[u][v]
            if key in self.blocked_edges:
                edge["w"] = 1e9
                continue

            class_weight = {"arterial": 1.0, "ring": 0.95, "collector": 1.12, "local": 1.3}[edge["road_type"]]
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

    def analyze(self, vols, origin, dest):
        self.status = "ANALYZING"
        priority = [n for n, _ in sorted(vols.items(), key=lambda x: x[1], reverse=True)[:3]]
        anomalies = []
        for node, v in vols.items():
            s = list(self.sim.hist[node])
            if len(s) < 12:
                continue
            baseline = float(np.mean(s[-12:-2]))
            delta = v - baseline
            if delta > 140:
                anomalies.append((node, "surge", delta))
            elif delta < -120:
                anomalies.append((node, "drop", delta))

        health_issues = [n for n, h in self.sim.health.items() if h.degraded]
        _, route_cost = self.router.route(origin, dest)

        efficiency_delta = 0.0
        if route_cost:
            self.router.update(vols, signal_boost=0.0)
            _, base_cost = self.router.route(origin, dest)
            self.router.update(vols, signal_boost=0.12)
            _, adaptive_cost = self.router.route(origin, dest)
            if base_cost and adaptive_cost:
                efficiency_delta = (base_cost - adaptive_cost) / max(base_cost, 1)

        trend = "stable"
        hist = list(self.sim.hist[dest])
        if len(hist) > 15:
            prev = np.mean(hist[-15:-8])
            curr = np.mean(hist[-7:])
            trend = "increasing" if curr - prev > 25 else "decreasing" if prev - curr > 25 else "stable"

        if anomalies:
            self.status = "ALERT"
            n, k, d = anomalies[0]
            self.log("INCIDENT", f"Anomaly at {n}: {k} ({d:+.1f})")
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
            hot = analysis["anomalies"][0][0]
            neighbors = list(self.router.G.neighbors(hot))
            if neighbors:
                edge = tuple(sorted((hot, neighbors[0])))
                self.router.block_edge(edge[0], edge[1], duration=12)
                msg = f"Auto-control blocked {edge[0]}-{edge[1]} for incident isolation"
                self.log("ACTION", msg)
                return msg
        if analysis["efficiency_delta"] > 0.03:
            msg = f"Adaptive signal timing applied, efficiency +{analysis['efficiency_delta']*100:.1f}%"
            self.log("ACTION", msg)
            return msg
        return "Monitoring"
