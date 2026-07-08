# GE Demo — IIoT Dashboard: Complete Rebuild Master Plan

Version 2.0 — Unified Docker Edition | Minimalist Matte Design

# **1\. Purpose of This Document**

This document is the complete specification for rebuilding the GE Demo IIoT dashboard from scratch. The original repository was poorly structured: machine bridge scripts, a React frontend, a camera proxy, and a safety monitor were all separate processes that had to be started manually in the correct order. IPs were hardcoded across multiple files with no central configuration. The UI used gradients, glows, and unnecessary visual noise.

This rebuild addresses all of those problems. The result will be a single Docker container that starts everything at once, a clean centralized config file, and a minimalist UI that shows only what the operator needs.

# **2\. What the App Actually Does**

The application is an IIoT monitoring dashboard for the Makino Lab (Room 1067, Area M, Grid 14, Basement Level) at Miami University. It aggregates live telemetry from two physical machines and simulates three additional machines, overlays two camera feeds with YOLO-based object detection, and provides a safety monitoring system that can automatically slow or stop the UR5e cobot when a human enters its workspace.

The five machines tracked by the dashboard are listed below. Only the Haas TL-1 and UR5e have real hardware connections. The three Makino machines are simulated with realistic drifting data.

| Machine | Type | Real Connection? | Protocol |
| :---- | :---- | :---- | :---- |
| Haas TL-1 | CNC Lathe (2-axis) | YES — Live | Q-Command TCP |
| UR5e Cobot | Collaborative Robot Arm | YES — Live | RTDE (binary) |
| Makino a51nx | Horizontal Machining Center | No — Simulated | — |
| Makino d200Z | 5-Axis VMC | No — Simulated | — |
| Makino PS95 | VMC | No — Simulated | — |

# **3\. UI Design System**

The new design is strictly minimalist. The guiding principle is: if a UI element does not directly communicate machine state to the operator, it does not exist. Every design decision below is a hard rule, not a suggestion.

## **3.1 Color Palette**

The palette is two-tone: matte black for all backgrounds and surfaces, and a matte reddish-orange for all active states, alerts, and interactive accents. No other colors are permitted. There are no gradients, no glows, no shadows, and no bluish, greenish, or purplish tints of any kind.

| Token | Hex Value | Usage |
| :---- | :---- | :---- |
| \--bg-base | \#0D0D0D | Main page background |
| \--bg-surface | \#141414 | Cards, panels, sidebars |
| \--bg-elevated | \#1C1C1C | Hover states, active rows |
| \--border | \#2A2A2A | All dividers and borders |
| \--text-primary | \#E8E8E8 | All primary text |
| \--text-muted | \#666666 | Labels, secondary text |
| \--accent | \#C0441A | Alerts, live indicators, interactive accents (matte red-orange) |

## **3.2 Typography**

Use two fonts only. Inter (or system-ui) for all labels and body text. JetBrains Mono (or any monospace) for all numeric readouts, machine values, and code. Font sizes should follow a strict scale: 10px for micro-labels, 12px for body, 14px for section headers, 20px for KPI values. No decorative fonts. No font weights heavier than 600 (semibold).

## **3.3 Layout Rules**

The layout is a fixed top header bar, a fixed left sidebar for navigation, and a main content area. The Makino Lab view is the primary screen. It shows a 2D schematic floor map on the left half and a scrollable list of machine data panels on the right half. Each machine panel shows only: status indicator, machine name, the three or four most critical metrics (RPM, load, feed rate, power), and an alarm field. No hero images. No decorative banners. No carousels.

## **3.4 Status Indicators**

Machine status is communicated by a single small solid square (4×4px) next to the machine name. Running \= white. Idle \= \#444444 (dark grey). Alarm \= \#C0441A (accent red-orange). Offline \= \#2A2A2A (border color). No pulsing animations. No color-coded backgrounds. The status square is the only status indicator.

# **4\. Unified Architecture**

The rebuild collapses all previously separate processes into a single application with a well-defined internal structure. A single Docker container runs everything. There is one port exposed to the outside world.

## **4.1 Architecture Overview**

The backend is a Python FastAPI application. It serves the compiled React frontend as static files, exposes a single WebSocket endpoint (/ws/telemetry) that the browser connects to, and runs the Haas and UR5e bridge polling loops as asyncio background tasks. The camera streams are proxied through the same server using an embedded mediamtx process managed by the Python supervisor.

