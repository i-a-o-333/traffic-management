import asyncio
from datetime import datetime

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
nodes = router.nodes
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


def serialize_blocked_edges(include_expiry: bool = False):
    blocked_edges = []
    for (u, v), expiry in router.blocked_edges.items():
        edge = {"u": u, "v": v}
        if include_expiry:
            edge["expiry"] = expiry
        blocked_edges.append(edge)
    return blocked_edges


def build_route_payload(path_edges, route_cost):
    return {
        "edges": [[u, v] for u, v in path_edges] if path_edges else [],
        "cost": route_cost,
        "eta_minutes": (route_cost / 60.0) if route_cost else 0,
    }


def serialize_node_positions():
    return {
        node: {
            "x": router.G.nodes[node].get("x"),
            "y": router.G.nodes[node].get("y"),
        }
        for node in nodes
    }


@app.get("/api/nodes")
async def get_nodes():
    return {
        "nodes": nodes,
        "positions": serialize_node_positions(),
        "city": router.city,
        "city_source": router.city_source,
        "city_center": router.city_center,
    }


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
    return {
        "volumes": vols,
        "timestamp": datetime.now().isoformat(),
        "blocked_edges": serialize_blocked_edges(include_expiry=True),
    }


@app.post("/api/route")
async def calculate_route(request: RouteRequest):
    global current_route
    current_route = {"start": request.start, "end": request.end}

    path_edges, route_cost = router.route(request.start, request.end)
    if not path_edges:
        return {"success": False, "message": "No route available"}

    route = build_route_payload(path_edges, route_cost)
    return {
        "success": True,
        "path": route["edges"],
        "cost": route["cost"],
        "eta_minutes": route["eta_minutes"],
        "edges_count": len(path_edges),
    }


@app.post("/api/block")
async def block_edge(request: BlockRequest):
    blocked_u, blocked_v = router.normalize_edge(request.node1, request.node2)
    router.block_edge(blocked_u, blocked_v, request.duration)
    ai.log("API", f"Edge {blocked_u}-{blocked_v} blocked for {request.duration}s")
    return {"success": True, "message": f"Blocked {blocked_u}-{blocked_v} for {request.duration}s"}


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
        "external_eta_s": live.external_eta_s,
    }


@app.websocket("/ws/traffic")
async def websocket_endpoint(websocket: WebSocket):
    global vols

    await websocket.accept()

    try:
        while True:
            vols, _ = sim.step(live.speed_factor if live.live_mode else 1.0)
            router.check_blocks()
            router.update(vols)

            for node, volume in vols.items():
                nn.update(node, volume)

            analysis = ai.analyze(vols, current_route["start"], current_route["end"])
            action = ai.maybe_act(analysis)
            path_edges, route_cost = router.route(current_route["start"], current_route["end"])

            await websocket.send_json({
                "volumes": vols,
                "timestamp": datetime.now().isoformat(),
                "blocked_edges": serialize_blocked_edges(),
                "route": build_route_payload(path_edges, route_cost),
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
                "city": {
                    "name": router.city,
                    "source": router.city_source,
                    "center": router.city_center,
                },
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
