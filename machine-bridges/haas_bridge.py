"""
haas_bridge.py — Haas TL-1 Q-Command → WebSocket Bridge
=========================================================
Runs on: Your PC (192.168.1.16)
Connects to: Haas TL-1 at 192.168.1.50:5051 via Q-Command TCP
Serves:  WebSocket on ws://0.0.0.0:8765  (dashboard connects here)

Install dependencies (run once):
    pip install websockets

Run:
    python haas_bridge.py

The dashboard will automatically switch from simulation to live data
once this script is running and the Haas control is powered on.
"""

import asyncio
import json
import socket
import time
import logging
from datetime import datetime

import websockets
from websockets.server import WebSocketServerProtocol

# ── Configuration ────────────────────────────────────────────────
HAAS_IP        = "192.168.1.50"
HAAS_PORT      = 5051
WS_HOST        = "0.0.0.0"
WS_PORT        = 8765
POLL_INTERVAL  = 1.0   # seconds between Q-Command polls
RECONNECT_WAIT = 5.0   # seconds before retrying Haas connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HAAS] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("haas_bridge")

# ── Q-Command query list ─────────────────────────────────────────
# Each tuple: (variable_name, Q-Command string)
# Full list: https://www.haascnc.com/service/troubleshooting-and-how-to/how-to/machine-data-collection---qc.html
QUERIES = [
    ("program",       "?Q500"),   # Active program name
    ("status",        "?Q600"),   # Machine status (IDLE / FEED HOLD / ALARM / etc.)
    ("part_count",    "?Q402"),   # Parts count
    ("tool_number",   "?Q403"),   # Current tool number
    ("spindle_rpm",   "?Q408"),   # Commanded spindle speed
    ("spindle_load",  "?Q410"),   # Spindle load %
    ("feed_rate",     "?Q411"),   # Commanded feed rate
    ("x_pos",         "?Q504"),   # X machine position (work coordinate)
    ("z_pos",         "?Q506"),   # Z machine position (work coordinate — TL-1 is 2-axis)
    ("cycle_time",    "?Q404"),   # Cycle time (seconds)
    ("power_on_time", "?Q406"),   # Power-on time
    ("alarm",         "?Q300"),   # Active alarm code (0 = no alarm)
    ("coolant",       "?Q409"),   # Coolant status
]

def query_haas(sock: socket.socket, cmd: str) -> str:
    """Send a single Q-Command and return the raw response string."""
    try:
        sock.sendall((cmd + "\r\n").encode("ascii"))
        data = b""
        sock.settimeout(2.0)
        while True:
            chunk = sock.recv(256)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        return data.decode("ascii", errors="replace").strip()
    except socket.timeout:
        return ""
    except Exception as e:
        raise ConnectionError(f"Q-Command failed: {e}") from e

def parse_response(raw: str) -> str:
    """Strip the echoed command and return just the value."""
    # Haas response format: ">Q408\r\n1200\r\n"  or  "1200"
    lines = [l.strip() for l in raw.replace("\r", "\n").split("\n") if l.strip()]
    for line in lines:
        if not line.startswith(">") and not line.startswith("?"):
            return line
    return raw.strip()

def build_payload(raw: dict) -> dict:
    """Convert raw Q-Command strings into a typed dashboard payload."""
    def safe_float(key: str, default=0.0) -> float:
        try:
            return float(raw.get(key, default))
        except (ValueError, TypeError):
            return default

    def safe_int(key: str, default=0) -> int:
        try:
            return int(float(raw.get(key, default)))
        except (ValueError, TypeError):
            return default

    status_raw = raw.get("status", "").upper()
    if "ALARM" in status_raw:
        status = "alarm"
    elif "IDLE" in status_raw or "NOT RUNNING" in status_raw:
        status = "idle"
    elif "FEED HOLD" in status_raw:
        status = "paused"
    elif "RUNNING" in status_raw or "CYCLE" in status_raw:
        status = "running"
    else:
        status = "idle"

    alarm_code = safe_int("alarm")
    alarms = [f"ALARM {alarm_code}"] if alarm_code != 0 else []

    spindle_rpm  = safe_float("spindle_rpm")
    spindle_load = safe_float("spindle_load")
    feed_rate    = safe_float("feed_rate")

    # Estimate power from spindle load (TL-1 max ~7.5 kW)
    power_kw = round(spindle_load / 100.0 * 7.5, 2)

    return {
        "machine":      "haas-tl1",
        "name":         "Haas TL-1",
        "type":         "CNC Lathe",
        "timestamp":    datetime.now().isoformat(),
        "status":       status,
        "program":      raw.get("program", "—"),
        "spindleRpm":   spindle_rpm,
        "spindleLoad":  spindle_load,
        "feedRate":     feed_rate,
        "position": {
            "x": safe_float("x_pos"),
            "z": safe_float("z_pos"),
        },
        "toolNumber":   safe_int("tool_number"),
        "cycleTime":    safe_float("cycle_time"),
        "partCount":    safe_int("part_count"),
        "powerKw":      power_kw,
        "coolant":      "ON" in raw.get("coolant", "").upper(),
        "alarms":       alarms,
    }

# ── WebSocket broadcast ──────────────────────────────────────────
connected_clients: set[WebSocketServerProtocol] = set()
latest_payload: dict = {"machine": "haas-tl1", "status": "connecting"}

async def ws_handler(ws: WebSocketServerProtocol):
    connected_clients.add(ws)
    log.info(f"Dashboard connected ({len(connected_clients)} clients)")
    try:
        # Send latest known state immediately on connect
        await ws.send(json.dumps(latest_payload))
        async for _ in ws:
            pass  # We don't expect messages from the dashboard
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(ws)
        log.info(f"Dashboard disconnected ({len(connected_clients)} clients)")

async def broadcast(payload: dict):
    global latest_payload
    latest_payload = payload
    if connected_clients:
        msg = json.dumps(payload)
        await asyncio.gather(
            *[ws.send(msg) for ws in list(connected_clients)],
            return_exceptions=True,
        )

# ── Haas polling loop ────────────────────────────────────────────
async def haas_poll_loop():
    while True:
        sock = None
        try:
            log.info(f"Connecting to Haas TL-1 at {HAAS_IP}:{HAAS_PORT}…")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((HAAS_IP, HAAS_PORT))
            log.info("Connected to Haas TL-1 ✓")

            while True:
                raw = {}
                for name, cmd in QUERIES:
                    resp = query_haas(sock, cmd)
                    raw[name] = parse_response(resp)

                payload = build_payload(raw)
                await broadcast(payload)
                log.debug(f"Polled: status={payload['status']} rpm={payload['spindleRpm']}")
                await asyncio.sleep(POLL_INTERVAL)

        except (ConnectionError, OSError, socket.error) as e:
            log.warning(f"Haas connection lost: {e}. Retrying in {RECONNECT_WAIT}s…")
            await broadcast({"machine": "haas-tl1", "status": "offline", "alarms": [str(e)]})
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        await asyncio.sleep(RECONNECT_WAIT)

# ── Main ─────────────────────────────────────────────────────────
async def main():
    log.info(f"Starting Haas TL-1 bridge — WebSocket on ws://0.0.0.0:{WS_PORT}")
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        await haas_poll_loop()

if __name__ == "__main__":
    asyncio.run(main())