Data flow:

**Haas TL-1 (192.168.1.50:5051)** → \[Q-Command TCP poll, 1s interval\] → FastAPI background task → WebSocket broadcast → React frontend

**UR5e (192.168.1.15:30004)** → \[RTDE binary stream, 10Hz\] → FastAPI background task → WebSocket broadcast → React frontend

**Amcrest Camera (192.168.1.108)** → \[RTSP\] → mediamtx subprocess → HLS → React frontend (hls.js)

**RealSense L515** → \[pyrealsense2 \+ YOLOv8\] → MJPEG stream → React frontend (img tag)

## **4.2 Directory Structure (Rebuild Target)**

iiot-dashboard/  
├── Dockerfile  
├── docker-compose.yml  
├── .env                         ← All machine IPs and ports live here  
├── backend/  
│   ├── main.py                  ← FastAPI app, WebSocket server, startup tasks  
│   ├── bridges/  
│   │   ├── haas\_bridge.py       ← Haas Q-Command polling loop (async task)  
│   │   └── ur5e\_bridge.py       ← UR5e RTDE polling loop (async task)  
│   ├── cameras/  
│   │   ├── realsense\_stream.py  ← RealSense MJPEG stream (subprocess or thread)  
│   │   └── safety\_monitor.py    ← YOLO \+ RealSense safety supervisor  
│   ├── simulation/  
│   │   └── sim\_tick.py          ← Fallback simulation for all 5 machines  
│   └── config.py                ← Reads .env, exposes typed settings  
├── frontend/  
│   ├── src/  
│   │   ├── App.tsx  
│   │   ├── pages/  
│   │   │   ├── MakinoLab.tsx    ← Primary dashboard view  
│   │   │   └── Login.tsx  
│   │   ├── stores/  
│   │   │   ├── equipmentStore.ts ← Single WS connection to /ws/telemetry  
│   │   │   └── cameraStore.ts  
│   │   └── components/  
│   │       ├── MachinePanel.tsx  
│   │       ├── FloorMap.tsx  
│   │       └── CameraTile.tsx  
│   ├── package.json  
│   └── vite.config.ts  
├── mediamtx.yml                 ← Camera proxy config  
└── requirements.txt

## **4.3 The .env Configuration File**

All machine IPs, ports, and API keys are centralized in a single .env file. The backend reads this file at startup via a config.py module. The frontend never needs to know machine IPs directly — it only connects to the backend's WebSocket.
```
\# .env — All environment configuration in one place

\# Machine IPs  
HAAS\_IP=192.168.1.50  
HAAS\_PORT=5051  
UR5E\_IP=192.168.1.15  
UR5E\_RTDE\_PORT=30004  
UR5E\_DASHBOARD\_PORT=29999  
UR5E\_SCRIPT\_PORT=30001

\# Camera IPs  
AMCREST\_IP=192.168.1.108  
AMCREST\_RTSP\_USER=admin  
AMCREST\_RTSP\_PASS=your\_password\_here

\# Server config  
BACKEND\_PORT=8000  
UR5E\_HTTP\_API\_KEY=makino-lab

\# Bridge polling intervals (seconds)  
HAAS\_POLL\_INTERVAL=1.0  
UR5E\_POLL\_INTERVAL=0.1  
RECONNECT\_WAIT=5.0
```
# **5\. Backend Implementation**

## **5.1 main.py — FastAPI Application**

