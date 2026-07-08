import asyncio
import logging
import socket

from backend.config import settings

logger = logging.getLogger(__name__)

QUERIES = [
    ("program",      "?Q500"),
    ("status",       "?Q600"),
    ("part_count",   "?Q402"),
    ("tool_number",  "?Q403"),
    ("spindle_rpm",  "?Q408"),
    ("spindle_load", "?Q410"),
    ("feed_rate",    "?Q411"),
    ("x_pos",        "?Q504"),
    ("z_pos",        "?Q506"),
    ("cycle_time",   "?Q404"),
    ("alarm",        "?Q300"),
    ("coolant",      "?Q409"),
]


def query_haas(sock: socket.socket, cmd: str) -> str:
    sock.sendall((cmd + "\r\n").encode("ascii"))
    data = b""
    sock.settimeout(2.0)
    while True:
        chunk = sock.recv(256)
        if not chunk or b"\n" in chunk:
            data += chunk
            break
        data += chunk
    return data.decode("ascii", errors="replace").strip()


def parse_response(raw: str) -> str:
    lines = [l.strip() for l in raw.replace("\r", "\n").split("\n") if l.strip()]
    for line in lines:
        if not line.startswith(">") and not line.startswith("?"):
            return line
    return raw.strip()


def safe_float(raw: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(raw.get(key, default))
    except (ValueError, TypeError):
        return default


def safe_int(raw: dict, key: str, default: int = 0) -> int:
    try:
        return int(float(raw.get(key, default)))
    except (ValueError, TypeError):
        return default


def parse_haas_status(status_raw: str) -> str:
    s = status_raw.upper()
    if "ALARM" in s:
        return "alarm"
    if "FEED HOLD" in s:
        return "paused"
    if "RUNNING" in s or "CYCLE" in s:
        return "running"
    return "idle"


def build_payload(raw: dict) -> dict:
    spindle_load = safe_float(raw, "spindle_load")
    alarm_code = safe_int(raw, "alarm")

    return {
        "machine": "haas-tl1",
        "status": parse_haas_status(raw.get("status", "")),
        "program": raw.get("program", "\u2014"),
        "spindleRpm": safe_float(raw, "spindle_rpm"),
        "spindleLoad": spindle_load,
        "feedRate": safe_float(raw, "feed_rate"),
        "position": {
            "x": safe_float(raw, "x_pos"),
            "z": safe_float(raw, "z_pos"),
        },
        "toolNumber": safe_int(raw, "tool_number"),
        "cycleTime": safe_float(raw, "cycle_time"),
        "partCount": safe_int(raw, "part_count"),
        "powerKw": round(spindle_load / 100.0 * 7.5, 2),
        "coolant": "ON" in raw.get("coolant", "").upper(),
        "alarms": [f"ALARM {alarm_code}"] if alarm_code != 0 else [],
    }


def poll_once(sock: socket.socket) -> dict:
    raw = {}
    for name, cmd in QUERIES:
        resp = query_haas(sock, cmd)
        raw[name] = parse_response(resp)
    return raw


async def haas_poll_loop(state_manager):
    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            await asyncio.to_thread(sock.connect, (settings.haas_ip, settings.haas_port))
            state_manager.set_haas_bridge_status("live")
            logger.info("Haas TL-1 connected at %s:%d", settings.haas_ip, settings.haas_port)

            while True:
                raw = await asyncio.to_thread(poll_once, sock)
                payload = build_payload(raw)
                await state_manager.update_haas(payload)
                await asyncio.sleep(settings.haas_poll_interval)

        except Exception as e:
            logger.warning("Haas bridge error: %s", e)
            state_manager.set_haas_bridge_status("offline")
            await state_manager.update_haas({"machine": "haas-tl1", "status": "offline"})
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        await asyncio.sleep(settings.reconnect_wait)
