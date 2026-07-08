import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend.bridges.haas_bridge import haas_poll_loop
from backend.bridges.ur5e_bridge import ur5e_poll_loop, send_dashboard_cmd, send_home_script
from backend.simulation.sim_tick import sim_tick_loop
from backend.cameras.realsense_stream import camera_router
from backend.state import state_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(haas_poll_loop(state_manager)),
        asyncio.create_task(ur5e_poll_loop(state_manager)),
        asyncio.create_task(sim_tick_loop(state_manager)),
    ]
    logger.info("Background tasks started: haas_bridge, ur5e_bridge, sim_tick")
    yield
    for t in tasks:
        t.cancel()
    logger.info("Background tasks cancelled")


app = FastAPI(lifespan=lifespan)

app.include_router(camera_router)


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
