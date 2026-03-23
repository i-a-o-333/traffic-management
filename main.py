import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import FancyArrowPatch

from main_system import AIDecisionEngine, LiveTrafficIntegrator, NeuralPredictor, Router, TrafficSim

plt.style.use("dark_background")

MAX_VOL = 900
UPDATE_MS = 1000
BLOCK_DURATION = 30
PRED_HORIZON = 12


class VoiceAlert:
    def __init__(self):
        self.enabled = True
        self._engine = None
        self._last_spoken = 0.0
        self.cooldown_s = 4.0
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 170)
            self._engine.setProperty("volume", 0.9)
        except Exception:
            self.enabled = False

    def speak(self, text: str):
        if not self.enabled:
            return
        if time.time() - self._last_spoken < self.cooldown_s:
            return
        self._last_spoken = time.time()
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            self.enabled = False


class Dashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI TRAFFIC CONTROL • CENTRAL COMMAND")
        self.root.geometry("1900x1000")
        self.root.configure(bg="#121212")

        self.router = Router()
        self.nodes = list(self.router.G.nodes())
        self.sim = TrafficSim(self.nodes)
        self.nn = NeuralPredictor()
        self.ai = AIDecisionEngine(self.sim, self.router)
        self.voice = VoiceAlert()
        self.live = LiveTrafficIntegrator()
        self.sim.calibrate_from_historical(self.live)

        self.vols = {n: 200.0 for n in self.nodes}

        self.start_node = tk.StringVar(value=self.nodes[0])
        self.end_node = tk.StringVar(value=self.nodes[min(4, len(self.nodes) - 1)])
        self.route_text = tk.StringVar(value="Initializing...")
        self.ai_status = tk.StringVar(value="ONLINE")
        self.confidence_text = tk.StringVar(value="Confidence: N/A")
        self.trend_text = tk.StringVar(value="Trend: stable")
        self.eff_text = tk.StringVar(value="Route Efficiency: --")
        self.health_text = tk.StringVar(value="Sensors: healthy")
        self.data_source_text = tk.StringVar(value="Live: Simulation only")
        self.travel_overlay_text = tk.StringVar(value="ETA Overlay: --")
        self.eta_gap_text = tk.StringVar(value="ETA Gap: --")
        self.provider_status_text = tk.StringVar(value="Providers: idle")

        self.auto_mode_var = tk.BooleanVar(value=True)
        self.poll_queue: queue.Queue = queue.Queue()
        self.poll_inflight = False
        self.avatar_question = tk.StringVar(value="ETA summary")
        self.avatar_message = tk.StringVar(value="Hi! I'm NavAI. Click me for route and prediction insights.")
        self.last_eta_local = None
        self.last_eta_google = None
        self.last_conf = 0.0
        self.last_trend = "stable"
        self.last_action_msg = "Monitoring"

        self._setup_layout()
        self._panel_accident_controls()
        self._panel_route_planning()
        self._panel_traffic_display()
        self._panel_avatar()

        self.tick()

    def _setup_layout(self):
        self.pan_left = tk.Frame(self.root, bg="#1e1e1e", width=360)
        self.pan_left.pack(side="left", fill="y", padx=5, pady=5)
        self.pan_left.pack_propagate(False)

        self.pan_right = tk.Frame(self.root, bg="#121212")
        self.pan_right.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.pan_top = tk.Frame(self.pan_right, bg="#1e1e1e", height=260)
        self.pan_top.pack(side="top", fill="x", pady=(0, 5))
        self.pan_top.pack_propagate(False)

        self.pan_btm = tk.Frame(self.pan_right, bg="#1e1e1e")
        self.pan_btm.pack(side="bottom", fill="both", expand=True)

    def _panel_accident_controls(self):
        tk.Label(self.pan_left, text="⚠️ INCIDENT CONTROLS", font=("Helvetica", 16, "bold"), bg="#1e1e1e", fg="#ff5555").pack(pady=8)
        ttk.Checkbutton(self.pan_left, text="AI Autonomous Control", variable=self.auto_mode_var, command=self._toggle_auto).pack(pady=4)

        self.lbl_ai_state = tk.Label(self.pan_left, textvariable=self.ai_status, font=("Consolas", 12, "bold"), bg="#1e1e1e", fg="#00ff90")
        self.lbl_ai_state.pack(pady=4)

        canvas = tk.Canvas(self.pan_left, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.pan_left, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg="#1e1e1e")
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.edge_buttons = {}
        for u, v in list(self.router.G.edges())[:180]:
            key = self.router.normalize_edge(u, v)
            holder = tk.Frame(self.scroll_frame, bg="#1e1e1e", pady=1)
            holder.pack(fill="x", padx=8)
            btn = tk.Button(holder, text=f"{u} ↔ {v}", font=("Consolas", 8), bg="#333333", fg="white", relief="flat", height=1, command=lambda k=key: self.trigger_blockage(k))
            btn.pack(fill="x")
            self.edge_buttons[key] = btn

    def _toggle_auto(self):
        self.ai.auto_mode = self.auto_mode_var.get()
        self.ai.log("MODE", "Autonomous control enabled" if self.ai.auto_mode else "Autonomous control disabled")

    def _panel_route_planning(self):
        tk.Label(self.pan_top, text="🗺️ REALISTIC SIMULATED CITY ROUTE PLANNING", font=("Helvetica", 15, "bold"), bg="#1e1e1e", fg="#44aaff").pack(pady=8)
        ctl = tk.Frame(self.pan_top, bg="#1e1e1e")
        ctl.pack(pady=4)

        tk.Label(ctl, text="ORIGIN:", font=("Arial", 11, "bold"), bg="#1e1e1e", fg="white").pack(side="left", padx=8)
        om_from = tk.OptionMenu(ctl, self.start_node, *self.nodes)
        om_from.config(font=("Arial", 10), bg="#333333", fg="white", width=10)
        om_from.pack(side="left")

        tk.Label(ctl, text=" ➔ ", font=("Arial", 13), bg="#1e1e1e", fg="white").pack(side="left", padx=5)

        tk.Label(ctl, text="DESTINATION:", font=("Arial", 11, "bold"), bg="#1e1e1e", fg="white").pack(side="left", padx=8)
        om_to = tk.OptionMenu(ctl, self.end_node, *self.nodes)
        om_to.config(font=("Arial", 10), bg="#333333", fg="white", width=10)
        om_to.pack(side="left")

        self.lbl_status = tk.Label(self.pan_top, text="STATUS: ONLINE", font=("Arial", 12, "bold"), bg="#1e1e1e", fg="#00ff00")
        self.lbl_status.pack(pady=4)

        tk.Label(self.pan_top, textvariable=self.route_text, font=("Consolas", 10), bg="#222222", fg="#ffff00", wraplength=1100).pack(pady=4, fill="x", padx=20)

        info = tk.Frame(self.pan_top, bg="#1e1e1e")
        info.pack(fill="x")
        for sv, color in [
            (self.confidence_text, "#9ad0ff"),
            (self.trend_text, "#ffc857"),
            (self.eff_text, "#a3ffb5"),
            (self.health_text, "#ff9b9b"),
            (self.travel_overlay_text, "#cdb4ff"),
            (self.eta_gap_text, "#ffd166"),
        ]:
            tk.Label(info, textvariable=sv, bg="#1e1e1e", fg=color, font=("Consolas", 9)).pack(side="left", padx=10)

        tk.Label(self.pan_top, textvariable=self.provider_status_text, bg="#1e1e1e", fg="#9de0ad", font=("Consolas", 8)).pack(pady=(1, 0))

    def _panel_avatar(self):
        self.avatar_panel = tk.Frame(self.pan_btm, bg="#0f1720", bd=1, relief="ridge")
        self.avatar_panel.place(relx=0.985, rely=0.985, anchor="se")

        tk.Label(self.avatar_panel, text="NAV AI ASSISTANT", font=("Consolas", 9, "bold"), bg="#0f1720", fg="#8bd3ff").pack(pady=(6, 2), padx=8)

        self.avatar_canvas = tk.Canvas(self.avatar_panel, width=68, height=68, bg="#0f1720", highlightthickness=0, cursor="hand2")
        self.avatar_canvas.pack()
        self.avatar_canvas.create_oval(10, 8, 58, 56, fill="#2f4b7c", outline="#90caf9", width=2)
        self.avatar_canvas.create_oval(24, 24, 30, 30, fill="white", outline="")
        self.avatar_canvas.create_oval(38, 24, 44, 30, fill="white", outline="")
        self.avatar_canvas.create_arc(22, 30, 46, 48, start=200, extent=140, style="arc", outline="#d4f1ff", width=2)

        qbar = tk.Frame(self.avatar_panel, bg="#0f1720")
        qbar.pack(fill="x", padx=6, pady=4)
        tk.OptionMenu(qbar, self.avatar_question, "ETA summary", "Prediction outlook", "Traffic health", "Best action").pack(side="left")
        tk.Button(qbar, text="Ask", command=self._on_avatar_interact, bg="#1f2f4a", fg="white", relief="flat").pack(side="left", padx=4)

        action_bar = tk.Frame(self.avatar_panel, bg="#0f1720")
        action_bar.pack(fill="x", padx=6, pady=(0, 4))
        tk.Button(action_bar, text="Why?", command=self._on_avatar_why, bg="#2b3f61", fg="white", relief="flat").pack(side="left")
        tk.Button(action_bar, text="Apply Reroute", command=lambda: self._on_avatar_action("reroute"), bg="#2f855a", fg="white", relief="flat").pack(side="left", padx=4)
        tk.Button(action_bar, text="Silence 5m", command=lambda: self._on_avatar_action("silence"), bg="#7b341e", fg="white", relief="flat").pack(side="left")

        self.avatar_bubble = tk.Label(self.avatar_panel, textvariable=self.avatar_message, justify="left", wraplength=260, font=("Consolas", 8), bg="#111827", fg="#d6f3ff")
        self.avatar_bubble.pack(fill="x", padx=6, pady=(0, 7))

        self.avatar_canvas.bind("<Button-1>", lambda _e: self._on_avatar_interact())

    def _avatar_response(self):
        ask = self.avatar_question.get()
        eta_local = f"{self.last_eta_local:.1f} min" if self.last_eta_local is not None else "N/A"
        eta_google = f"{self.last_eta_google:.1f} min" if self.last_eta_google is not None else "N/A"
        conf = f"{self.last_conf*100:.1f}%" if self.last_conf else "warming"

        if ask == "ETA summary":
            return f"ETA check: Dijkstra {eta_local}; Google {eta_google}. {self.eta_gap_text.get()}."
        if ask == "Prediction outlook":
            return f"Prediction is {self.last_trend} with confidence {conf}."
        if ask == "Traffic health":
            return f"System health: {self.health_text.get()}. Data feed: {self.data_source_text.get()}."
        return f"Recommended action: {self.last_action_msg}."

    def _on_avatar_interact(self):
        msg = self._avatar_response()
        self.avatar_message.set(msg)
        self.ai.log("AVATAR", msg)

    def _on_avatar_why(self):
        why = f"Why: AI={self.ai_status.get()}, {self.eta_gap_text.get()}, trend={self.last_trend}, confidence={self.last_conf*100:.1f}%"
        self.avatar_message.set(why)
        self.ai.log("AVATAR", why)

    def _on_avatar_action(self, action: str):
        if action == "reroute":
            self.ai.log("AVATAR", "Operator accepted reroute recommendation")
            self.avatar_message.set("Reroute acknowledged. AI will prioritize lowest ETA corridors.")
        elif action == "silence":
            self.voice._last_spoken = time.time() + 300
            self.ai.log("AVATAR", "Voice alerts muted for 5 minutes")
            self.avatar_message.set("Voice alerts muted for five minutes.")

    def _launch_live_poll(self, origin_xy, dest_xy):
        if self.poll_inflight:
            return

        def worker():
            self.live.poll_all(origin_xy, dest_xy)
            self.poll_queue.put("done")

        self.poll_inflight = True
        threading.Thread(target=worker, daemon=True).start()

    def _consume_live_poll_result(self):
        got = False
        while True:
            try:
                self.poll_queue.get_nowait()
            except queue.Empty:
                break
            got = True

        if got:
            self.poll_inflight = False
            if self.live.live_mode:
                self.ai.log("LIVE", "Fetched TomTom/HERE/Google feeds")
            else:
                self.ai.log("WARN", "Live API unavailable; reverting to simulation")

    def _panel_traffic_display(self):
        self.frame_graph = tk.Frame(self.pan_btm, bg="#000000")
        self.frame_graph.pack(side="left", fill="both", expand=True)

        self.frame_metrics = tk.Frame(self.pan_btm, bg="#1e1e1e", width=600)
        self.frame_metrics.pack(side="right", fill="y")
        self.frame_metrics.pack_propagate(False)

        self.figN, self.axN = plt.subplots(figsize=(6, 6))
        self.figN.patch.set_facecolor("#000000")
        self.axN.set_facecolor("#000000")
        self.axN.axis("off")

        self.pos = {n: (self.router.G.nodes[n]["x"], self.router.G.nodes[n]["y"]) for n in self.nodes}
        self.canvasN = FigureCanvasTkAgg(self.figN, self.frame_graph)
        self.canvasN.get_tk_widget().pack(fill="both", expand=True)

        tk.Label(self.frame_metrics, text="LIVE METRICS + AI CONSOLE", font=("Helvetica", 12, "bold"), bg="#1e1e1e", fg="white").pack(pady=6)

        self.figF, self.axF = plt.subplots(figsize=(5, 2.2))
        self.figF.patch.set_facecolor("#1e1e1e")
        self.axF.set_facecolor("#121212")
        self.axF.tick_params(colors="white", labelsize=8)
        self.axF.set_title("Prediction + Real vs Sim", color="white", fontsize=10)
        self.pred_hist_line, = self.axF.plot([], [], color="#00ffff", lw=1.8, label="Blended")
        self.pred_horizon_line, = self.axF.plot([], [], color="#ff9f1c", lw=2, label="Horizon")
        self.real_line, = self.axF.plot([], [], color="#3ddc97", lw=1.6, label="Real scaled")
        self.sim_line, = self.axF.plot([], [], "--", color="#9aa0a6", lw=1.2, label="Simulated")
        self.axF.legend(loc="upper left", fontsize=7)

        self.canvasF = FigureCanvasTkAgg(self.figF, self.frame_metrics)
        self.canvasF.get_tk_widget().pack(fill="x", padx=10)

        topbar = tk.Frame(self.frame_metrics, bg="#1e1e1e")
        topbar.pack(fill="x", padx=10)
        self.clock = tk.Label(topbar, text="00:00:00", font=("Consolas", 20), bg="#1e1e1e", fg="white")
        self.clock.pack(side="left")
        tk.Label(topbar, textvariable=self.data_source_text, font=("Consolas", 9), bg="#1e1e1e", fg="#72efdd").pack(side="left", padx=10)

        self.console = tk.Text(self.frame_metrics, bg="#101010", fg="#4cff4c", font=("Consolas", 9), height=11, relief="flat")
        self.console.pack(fill="x", padx=10, pady=6)

    def log_console(self, live_message=""):
        self.console.delete("1.0", "20.0")
        for row in list(self.ai.logs)[:16]:
            self.console.insert("end", row + "\n")
        if self.live.last_error:
            self.console.insert("end", f"[WARN] API fallback: {self.live.last_error}\n")
        self.console.insert("end", f"[LIVE] {live_message}\n")

    def trigger_blockage(self, edge_key):
        self.router.block_edge(edge_key[0], edge_key[1], BLOCK_DURATION)
        self.edge_buttons[edge_key].config(bg="#ff0000", fg="white", text=f"⛔ {edge_key[0]}-{edge_key[1]}")
        msg = f"Manual blockage on {edge_key[0]}-{edge_key[1]}"
        self.ai.log("MANUAL", msg)
        self.voice.speak(msg)

    def _origin_dest_xy(self):
        origin = self.start_node.get()
        destination = self.end_node.get()
        return (self.pos[origin][0], self.pos[origin][1]), (self.pos[destination][0], self.pos[destination][1])

    def draw_network(self):
        self.axN.clear()
        self.axN.axis("off")

        blocked = self.router.blocked_edges.keys()
        edges_normal = [edge for edge in self.router.G.edges() if self.router.normalize_edge(*edge) not in blocked]
        nx.draw_networkx_edges(self.router.G, self.pos, edgelist=edges_normal, ax=self.axN, alpha=0.12, edge_color="#666", width=1)

        blocked_edges = [edge for edge in self.router.G.edges() if self.router.normalize_edge(*edge) in blocked]
        if blocked_edges:
            nx.draw_networkx_edges(self.router.G, self.pos, edgelist=blocked_edges, ax=self.axN, alpha=0.8, edge_color="#ff0000", width=3, style="dotted")

        vals = np.array(list(self.vols.values()))
        norm = np.clip(vals / MAX_VOL, 0, 1)
        colors = [(n, 1 - n, 0.2) for n in norm]
        nx.draw_networkx_nodes(self.router.G, self.pos, ax=self.axN, node_size=90, node_color=colors, edgecolors="white", linewidths=0.3)

        path_edges, route_cost = self.router.route(self.start_node.get(), self.end_node.get())
        if path_edges:
            for u, v in path_edges:
                self.axN.add_patch(FancyArrowPatch(self.pos[u], self.pos[v], color="#00ffcc", linewidth=2.8, alpha=0.8, arrowstyle="-"))

            eta_local = (route_cost / 60.0) if route_cost else 0
            eta_google = self.live.google_eta_s / 60.0 if self.live.google_eta_s else None
            overlay = f" | Google ETA: {eta_google:.1f}m" if eta_google else ""
            self.route_text.set(f"Route edges: {len(path_edges)} | Dijkstra ETA: {eta_local:.1f}m{overlay}")
            self.travel_overlay_text.set(f"ETA Overlay: Dijkstra {eta_local:.1f}m" + (f" vs Google {eta_google:.1f}m" if eta_google else ""))
            self.last_eta_local = eta_local
            self.last_eta_google = eta_google
            if eta_google is not None:
                gap = eta_google - eta_local
                self.eta_gap_text.set(f"ETA Gap: {gap:+.1f}m")
            else:
                self.eta_gap_text.set("ETA Gap: N/A")
            self.lbl_status.config(text="STATUS: ROUTE ACTIVE", fg="#00ffcc")
        else:
            self.route_text.set("⛔ NO ROUTE AVAILABLE")
            self.lbl_status.config(text="STATUS: ALERT", fg="#ff0000")

    def tick(self):
        origin_xy, dest_xy = self._origin_dest_xy()
        if self.live.should_poll():
            self._launch_live_poll(origin_xy, dest_xy)
        self._consume_live_poll_result()

        for lat, lon in self.live.incident_points:
            edge = self.router.block_incident_near(lat, lon, duration=45)
            if edge:
                self.ai.log("INCIDENT", f"HERE incident blocked edge {edge[0]}-{edge[1]}")

        if self.live.social_incidents:
            self.ai.log("SOCIAL", f"X incident signals: {len(self.live.social_incidents)} posts")

        self.vols, _ = self.sim.step(self.live.speed_factor if self.live.live_mode else 1.0)
        active_blocks = self.router.check_blocks()
        self.router.update(self.vols)

        for node, volume in self.vols.items():
            self.nn.update(node, volume)

        analysis = self.ai.analyze(self.vols, self.start_node.get(), self.end_node.get())
        action = self.ai.maybe_act(analysis)
        self.last_action_msg = action

        self.ai_status.set(self.ai.status)
        color_map = {"ONLINE": "#00ff90", "ANALYZING": "#00bcd4", "ALERT": "#ff5252", "OPTIMIZING": "#ffc107"}
        self.lbl_ai_state.config(fg=color_map.get(self.ai.status, "white"))

        now = time.time()
        for key, btn in self.edge_buttons.items():
            if key in active_blocks:
                remaining = int(active_blocks[key] - now)
                btn.config(bg="#aa0000", text=f"⛔ {key[0]}-{key[1]} ({remaining}s)")
            else:
                btn.config(bg="#333333", fg="white", text=f"{key[0]} ↔ {key[1]}")

        target = self.end_node.get()
        hist_y = list(self.sim.hist[target])
        pred = self.nn.predict(target)
        for collection in self.axF.collections[:]:
            collection.remove()

        if pred[0] is not None:
            _, std_dev, horizon, conf = pred
            x_hist = range(len(hist_y))
            x_pred = range(len(hist_y), len(hist_y) + len(horizon))
            self.pred_hist_line.set_data(x_hist, hist_y)
            self.pred_horizon_line.set_data(x_pred, horizon)
            self.real_line.set_data(x_hist, list(self.sim.hist_real[target]))
            self.sim_line.set_data(x_hist, list(self.sim.hist_sim[target]))
            self.axF.fill_between(x_pred, np.array(horizon) - 2 * std_dev, np.array(horizon) + 2 * std_dev, color="#00ffff", alpha=0.2)
            self.last_conf = conf
            self.confidence_text.set(f"Confidence: {conf*100:.1f}%")
            if np.mean(horizon[:4]) > 680:
                warning = f"Predictive congestion warning at {target}."
                self.ai.log("PREDICT", warning)
                self.voice.speak(warning)
        else:
            self.confidence_text.set("Confidence: warming up model")

        self.axF.set_xlim(max(0, len(hist_y) - 60), len(hist_y) + PRED_HORIZON)
        self.axF.set_ylim(0, 1000)

        self.last_trend = analysis["trend"]
        self.trend_text.set(f"Trend: {analysis['trend']}")
        self.eff_text.set(f"Route Efficiency: {analysis['efficiency_delta']*100:+.1f}%")
        self.health_text.set("Sensors: degraded" if analysis["health_issues"] else "Sensors: healthy")
        self.data_source_text.set(self.live.live_badge())
        self.provider_status_text.set(self.live.provider_badge())

        if analysis["anomalies"]:
            self.voice.speak("Incident detected. Autonomous control evaluating response.")

        self.log_console(f"Priority: {', '.join(analysis['priority_nodes'])} | {action}")

        self.clock.config(text=datetime.now().strftime("%H:%M:%S"))
        self.draw_network()
        self.canvasN.draw_idle()
        self.canvasF.draw_idle()
        self.root.after(UPDATE_MS, self.tick)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Dashboard().run()