The FastAPI application is the single entry point. On startup it launches the Haas bridge, UR5e bridge, and simulation tick as asyncio tasks. It exposes one WebSocket endpoint that all browser clients connect to. It also exposes a REST endpoint for UR5e control commands (play/stop/home). The compiled React frontend is served as static files from the /frontend/dist directory.
```

\# backend/main.py  
import asyncio  
import json  
from fastapi import FastAPI, WebSocket, WebSocketDisconnect  
from fastapi.staticfiles import StaticFiles  
from contextlib import asynccontextmanager  
from .bridges.haas\_bridge import haas\_poll\_loop  
from .bridges.ur5e\_bridge import ur5e\_poll\_loop  
from .simulation.sim\_tick import sim\_tick\_loop  
from .state import state\_manager  \# shared in-memory state

@asynccontextmanager  
async def lifespan(app: FastAPI):  
    \# Start all background tasks on server startup  
    tasks \= \[  
        asyncio.create\_task(haas\_poll\_loop(state\_manager)),  
        asyncio.create\_task(ur5e\_poll\_loop(state\_manager)),  
        asyncio.create\_task(sim\_tick\_loop(state\_manager)),  
    \]  
    yield  
    \# Cancel all tasks on shutdown  
    for t in tasks:  
        t.cancel()

app \= FastAPI(lifespan=lifespan)

\# ── WebSocket endpoint ──────────────────────────────────────────  
connected\_clients: set\[WebSocket\] \= set()

@app.websocket("/ws/telemetry")  
async def telemetry\_ws(ws: WebSocket):  
    await ws.accept()  
    connected\_clients.add(ws)  
    \# Send current state immediately on connect  
    await ws.send\_text(json.dumps(state\_manager.get\_snapshot()))  
    try:  
        async for msg in ws.iter\_text():  
            \# Handle control commands (play/stop/home for UR5e)  
            await handle\_command(json.loads(msg))  
    except WebSocketDisconnect:  
        pass  
    finally:  
        connected\_clients.discard(ws)

async def handle\_command(cmd: dict):  
    \# Forward robot commands to UR5e bridge  
    from .bridges.ur5e\_bridge import send\_dashboard\_cmd  
    action \= cmd.get("action")  
    if action in ("play", "stop", "pause", "home"):  
        await send\_dashboard\_cmd(action)

\# ── State change callback ───────────────────────────────────────  
async def broadcast\_state\_update(payload: dict):  
    msg \= json.dumps(payload)  
    dead \= set()  
    for ws in connected\_clients:  
        try:  
            await ws.send\_text(msg)  
        except Exception:  
            dead.add(ws)  
    connected\_clients \-= dead

state\_manager.on\_update \= broadcast\_state\_update

\# ── Serve React frontend ────────────────────────────────────────  
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")

## **5.2 config.py — Typed Settings from .env**

\# backend/config.py  
from pydantic\_settings import BaseSettings

class Settings(BaseSettings):  
    haas\_ip: str \= "192.168.1.50"  
    haas\_port: int \= 5051  
    ur5e\_ip: str \= "192.168.1.15"  
    ur5e\_rtde\_port: int \= 30004  
    ur5e\_dashboard\_port: int \= 29999  
    ur5e\_script\_port: int \= 30001  
    amcrest\_ip: str \= "192.168.1.108"  
    amcrest\_rtsp\_user: str \= "admin"  
    amcrest\_rtsp\_pass: str \= ""  
    backend\_port: int \= 8000  
    ur5e\_http\_api\_key: str \= "makino-lab"  
    haas\_poll\_interval: float \= 1.0  
    ur5e\_poll\_interval: float \= 0.1  
    reconnect\_wait: float \= 5.0

    class Config:  
        env\_file \= ".env"

settings \= Settings()
```
## **5.3 Haas Bridge (Integrated Async Task)**

