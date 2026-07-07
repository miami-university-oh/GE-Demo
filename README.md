# IIoT Building Dashboard — How to Run

This app is a full-stack IIoT dashboard for an advanced manufacturing lab. It has three independent layers that work together:

1. **Web Dashboard** — React/Vite frontend + Express backend (runs on your PC)
2. **Machine Bridges** — Python scripts that connect to the Haas TL-1 and UR5e robot over the local network and push live data to the dashboard via WebSocket
3. **Camera Streaming** — mediamtx proxy and Python scripts that stream live camera feeds into the dashboard

You can run the dashboard alone in simulation mode (no hardware required). Connect the bridges and cameras when the physical machines are available.

---

## Prerequisites

### Node.js + pnpm (for the dashboard)

1. Download and install **Node.js LTS** from [https://nodejs.org](https://nodejs.org)
2. Open a terminal and install pnpm:
   ```
   npm install -g pnpm
   ```

### Python 3.9+ (for bridges and camera scripts)

1. Download from [https://python.org](https://python.org)
2. During install, check **"Add Python to PATH"**
3. Run the included installer to get all Python dependencies:
   ```
   install_requirements.bat
   ```
   > **Note:** `pyrealsense2` and `ur-rtde` require the RealSense SDK and UR robot drivers respectively. If you don't have that hardware, those install errors are safe to ignore.

---

## Part 1 — Start the Dashboard

Open a terminal in the project root (`GE Demo\`) and run:

```bash
pnpm install
pnpm dev
```

The dashboard will be available at:
```
http://localhost:3000
```

The dashboard runs fully in **simulation mode** by default — all equipment panels show animated fake data with a **SIM** badge. No hardware is required to use the UI.

---

## Part 2 — Machine Bridges (Live Data from Lab Equipment)

The bridges run on your PC and connect to the physical machines on the local network (`192.168.1.x`). Each bridge translates machine data into a WebSocket stream the dashboard reads automatically.

| Bridge | Machine | Your PC WebSocket | Machine IP |
|---|---|---|---|
| `haas_bridge.py` | Haas TL-1 lathe | `ws://YOUR-PC:8765` | `192.168.1.50:5051` |
| `ur5e_bridge.py` | UR5e cobot | `ws://YOUR-PC:8766` | `192.168.1.15:30004` |

### Quick Start (both bridges at once)

Navigate to the `machine-bridges` folder and double-click:
```
machine-bridges\start_all_bridges.bat
```

Two terminal windows open — one per machine. When they connect, the dashboard's equipment panels automatically switch from **SIM** to **LIVE**.

### Start bridges manually

```bash
cd machine-bridges

# Haas TL-1 (port 8765)
python haas_bridge.py

# UR5e cobot (port 8766) — open a second terminal
python ur5e_bridge.py
```

### Haas TL-1 one-time setup

On the Haas control panel:
1. Press **SETTING**
2. Search for setting **#143** (Remote Q-Command)
3. Set it to **1** (Enabled)

### UR5e — no setup needed

The UR5e RTDE interface is always active on port `30004`. Just make sure:
- The robot is **powered on** and **not in E-Stop**
- Your PC can ping `192.168.1.15`

### Firewall rules (run once as Administrator if bridges can't connect)

```
netsh advfirewall firewall add rule name="IIoT Haas Bridge" dir=in action=allow protocol=TCP localport=8765
netsh advfirewall firewall add rule name="IIoT UR5e Bridge" dir=in action=allow protocol=TCP localport=8766
```

### UR5e HTTP control API (optional)

`ur5e_bridge.py` also starts a REST API on port `5000` for Siri Shortcuts or any HTTP client:

| Endpoint | Action |
|---|---|
| `POST http://YOUR-PC:5000/play` | Start the robot |
| `POST http://YOUR-PC:5000/stop` | Stop the robot |
| `POST http://YOUR-PC:5000/pause` | Pause the robot |
| `POST http://YOUR-PC:5000/home` | Move robot to home position |

Include the header `X-API-Key: makino-lab` on every request.

---

## Part 3 — Camera Streaming

### CAM-02 — Amcrest IP Camera (via mediamtx HLS proxy)

This runs on the server PC at `192.168.1.15`.

1. Download `mediamtx.exe` from [https://github.com/bluenviron/mediamtx/releases/latest](https://github.com/bluenviron/mediamtx/releases/latest)
   - Look for: `mediamtx_vX.X.X_windows_amd64.zip`
   - Extract `mediamtx.exe` into `camera-streaming-setup\`
2. Double-click:
   ```
   camera-streaming-setup\start_camera_proxy.bat
   ```
3. Open Windows Firewall and allow inbound TCP on port `8888`

Once running, the HLS stream is at:
```
http://192.168.1.15:18888/cam02/index.m3u8
```

The dashboard CAM-02 tile switches to live video automatically.

### CAM-02 — Amcrest with YOLO person/hard-hat detection (optional)

Streams an annotated MJPEG feed with real-time PPE compliance detection:

```bash
cd camera-streaming-setup
python amcrest_yolo_stream.py
```

Edit `CAMERA_URL` at the top of `amcrest_yolo_stream.py` to match your camera's IP and credentials before running:
```python
CAMERA_URL = "rtsp://admin:YOUR-PASSWORD@192.168.1.X/cam/realmonitor?channel=1&subtype=0"
```

Stream endpoints (served on port `5002`):
| URL | Description |
|---|---|
| `http://YOUR-PC:5002/video_feed` | Live annotated MJPEG stream |
| `http://YOUR-PC:5002/detections` | Latest detections as JSON |
| `http://YOUR-PC:5002/status` | Camera + model status JSON |

### CAM-01 — Intel RealSense L515

**Simple RGB stream (no AI):**
```bash
cd camera-streaming-setup
python realsense_stream.py
```
Stream at: `http://YOUR-PC:5001/video_feed`

**RGB stream with YOLOv8 pose estimation:**
```bash
cd camera-streaming-setup
python realsense_yolo_stream.py
```

**Quick camera test** (verifies the RealSense is working):
```bash
python _test_cam.py
```
Open `http://localhost:5555` — if you see video, the camera works.

### Safety Monitor (RealSense + YOLO + UR5e integration)

Monitors the robot workspace from above using the RealSense L515, detects people, and automatically slows or pauses the UR5e when someone enters the danger zone:

```bash
cd camera-streaming-setup
python safety_monitor.py
```

Requires the UR5e to be connected and `ur-rtde` installed. Also sends zone state updates to Isaac Sim over UDP port `9876` when Isaac Sim is running.

### Isaac Sim Viewport Stream (optional)

If you have NVIDIA Isaac Sim running, stream its viewport into the dashboard:

1. In Isaac Sim, open **Script Editor** (Window → Script Editor)
2. Run:
   ```python
   exec(open("C:\\Users\\nusairwn\\Documents\\GE Demo\\machine-bridges\\isaac_viewport_stream.py").read())
   ```
3. Stream available at: `http://localhost:8211/feed`

---

## Full Startup Checklist

Use this order when bringing up the full system:

- [ ] `pnpm install` then `pnpm dev` — dashboard running at `http://localhost:3000`
- [ ] `machine-bridges\start_all_bridges.bat` — Haas + UR5e bridges running
- [ ] `camera-streaming-setup\start_camera_proxy.bat` — mediamtx HLS proxy running (CAM-02)
- [ ] `python realsense_stream.py` *(optional)* — RealSense CAM-01 stream running
- [ ] `python safety_monitor.py` *(optional)* — safety zone monitoring active

---

## Port Reference

| Port | Service |
|---|---|
| `3000` | Dashboard (Vite dev server) |
| `5000` | UR5e HTTP control API |
| `5001` | RealSense MJPEG stream |
| `5002` | Amcrest YOLO MJPEG stream |
| `5555` | RealSense quick test stream |
| `8211` | Isaac Sim viewport stream |
| `8765` | Haas TL-1 WebSocket bridge |
| `8766` | UR5e WebSocket bridge |
`18888` | mediamtx HLS proxy (CAM-02) |
| `9997` | mediamtx API health check |

---

## Changing the PC IP Address

If your PC's IP is not `192.168.1.16`, update the WebSocket URLs in:
```
client/src/lib/equipmentData.ts
```

Look for `HAAS_WS_URL` and `UR5E_WS_URL` and update them to your PC's actual IP.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard won't start | Run `pnpm install` first, then `pnpm dev` |
| Equipment shows SIM badge | Bridge scripts are not running, or machines are unreachable |
| Bridge says "Connection refused" | Check machine is on and firewall rules are added |
| UR5e bridge fails | Ensure no other RTDE client (UR Simulator) is connected — only 1 allowed at a time |
| Camera feed is black | Check camera IP is reachable (`ping 192.168.1.108`), or try sub-stream (`subtype=1`) |
| `mediamtx.exe not found` | Place `mediamtx.exe` in `camera-streaming-setup\` alongside `mediamtx.yml` |
| `pyrealsense2` install fails | Install the [Intel RealSense SDK 2.0](https://github.com/IntelRealSense/librealsense/releases) first |
