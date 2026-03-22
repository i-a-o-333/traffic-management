import asyncio
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main_system import TrafficSim, Router, NeuralPredictor, AIDecisionEngine, LiveTrafficIntegrator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = Router()
nodes = list(router.G.nodes())
sim = TrafficSim(nodes)
nn = NeuralPredictor()
ai = AIDecisionEngine(sim, router)
live = LiveTrafficIntegrator()

vols = {n: 200.0 for n in nodes}
current_route = {"start": nodes[0], "end": nodes[min(4, len(nodes) - 1)]}
ai_enabled = True


class RouteRequest(BaseModel):
    start: str
    end: str


class BlockRequest(BaseModel):
    node1: str
    node2: str
    duration: int = 30


class AIToggle(BaseModel):
    enabled: bool


@app.get("/api/nodes")
async def get_nodes():
    return {"nodes": nodes}


@app.get("/api/edges")
async def get_edges():
    edges = []
    for u, v in router.G.edges():
        edge_data = router.G[u][v]
        edges.append({
            "source": u,
            "target": v,
            "road_type": edge_data.get("road_type", "local"),
            "length_km": edge_data.get("length_km", 0),
            "speed_kmh": edge_data.get("speed_kmh", 0),
        })
    return {"edges": edges}


@app.get("/api/traffic")
async def get_traffic():
    global vols
    return {
        "volumes": vols,
        "timestamp": datetime.now().isoformat(),
        "blocked_edges": [{"u": u, "v": v, "expiry": exp} for (u, v), exp in router.blocked_edges.items()],
    }


@app.post("/api/route")
async def calculate_route(request: RouteRequest):
    global current_route
    current_route = {"start": request.start, "end": request.end}

    path_edges, route_cost = router.route(request.start, request.end)

    if not path_edges:
        return {"success": False, "message": "No route available"}

    eta_min = (route_cost / 60.0) if route_cost else 0

    return {
        "success": True,
        "path": [e for e in path_edges],
        "cost": route_cost,
        "eta_minutes": eta_min,
        "edges_count": len(path_edges),
    }


@app.post("/api/block")
async def block_edge(request: BlockRequest):
    key = tuple(sorted((request.node1, request.node2)))
    router.block_edge(key[0], key[1], request.duration)
    ai.log("API", f"Edge {key[0]}-{key[1]} blocked for {request.duration}s")
    return {"success": True, "message": f"Blocked {key[0]}-{key[1]} for {request.duration}s"}


@app.post("/api/ai/toggle")
async def toggle_ai(request: AIToggle):
    global ai_enabled
    ai_enabled = request.enabled
    ai.auto_mode = request.enabled
    ai.log("API", f"AI autonomous control {'enabled' if request.enabled else 'disabled'}")
    return {"success": True, "enabled": ai_enabled}


@app.get("/api/ai/status")
async def get_ai_status():
    return {
        "status": ai.status,
        "enabled": ai_enabled,
        "logs": list(ai.logs)[:20],
    }


@app.get("/api/predictions/{node}")
async def get_predictions(node: str):
    if node not in nodes:
        return {"error": "Node not found"}

    pred = nn.predict(node)
    if pred[0] is None:
        return {"warming_up": True}

    mean, std, horizon, conf = pred
    return {
        "node": node,
        "mean": mean,
        "std": std,
        "horizon": horizon,
        "confidence": conf,
        "current": vols.get(node, 0),
    }


@app.get("/api/live/status")
async def get_live_status():
    return {
        "live_mode": live.live_mode,
        "speed_factor": live.speed_factor,
        "provider_status": live.provider_status,
        "last_latency_ms": live.last_latency_ms,
        "incident_count": len(live.incident_points),
        "social_incidents": len(live.social_incidents),
    }


@app.websocket("/ws/traffic")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            global vols

            vols, sim_only = sim.step(live.speed_factor if live.live_mode else 1.0)
            router.check_blocks()
            router.update(vols)

            for n, v in vols.items():
                nn.update(n, v)

            analysis = ai.analyze(vols, current_route["start"], current_route["end"])
            action = ai.maybe_act(analysis)

            path_edges, route_cost = router.route(current_route["start"], current_route["end"])

            data = {
                "volumes": vols,
                "timestamp": datetime.now().isoformat(),
                "blocked_edges": [{"u": u, "v": v} for u, v in router.blocked_edges.keys()],
                "route": {
                    "edges": [[u, v] for u, v in path_edges] if path_edges else [],
                    "cost": route_cost,
                    "eta_minutes": (route_cost / 60.0) if route_cost else 0,
                },
                "ai": {
                    "status": ai.status,
                    "action": action,
                    "priority_nodes": analysis["priority_nodes"],
                    "anomalies": len(analysis["anomalies"]),
                    "trend": analysis["trend"],
                },
                "health": {
                    node: {"quality": sim.health[node].quality, "degraded": sim.health[node].degraded}
                    for node in nodes[:10]
                },
            }

            await websocket.send_json(data)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