The Haas bridge is no longer a standalone script. It is an async coroutine that runs inside the FastAPI event loop. It connects to the Haas TL-1 via TCP, polls Q-Commands every second, and calls state\_manager.update\_haas(payload) which triggers a broadcast to all WebSocket clients.
```
\# backend/bridges/haas\_bridge.py  
import asyncio  
import socket  
import json  
from ..config import settings

QUERIES \= \[  
    ("program",      "?Q500"),  \# Active program name  
    ("status",       "?Q600"),  \# Machine status  
    ("part\_count",   "?Q402"),  \# Parts count  
    ("tool\_number",  "?Q403"),  \# Current tool  
    ("spindle\_rpm",  "?Q408"),  \# Commanded spindle speed  
    ("spindle\_load", "?Q410"),  \# Spindle load %  
    ("feed\_rate",    "?Q411"),  \# Feed rate  
    ("x\_pos",        "?Q504"),  \# X work coordinate  
    ("z\_pos",        "?Q506"),  \# Z work coordinate  
    ("cycle\_time",   "?Q404"),  \# Cycle time  
    ("alarm",        "?Q300"),  \# Active alarm code  
    ("coolant",      "?Q409"),  \# Coolant status  
\]

def query\_haas(sock, cmd: str) \-\> str:  
    sock.sendall((cmd \+ "\\r\\n").encode("ascii"))  
    data \= b""  
    sock.settimeout(2.0)  
    while True:  
        chunk \= sock.recv(256)  
        if not chunk or b"\\n" in chunk:  
            data \+= chunk  
            break  
        data \+= chunk  
    return data.decode("ascii", errors="replace").strip()

def parse\_response(raw: str) \-\> str:  
    lines \= \[l.strip() for l in raw.replace("\\r", "\\n").split("\\n") if l.strip()\]  
    for line in lines:  
        if not line.startswith("\>") and not line.startswith("?"):  
            return line  
    return raw.strip()

def build\_payload(raw: dict) \-\> dict:  
    def safe\_float(k, d=0.0):  
        try: return float(raw.get(k, d))  
        except: return d  
    def safe\_int(k, d=0):  
        try: return int(float(raw.get(k, d)))  
        except: return d

    status\_raw \= raw.get("status", "").upper()  
    if "ALARM" in status\_raw: status \= "alarm"  
    elif "FEED HOLD" in status\_raw: status \= "paused"  
    elif "RUNNING" in status\_raw or "CYCLE" in status\_raw: status \= "running"  
    else: status \= "idle"

    alarm\_code \= safe\_int("alarm")  
    spindle\_load \= safe\_float("spindle\_load")

    return {  
        "machine": "haas-tl1",  
        "status": status,  
        "program": raw.get("program", "—"),  
        "spindleRpm": safe\_float("spindle\_rpm"),  
        "spindleLoad": spindle\_load,  
        "feedRate": safe\_float("feed\_rate"),  
        "position": {"x": safe\_float("x\_pos"), "z": safe\_float("z\_pos")},  
        "toolNumber": safe\_int("tool\_number"),  
        "cycleTime": safe\_float("cycle\_time"),  
        "partCount": safe\_int("part\_count"),  
        "powerKw": round(spindle\_load / 100.0 \* 7.5, 2),  
        "coolant": "ON" in raw.get("coolant", "").upper(),  
        "alarms": \[f"ALARM {alarm\_code}"\] if alarm\_code \!= 0 else \[\],  
    }

async def haas\_poll\_loop(state\_manager):  
    while True:  
        sock \= None  
        try:  
            sock \= socket.socket(socket.AF\_INET, socket.SOCK\_STREAM)  
            sock.settimeout(5.0)  
            sock.connect((settings.haas\_ip, settings.haas\_port))  
            state\_manager.set\_haas\_bridge\_status("live")  
            while True:  
                raw \= {}  
                for name, cmd in QUERIES:  
                    resp \= query\_haas(sock, cmd)  
                    raw\[name\] \= parse\_response(resp)  
                payload \= build\_payload(raw)  
                await state\_manager.update\_haas(payload)  
                await asyncio.sleep(settings.haas\_poll\_interval)  
        except Exception as e:  
            state\_manager.set\_haas\_bridge\_status("offline")  
            await state\_manager.update\_haas({"machine": "haas-tl1", "status": "offline"})  
        finally:  
            if sock:  
                try: sock.close()  
                except: pass  
        await asyncio.sleep(settings.reconnect\_wait)
```
## **5.4 UR5e Bridge (Integrated Async Task)**

