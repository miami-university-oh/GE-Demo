# GE-Demo-Revamp

IIoT monitoring dashboard for the Makino Lab. Everything runs in **one Docker
container** (FastAPI backend + built React frontend + mediamtx camera proxy as a
backend-managed subprocess) exposed on a **single port (8000)**.

The only external piece is the CAM01 camera publisher: Docker Desktop on
Windows cannot pass USB devices into Linux containers, so the RealSense L515 is
captured on the host and pushed to the backend over HTTP.

### Prerequisites
- Docker and Docker Compose installed.
- `.env` configured with your machine and camera settings (see `.env.example`).
- Python 3 on the machine the L515 is plugged into (for the publisher).

### Start the Application
```bash
docker-compose up -d --build
```
Dashboard: `http://localhost:8000`

### Start the CAM01 Publisher (one script)
```bash
publisher\run_publisher.bat
```
First run creates its Python environment automatically, then it streams. Leave
it running; it reconnects on its own if the camera or server drops. The
dashboard shows `WAITING FOR CAM01 PUBLISHER` until frames arrive.

- Close the Windows Camera app first — it can hold the device exclusively.
- Wireless: the L515 itself is USB-only, but the publisher can run on any
  machine on the network. Plug the camera into a laptop on WiFi and set
  `CAM01_INGEST_URL=http://<dashboard-server-ip>:8000` in that machine's `.env`.

### Cameras
| Camera | Source | How it reaches the dashboard |
|---|---|---|
| CAM01 (+ YOLO overlay) | RealSense L515 (USB) | host publisher → `/api/cam01/ingest` → MJPEG |
| CAM02 | Amcrest PTZ (RTSP) | mediamtx subprocess → HLS proxied at `/cam02/index.m3u8` |

CAM02 needs the real camera password in `.env` (`AMCREST_RTSP_PASS`); the
backend passes it to mediamtx at startup — it is not stored in `mediamtx.yml`.

### View Logs
```bash
docker-compose logs -f
```

### Stop the Application
```bash
docker-compose down
```
