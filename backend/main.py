import asyncio
import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.bridges.haas_bridge import haas_poll_loop
from backend.bridges.ur5e_bridge import ur5e_poll_loop, send_dashboard_cmd, send_home_script
from backend.simulation.sim_tick import sim_tick_loop
from backend.cameras.cam01_stream import camera_router
from backend.cameras.cam02_proxy import cam02_router
from backend.config import settings
from backend.state import state_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class CameraAccessFilter(logging.Filter):
    # Frame ingest (~20/s) and HLS playlist polls (several/s) would bury real information.
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/api/cam01/ingest" not in msg and "/cam02/" not in msg


logging.getLogger("uvicorn.access").addFilter(CameraAccessFilter())

connected_clients: set[WebSocket] = set()


async def broadcast_state_update(payload: dict):
    msg = json.dumps(payload)
    dead: set[WebSocket] = set()
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


state_manager.on_update = broadcast_state_update


async def handle_command(cmd: dict):
    action = cmd.get("action")
    if action in ("play", "stop", "pause"):
        await send_dashboard_cmd(action)
    elif action == "home":
        await send_home_script()


def build_amcrest_rtsp_url() -> str:
    return (
        f"rtsp://{settings.amcrest_rtsp_user}:{settings.amcrest_rtsp_pass}"
        f"@{settings.amcrest_ip}/cam/realmonitor?channel=1&subtype=0"
    )


def start_mediamtx() -> subprocess.Popen | None:
    if not Path("mediamtx").exists():
        logger.warning("mediamtx binary not found, cam02 HLS disabled")
        return None
    # Credentials live in .env, not mediamtx.yml; inject the source URL at launch.
    env = dict(os.environ, MTX_PATHS_CAM02_SOURCE=build_amcrest_rtsp_url())
    proc = subprocess.Popen(["./mediamtx", "mediamtx.yml"], env=env)
    logger.info("mediamtx subprocess started, pid=%d", proc.pid)
    return proc


def stop_mediamtx(proc: subprocess.Popen | None):
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    logger.info("mediamtx subprocess stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mediamtx_proc = start_mediamtx()
    tasks = [
        asyncio.create_task(haas_poll_loop(state_manager)),
        asyncio.create_task(ur5e_poll_loop(state_manager)),
        asyncio.create_task(sim_tick_loop(state_manager)),
    ]
    logger.info("Background tasks started: haas_bridge, ur5e_bridge, sim_tick")
    yield
    for t in tasks:
        t.cancel()
    stop_mediamtx(mediamtx_proc)
    logger.info("Background tasks cancelled")


app = FastAPI(lifespan=lifespan)

app.include_router(camera_router)
app.include_router(cam02_router)


@app.websocket("/ws/telemetry")
async def telemetry_ws(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info("WebSocket client connected, total=%d", len(connected_clients))

    try:
        await ws.send_text(json.dumps(state_manager.get_snapshot()))
        async for msg in ws.iter_text():
            try:
                cmd = json.loads(msg)
                await handle_command(cmd)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        logger.info("WebSocket client disconnected, total=%d", len(connected_clients))


try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except Exception:
    logger.warning("frontend/dist not found, skipping static file mount")


@app.exception_handler(404)
async def spa_fallback(request, exc):
    # Client-side routes like /cameras must load the SPA on refresh or deep link.
    path = request.url.path
    index = Path("frontend/dist/index.html")
    if path.startswith(("/api", "/ws", "/cam02")) or not index.exists():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse(index)