The UR5e bridge connects via RTDE (port 30004\) for telemetry and the Dashboard Server (port 29999\) for control commands. It negotiates RTDE protocol version 2, subscribes to joint positions, TCP pose, safety mode, and robot mode, then streams binary data at \~10Hz. The key RTDE variables to subscribe to are listed below.
```
\# RTDE Variables to subscribe to (in ur5e\_bridge.py)  
RTDE\_VARIABLES \= \[  
    "actual\_q",                      \# Joint angles (VECTOR6D, 6 doubles, radians)  
    "actual\_qd",                     \# Joint velocities (VECTOR6D, rad/s)  
    "actual\_current",                \# Joint currents (VECTOR6D, Amps)  
    "actual\_TCP\_pose",               \# TCP position \+ orientation (VECTOR6D, m \+ rad)  
    "actual\_TCP\_speed",              \# TCP speed vector (VECTOR6D, m/s)  
    "target\_speed\_fraction",         \# Speed slider 0.0–1.0 (DOUBLE)  
    "robot\_mode",                    \# Robot mode code (INT32)  
    "safety\_mode",                   \# Safety mode code (INT32)  
    "actual\_robot\_voltage",          \# Bus voltage (DOUBLE, Volts)  
    "actual\_robot\_current",          \# Bus current (DOUBLE, Amps)  
    "runtime\_state",                 \# Program runtime state (INT32)  
    "output\_bit\_registers0\_to\_31",   \# Digital outputs (UINT32)  
\]

\# RTDE Wire Protocol (manual implementation — no library needed):  
\# 1\. Connect TCP to UR5E\_IP:30004  
\# 2\. Send: struct.pack("\>HBH", 5, 0x56, 2\)  → Request protocol version 2  
\# 3\. Recv: 4 bytes header \+ 1 byte accepted flag  
\# 4\. Send: struct.pack("\>HB", 3+len(recipe), 0x4F) \+ recipe.encode()  → Setup outputs  
\# 5\. Recv: recipe\_id byte \+ comma-separated type string  
\# 6\. Send: struct.pack("\>HB", 3, 0x53)  → Start streaming  
\# 7\. Loop: recv frames, unpack binary according to type list

\# Robot Mode Codes:  
\# \-1=NO\_CONTROLLER, 0=DISCONNECTED, 3=POWER\_OFF, 4=POWER\_ON,  
\#  5=IDLE, 7=RUNNING

\# Safety Mode Codes:  
\# 1=NORMAL, 2=REDUCED, 3=PROTECTIVE\_STOP, 5=SAFEGUARD\_STOP,  
\# 6=SYSTEM\_EMERGENCY\_STOP, 7=ROBOT\_EMERGENCY\_STOP, 8=VIOLATION, 9=FAULT

\# Dashboard Server Commands (port 29999):  
\# Connect TCP, discard welcome banner, send "play\\n" / "stop\\n" / "pause\\n"  
\# Response: "Starting program\\n" or "Stopped\\n" etc.

\# URScript Upload (port 30001):  
\# Connect TCP, send script as UTF-8 string \+ newline, controller executes immediately  
\# Home position script:  
HOME\_SCRIPT \= """  
def home():  
  movej(\[0, \-1.5708, 0, \-1.5708, 0, 0\], a=0.5, v=0.3)  
end  
home()  
"""
```
# **6\. Frontend Implementation**

## **6.1 Single WebSocket Connection**

In the rebuild, the frontend connects to exactly one WebSocket endpoint: ws://{host}/ws/telemetry. The backend multiplexes all machine data (Haas, UR5e, and all three simulated Makinos) into a single stream. The frontend no longer needs to know machine IPs or manage multiple WebSocket connections.
```
// frontend/src/stores/equipmentStore.ts  
// Single WebSocket connection to the unified backend

const WS\_URL \= \`ws://${window.location.host}/ws/telemetry\`;

class EquipmentStore {  
  private ws: WebSocket | null \= null;

  // Machine state  
  haas: HaasData \= HAAS\_DEFAULTS;  
  ur5e: UR5eData \= UR5E\_DEFAULTS;  
  makinoA51nx: MakinoData \= MAKINO\_A51NX\_DEFAULTS;  
  makinoD200Z: MakinoData \= MAKINO\_D200Z\_DEFAULTS;  
  makinoPS95: MakinoData \= MAKINO\_PS95\_DEFAULTS;

  // Bridge status (set by backend in the payload)  
  haasBridgeStatus: 'live' | 'sim' | 'offline' \= 'sim';  
  ur5eBridgeStatus: 'live' | 'sim' | 'offline' \= 'sim';

  private listeners \= new Set\<() \=\> void\>();

  connect() {  
    this.ws \= new WebSocket(WS\_URL);  
    this.ws.onmessage \= (evt) \=\> {  
      const snapshot \= JSON.parse(evt.data);  
      this.applySnapshot(snapshot);  
      this.notify();  
    };  
    this.ws.onclose \= () \=\> {  
      // Reconnect after 5 seconds  
      setTimeout(() \=\> this.connect(), 5000);  
    };  
  }

  sendCommand(cmd: object) {  
    if (this.ws?.readyState \=== WebSocket.OPEN) {  
      this.ws.send(JSON.stringify(cmd));  
    }  
  }

  private applySnapshot(snapshot: any) {  
    if (snapshot.haas)        this.haas \= snapshot.haas;  
    if (snapshot.ur5e)        this.ur5e \= snapshot.ur5e;  
    if (snapshot.makinoA51nx) this.makinoA51nx \= snapshot.makinoA51nx;  
    if (snapshot.makinoD200Z) this.makinoD200Z \= snapshot.makinoD200Z;  
    if (snapshot.makinoPS95)  this.makinoPS95 \= snapshot.makinoPS95;  
    if (snapshot.bridgeStatus) {  
      this.haasBridgeStatus \= snapshot.bridgeStatus.haas;  
      this.ur5eBridgeStatus \= snapshot.bridgeStatus.ur5e;  
    }  
  }

  subscribe(fn: () \=\> void) {  
    this.listeners.add(fn);  
    if (this.listeners.size \=== 1\) this.connect();  
    return () \=\> this.listeners.delete(fn);  
  }

  private notify() { this.listeners.forEach(fn \=\> fn()); }  
}

export const equipmentStore \= new EquipmentStore();
```
## **6.2 Machine Data Types (TypeScript)**

The TypeScript interfaces below define the exact shape of data the frontend expects from the backend. These must match the Python build\_payload() output exactly.
```
// frontend/src/types/equipment.ts

export type MachineStatus \= 'running' | 'idle' | 'alarm' | 'offline';

export interface HaasData {  
  machine: 'haas-tl1';  
  status: MachineStatus;  
  program: string;  
  spindleRpm: number;       // RPM (0–6000)  
  spindleLoad: number;      // % (0–100)  
  feedRate: number;         // mm/rev  
  position: { x: number; z: number }; // mm, 2-axis lathe  
  toolNumber: number;       // turret position (1–12)  
  cycleTime: number;        // seconds  
  partCount: number;  
  powerKw: number;  
  coolant: boolean;  
  alarms: string\[\];  
}

export interface CobotJoint {  
  id: string;               // "J1" through "J6"  
  label: string;            // "Base", "Shoulder", etc.  
  angle: number;            // degrees  
  speed: number;            // deg/s  
  torque: number;           // Nm (estimated from current × 3.0)  
}

export interface UR5eData {  
  machine: 'ur5e';  
  status: MachineStatus;  
  program: string;  
  robotMode: string;        // "RUNNING", "IDLE", etc.  
  safetyMode: string;       // "NORMAL", "PROTECTIVE\_STOP", etc.  
  tcpPosition: {  
    x: number; y: number; z: number;   // mm  
    rx: number; ry: number; rz: number; // degrees  
  };  
  tcpSpeed: number;         // mm/s  
  speedFraction: number;    // % (0–100)  
  joints: CobotJoint\[\];     // 6 joints  
  powerKw: number;  
  voltage: number;          // V  
  current: number;          // A  
  alarms: string\[\];  
  digitalOutputs: number;   // bitmask  
}

export interface MakinoData {  
  machine: 'makino-a51nx' | 'makino-d200z' | 'makino-ps95';  
  status: MachineStatus;  
  program: string;  
  spindleRpm: number;  
  spindleLoad: number;  
  feedRate: number;  
  position: { x: number; y: number; z: number };  
  toolNumber: number;  
  cycleTime: number;  
  partCount: number;  
  powerKw: number;  
  alarms: string\[\];  
}
```
## **6.3 Machine Panel Component**

Each machine has a single panel component. The panel is a flat rectangle on the matte black background. It contains: a status square \+ machine name on the top row, a 2-column grid of data rows (label left, value right), and an alarm row at the bottom that is hidden when alarms is empty. No images. No charts unless explicitly needed.
```
// frontend/src/components/MachinePanel.tsx (structure only)  
// Styling: all colors from CSS variables defined in the design system

function MachinePanel({ data }: { data: HaasData | UR5eData | MakinoData }) {  
  return (  
    \<div className="machine-panel"\>  
      {/\* Header row \*/}  
      \<div className="panel-header"\>  
        \<span className={\`status-square status-${data.status}\`} /\>  
        \<span className="machine-name"\>{data.machine}\</span\>  
        \<span className="bridge-badge"\>{bridgeStatus}\</span\>  
      \</div\>

      {/\* Data rows — only the critical fields \*/}  
      \<DataRow label="PROGRAM"  value={data.program} /\>  
      \<DataRow label="RPM"      value={data.spindleRpm}  unit="rpm" /\>  
      \<DataRow label="LOAD"     value={data.spindleLoad} unit="%" /\>  
      \<DataRow label="FEED"     value={data.feedRate}    unit="mm/min" /\>  
      \<DataRow label="POWER"    value={data.powerKw}     unit="kW" /\>

      {/\* Alarm row — only shown when alarms exist \*/}  
      {data.alarms.length \> 0 && (  
        \<div className="alarm-row"\>  
          {data.alarms.join(' | ')}  
        \</div\>  
      )}  
    \</div\>  
  );  
}
```
# **7\. Docker Container**

## **7.1 Dockerfile**

The Dockerfile uses a multi-stage build. The first stage builds the React frontend. The second stage is the production Python image that copies the compiled frontend and runs the FastAPI server.
```
\# Dockerfile

\# ── Stage 1: Build the React frontend ──────────────────────────  
FROM node:22-slim AS frontend-builder  
WORKDIR /app/frontend  
COPY frontend/package.json frontend/pnpm-lock.yaml ./  
RUN npm install \-g pnpm && pnpm install \--frozen-lockfile  
COPY frontend/ ./  
RUN pnpm build  
\# Output: /app/frontend/dist

\# ── Stage 2: Production Python server ──────────────────────────  
FROM python:3.11-slim AS production

WORKDIR /app

\# Install system dependencies for pyrealsense2 and OpenCV  
RUN apt-get update && apt-get install \-y \--no-install-recommends \\  
    libusb-1.0-0 \\  
    libgl1-mesa-glx \\  
    libglib2.0-0 \\  
    && rm \-rf /var/lib/apt/lists/\*

\# Install Python dependencies  
COPY requirements.txt .  
RUN pip install \--no-cache-dir \-r requirements.txt

\# Copy backend source  
COPY backend/ ./backend/

\# Copy compiled frontend from Stage 1  
COPY \--from=frontend-builder /app/frontend/dist ./frontend/dist

\# Copy mediamtx binary and config (download separately, see note below)  
COPY mediamtx ./mediamtx  
COPY mediamtx.yml ./mediamtx.yml  
RUN chmod \+x ./mediamtx

\# Copy .env (or pass via docker run \--env-file)  
\# COPY .env .env

EXPOSE 8000

CMD \["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"\]

## **7.2 docker-compose.yml**

Use Docker Compose to manage the container, pass the .env file, and configure host networking so the container can reach the machines on the local 192.168.1.x subnet.

\# docker-compose.yml

services:  
  iiot-dashboard:  
    build: .  
    image: iiot-dashboard:latest  
    container\_name: iiot-dashboard

    \# Use host networking so the container can reach 192.168.1.x machines directly  
    \# (Linux only; on Windows/Mac use bridge network \+ host.docker.internal)  
    network\_mode: host

    \# Load all config from .env  
    env\_file: .env

    \# Restart automatically if it crashes  
    restart: unless-stopped

    \# Mount .env separately if you don't want to bake it into the image  
    volumes:  
      \- ./.env:/app/.env:ro

    \# Optional: mount YOLO weights file  
    \# \- ./weights.pt:/app/backend/cameras/weights.pt:ro
```
## **7.3 requirements.txt**
```
\# requirements.txt

\# Web server  
fastapi\>=0.115.0  
uvicorn\[standard\]\>=0.30.0  
pydantic-settings\>=2.0.0  
websockets\>=13.0

\# Machine bridges  
\# (no extra deps — uses stdlib socket, struct, asyncio)

\# Camera streaming  
flask\>=3.0.0           \# For the MJPEG stream endpoint  
opencv-python-headless\>=4.10.0  
numpy\>=1.26.0  
ultralytics\>=8.0.0     \# YOLOv8

\# RealSense (only if hardware is present; comment out if not)  
\# pyrealsense2\>=2.55.0  \# Requires Intel RealSense SDK installed on host

\# UR5e control (only needed for safety\_monitor.py)  
\# ur-rtde\>=1.5.0        \# Requires UR robot drivers on host
```
## **7.4 Build and Run**

\# 1\. Clone your new repo  
git clone https://github.com/your-org/iiot-dashboard.git  
cd iiot-dashboard

\# 2\. Edit .env with your machine IPs  
nano .env

\# 3\. Download mediamtx binary (not included in repo — too large)  
\#    https://github.com/bluenviron/mediamtx/releases/latest  
\#    Place mediamtx (Linux binary) in the project root

\# 4\. Build and start  
docker compose up \--build

\# Dashboard available at:  
\#   http://localhost:8000

\# To run in background:  
docker compose up \-d \--build

\# To view logs:  
docker compose logs \-f

\# To stop:  
docker compose down

# **8\. Camera Streaming**

Camera streaming is handled inside the unified backend. The mediamtx binary is launched as a subprocess by the FastAPI app on startup. The RealSense MJPEG stream is served as a FastAPI route.

| Camera | Source | Frontend URL |
| :---- | :---- | :---- |
| CAM-01 | Intel RealSense L515 (USB) | /api/cam01/feed  (MJPEG) |
| CAM-02 | Amcrest IP (192.168.1.108, RTSP) | /cam02/index.m3u8  (HLS via mediamtx) |
| CAM-01 YOLO | RealSense \+ YOLOv8 annotated | /api/cam01/yolo\_feed  (MJPEG) |
| Isaac Sim | NVIDIA Isaac Sim viewport | /api/isaac/feed  (MJPEG, optional) |

The mediamtx config (mediamtx.yml) should define a single path 'cam02' pointing to the Amcrest RTSP URL. The RTSP URL format for the Amcrest camera is: rtsp://{user}:{password}@{AMCREST\_IP}/cam/realmonitor?channel=1\&subtype=0

# **9\. Port Reference**

In the unified architecture, only one port is exposed externally. All internal communication is within the container.

| Port | Service | Exposed? |
| :---- | :---- | :---- |
| 8000 | FastAPI (frontend \+ WebSocket \+ REST) | YES — public |
| 8000/ws/telemetry | WebSocket telemetry stream | YES (via 8000\) |
| 8888 | mediamtx HLS proxy (internal) | NO — internal only |
| 9997 | mediamtx API health check (internal) | NO — internal only |
| 5051 | Haas TL-1 Q-Command (outbound to machine) | N/A — outbound |
| 30004 | UR5e RTDE (outbound to robot) | N/A — outbound |
| 29999 | UR5e Dashboard Server (outbound to robot) | N/A — outbound |
| 30001 | UR5e Script port (outbound to robot) | N/A — outbound |

# **10\. Authentication**

The original app used purely client-side authentication with hardcoded credentials in the JavaScript bundle. This is insecure. In the rebuild, authentication should be moved to the backend. The simplest approach is HTTP Basic Auth or a simple token check in the FastAPI middleware. Credentials should be stored in the .env file, not in source code.
```
\# .env additions for auth  
DASHBOARD\_USERNAME=admin  
DASHBOARD\_PASSWORD=your\_secure\_password\_here

\# In backend/main.py, add a dependency:  
from fastapi import Depends, HTTPException, status  
from fastapi.security import HTTPBasic, HTTPBasicCredentials  
import secrets

security \= HTTPBasic()

def verify\_credentials(credentials: HTTPBasicCredentials \= Depends(security)):  
    correct\_user \= secrets.compare\_digest(credentials.username, settings.dashboard\_username)  
    correct\_pass \= secrets.compare\_digest(credentials.password, settings.dashboard\_password)  
    if not (correct\_user and correct\_pass):  
        raise HTTPException(status\_code=status.HTTP\_401\_UNAUTHORIZED,  
                            headers={"WWW-Authenticate": "Basic"})
```
# **11\. Important Notes and Gotchas**

Network mode: The Docker container must be able to reach the machines on 192.168.1.x. On Linux, 'network\_mode: host' in docker-compose.yml handles this. On Windows or macOS, Docker Desktop uses a VM and host networking does not work the same way. In that case, use bridge networking and ensure the host machine has a route to 192.168.1.x.

RealSense USB passthrough: The Intel RealSense L515 connects via USB. To use it inside Docker, you must pass the USB device through: add 'devices: \- /dev/bus/usb:/dev/bus/usb' to docker-compose.yml and run the container with '--privileged' or specific device permissions.

RTDE limitation: The UR5e RTDE interface only allows one client at a time. If UR Polyscope or UR Simulator is connected, the bridge will fail with 'Connection refused'. Disconnect all other RTDE clients before starting the container.

mediamtx binary: The mediamtx binary is not included in the repository (it is gitignored). Download the correct binary for your target platform from https://github.com/bluenviron/mediamtx/releases and place it in the project root before building the Docker image. For the Docker container (Linux), download the linux\_amd64 version.

YOLO weights: The custom-trained YOLO model weights file (weights.pt) is also gitignored. It must be obtained separately and mounted into the container via a Docker volume.

Simulated machines: The Makino a51nx, d200Z, and PS95 have no real connections. Their data is generated by the sim\_tick\_loop in the backend, which runs on a 1.5-second interval and produces realistic drifting values. These machines will always show as SIM regardless of network state.