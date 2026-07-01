"""
ur5e_bridge.py — UR5e Cobot RTDE → WebSocket + Siri/HTTP Bridge
================================================================
Runs on: Your PC (192.168.1.16)
Connects to: UR5e controller at 192.168.1.15 via RTDE (port 30004)
Serves:
  WebSocket  ws://0.0.0.0:8766   (dashboard connects here for live data)
  HTTP       http://0.0.0.0:5000  (Siri Shortcuts / REST control)

Install dependencies:
    pip install websockets flask

Run:
    python ur5e_bridge.py

Siri Shortcut setup:
  URL:    http://192.168.1.16:5000/play   (or /stop, /pause, /home)
  Method: POST
  Header: X-API-Key: makino-lab
  Phrase: "Start the robot" / "Stop the robot" / etc.

Dashboard WebSocket commands (send JSON to ws://192.168.1.16:8766):
  {"action": "play"}
  {"action": "stop"}
  {"action": "pause"}
  {"action": "home"}
  {"action": "load", "program": "pick_and_place"}
"""

import asyncio
import functools
import json
import logging
import math
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────
UR_IP             = "192.168.1.15"
RTDE_PORT         = 30004
DASHBOARD_PORT    = 29999
SCRIPT_PORT       = 30001
WS_HOST           = "0.0.0.0"
WS_PORT           = 8766
HTTP_PORT         = 5000
API_KEY           = "makino-lab"
POLL_INTERVAL     = 0.1
RECONNECT_WAIT    = 5.0

executor = ThreadPoolExecutor(max_workers=4)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [UR5e] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ur5e_bridge")

# ── RTDE Constants ───────────────────────────────────────────────
RTDE_CMD_REQUEST_PROTOCOL_VERSION      = 86   # 'V'
RTDE_CMD_CONTROL_PACKAGE_SETUP_OUTPUTS = 79   # 'O'
RTDE_CMD_CONTROL_PACKAGE_START         = 83   # 'S'
RTDE_CMD_DATA_PACKAGE                  = 85   # 'U'

ROBOT_MODE_NAMES = {
    -1: "NO_CONTROLLER", 0: "DISCONNECTED", 1: "CONFIRM_SAFETY",
    2: "BOOTING", 3: "POWER_OFF", 4: "POWER_ON", 5: "IDLE",
    6: "BACKDRIVE", 7: "RUNNING", 8: "UPDATING_FIRMWARE",
}
SAFETY_MODE_NAMES = {
    1: "NORMAL", 2: "REDUCED", 3: "PROTECTIVE_STOP",
    4: "RECOVERY", 5: "SAFEGUARD_STOP", 6: "SYSTEM_EMERGENCY_STOP",
    7: "ROBOT_EMERGENCY_STOP", 8: "VIOLATION", 9: "FAULT",
}
JOINT_LABELS = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]

HOME_SCRIPT = """\
def home():
  movej([0, -1.5708, 0, -1.5708, 0, 0], a=0.5, v=0.3)
end
home()
"""

# ── Control helpers ───────────────────────────────────────────────

def dashboard_cmd(cmd: str) -> str:
    """Send a single Dashboard Server command and return the response."""
    try:
        with socket.create_connection((UR_IP, DASHBOARD_PORT), timeout=3.0) as s:
            s.recv(1024)  # welcome banner
            s.sendall((cmd + "\n").encode())
            return s.recv(1024).decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"ERROR: {e}"

def send_urscript(script: str) -> None:
    """Send a URScript program to the primary client interface (port 30001)."""
    with socket.create_connection((UR_IP, SCRIPT_PORT), timeout=3.0) as s:
        s.sendall((script + "\n").encode("utf-8"))

# ── RTDE Variables to subscribe ──────────────────────────────────
# We subscribe to ALL of these in one shot. If the controller returns
# NOT_FOUND for any, we still start streaming — NOT_FOUND variables
# simply produce 0 bytes in the data packet (they are excluded from
# the binary payload).
RTDE_VARIABLES = [
    "actual_q",
    "actual_qd",
    "actual_current",
    "actual_TCP_pose",
    "actual_TCP_speed",
    "target_speed_fraction",
    "robot_mode",
    "safety_mode",
    "actual_robot_voltage",
    "actual_robot_current",
    "runtime_state",
    "output_bit_registers0_to_31",
]

# Type sizes for binary parsing
TYPE_SIZES = {
    "VECTOR6D": 48,   # 6 doubles
    "DOUBLE":   8,
    "INT32":    4,
    "UINT32":   4,
    "NOT_FOUND": 0,   # excluded from data packet
}

# ── Socket helpers ───────────────────────────────────────────────

def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed")
        data += chunk
    return data

def rtde_send(sock, cmd, payload=b""):
    size = 3 + len(payload)
    sock.sendall(struct.pack(">HB", size, cmd) + payload)

def rtde_recv(sock):
    header = recv_exact(sock, 3)
    size, cmd = struct.unpack(">HB", header[:3])
    payload = recv_exact(sock, size - 3) if size > 3 else b""
    return cmd, payload

# ── RTDE Setup ───────────────────────────────────────────────────

# Set after setup — list of (var_name, type_string) for parsing
recipe_layout = []

def rtde_setup(sock):
    """Negotiate protocol, subscribe ONCE, and start streaming."""
    global recipe_layout

    # 1. Request protocol version 2
    rtde_send(sock, RTDE_CMD_REQUEST_PROTOCOL_VERSION, struct.pack(">H", 2))
    cmd, payload = rtde_recv(sock)
    accepted = struct.unpack(">B", payload[:1])[0]
    if not accepted:
        raise RuntimeError("RTDE protocol version 2 not accepted")
    log.info("RTDE protocol version 2 accepted")

    # 2. Setup outputs — subscribe to all variables in ONE call
    recipe_str = ",".join(RTDE_VARIABLES)
    rtde_send(sock, RTDE_CMD_CONTROL_PACKAGE_SETUP_OUTPUTS, recipe_str.encode("utf-8"))
    cmd, payload = rtde_recv(sock)

    # Parse response: first byte = recipe ID, rest = comma-separated types
    recipe_id = payload[0]
    types_str = payload[1:].decode("utf-8", errors="replace")
    types_list = [t.strip() for t in types_str.split(",")]

    # Verify count matches
    if len(types_list) != len(RTDE_VARIABLES):
        # Try full payload as string (some firmware versions)
        full_str = payload.decode("utf-8", errors="replace")
        full_list = [t.strip() for t in full_str.split(",")]
        if len(full_list) == len(RTDE_VARIABLES):
            types_list = full_list
            recipe_id = 1
        elif len(full_list) == len(RTDE_VARIABLES) + 1:
            types_list = full_list[1:]
            recipe_id = 1

    log.info(f"Recipe ID: {recipe_id}")
    log.info(f"Types: {','.join(types_list)}")

    # Build recipe layout — includes NOT_FOUND entries (0 bytes in data)
    recipe_layout = []
    for i, var_name in enumerate(RTDE_VARIABLES):
        if i < len(types_list):
            t = types_list[i]
            recipe_layout.append((var_name, t))
            if t == "NOT_FOUND":
                log.warning(f"  '{var_name}' → NOT_FOUND (will be skipped in data)")
        else:
            recipe_layout.append((var_name, "NOT_FOUND"))

    supported = sum(1 for _, t in recipe_layout if t != "NOT_FOUND")
    log.info(f"Supported: {supported}/{len(RTDE_VARIABLES)} variables")

    if supported == 0:
        raise RuntimeError("No variables supported — check UR firmware")

    # 3. Start streaming immediately — DO NOT re-subscribe
    rtde_send(sock, RTDE_CMD_CONTROL_PACKAGE_START)
    cmd, payload = rtde_recv(sock)
    accepted = struct.unpack(">B", payload[:1])[0]
    if not accepted:
        raise RuntimeError("RTDE start rejected")
    log.info("RTDE streaming started ✓")


def parse_data_package(payload):
    """Parse a DATA_PACKAGE using recipe_layout.
    NOT_FOUND variables are excluded from the binary payload entirely."""
    offset = 1  # skip recipe ID byte
    values = {}

    for var_name, var_type in recipe_layout:
        if var_type == "NOT_FOUND":
            # NOT_FOUND variables are NOT in the data packet at all
            values[var_name] = None
            continue

        try:
            if var_type == "VECTOR6D":
                vec = struct.unpack_from(">6d", payload, offset)
                values[var_name] = list(vec)
                offset += 48
            elif var_type == "DOUBLE":
                values[var_name] = struct.unpack_from(">d", payload, offset)[0]
                offset += 8
            elif var_type == "INT32":
                values[var_name] = struct.unpack_from(">i", payload, offset)[0]
                offset += 4
            elif var_type == "UINT32":
                values[var_name] = struct.unpack_from(">I", payload, offset)[0]
                offset += 4
            else:
                # Unknown type — skip
                values[var_name] = None
        except struct.error:
            values[var_name] = None
            break

    return values


def build_dashboard_payload(rtde_data, program_name="—"):
    """Convert RTDE data to the format the dashboard expects."""
    robot_mode  = rtde_data.get("robot_mode") or -1
    safety_mode = rtde_data.get("safety_mode") or 1
    runtime     = rtde_data.get("runtime_state") or 0

    # Status logic
    if safety_mode >= 3:
        status = "alarm"
    elif robot_mode == 7 and runtime == 2:
        status = "running"
    elif robot_mode == 5:
        status = "idle"
    elif robot_mode in (3, 4):
        status = "offline"
    else:
        status = "idle"

    # Alarms
    alarms = []
    if safety_mode == 3:
        alarms.append("PROTECTIVE STOP")
    elif safety_mode == 5:
        alarms.append("SAFEGUARD STOP")
    elif safety_mode == 6:
        alarms.append("SYSTEM E-STOP")
    elif safety_mode == 7:
        alarms.append("ROBOT E-STOP")
    elif safety_mode >= 8:
        alarms.append(f"SAFETY FAULT: {SAFETY_MODE_NAMES.get(safety_mode, safety_mode)}")

    # TCP
    tcp = rtde_data.get("actual_TCP_pose") or [0]*6
    tcp_speed_vec = rtde_data.get("actual_TCP_speed") or [0]*6
    tcp_speed = round(math.sqrt(sum(v**2 for v in tcp_speed_vec[:3])) * 1000, 1)

    # Joints
    joints_q   = rtde_data.get("actual_q") or [0]*6
    joints_qd  = rtde_data.get("actual_qd") or [0]*6
    joints_cur = rtde_data.get("actual_current") or [0]*6

    joints = [
        {
            "id":     f"J{i+1}",
            "label":  JOINT_LABELS[i],
            "angle":  round(math.degrees(joints_q[i]), 2) if joints_q[i] is not None else 0,
            "speed":  round(math.degrees(joints_qd[i]), 2) if joints_qd[i] is not None else 0,
            "torque": round(abs(joints_cur[i]) * 3.0, 1) if joints_cur[i] is not None else 0,
        }
        for i in range(6)
    ]

    voltage = rtde_data.get("actual_robot_voltage") or 0.0
    current = rtde_data.get("actual_robot_current") or 0.0

    return {
        "machine":    "ur5e",
        "name":       "UR5e Cobot",
        "type":       "Collaborative Robot Arm",
        "timestamp":  datetime.now().isoformat(),
        "status":     status,
        "program":    program_name,
        "robotMode":  ROBOT_MODE_NAMES.get(robot_mode, str(robot_mode)),
        "safetyMode": SAFETY_MODE_NAMES.get(safety_mode, str(safety_mode)),
        "runtimeState": ["STOPPED", "STOPPED", "PLAYING", "PAUSING", "PAUSED", "RESUMING"][min(runtime, 5)] if isinstance(runtime, int) else "STOPPED",
        "tcpPosition": {
            "x":  round(tcp[0] * 1000, 2),
            "y":  round(tcp[1] * 1000, 2),
            "z":  round(tcp[2] * 1000, 2),
            "rx": round(math.degrees(tcp[3]), 2),
            "ry": round(math.degrees(tcp[4]), 2),
            "rz": round(math.degrees(tcp[5]), 2),
        },
        "tcpSpeed":       tcp_speed,
        "speedFraction":  round((rtde_data.get("target_speed_fraction") or 0.0) * 100, 1),
        "joints":         joints,
        "powerKw":        round(voltage * current / 1000.0, 3),
        "voltage":        round(voltage, 1),
        "current":        round(current, 2),
        "alarms":         alarms,
        "digitalOutputs": rtde_data.get("output_bit_registers0_to_31") or 0,
    }


# ── Dashboard Server query ───────────────────────────────────────

def get_program_name():
    try:
        with socket.create_connection((UR_IP, DASHBOARD_PORT), timeout=2.0) as s:
            s.recv(1024)
            s.sendall(b"get loaded program\n")
            resp = s.recv(1024).decode("utf-8", errors="replace").strip()
            if ":" in resp:
                return resp.split(":")[-1].strip().split("/")[-1]
            return resp
    except Exception:
        return "—"


# ── WebSocket server ─────────────────────────────────────────────

connected_clients = set()
latest_payload = {"machine": "ur5e", "status": "connecting"}

async def handle_ws_command(cmd: dict) -> str:
    """Handle a JSON command sent from the dashboard or any WebSocket client."""
    loop = asyncio.get_event_loop()
    action = cmd.get("action", "")
    if action in ("play", "stop", "pause"):
        return await loop.run_in_executor(executor, dashboard_cmd, action)
    elif action == "home":
        await loop.run_in_executor(executor, send_urscript, HOME_SCRIPT)
        return "moving to home"
    elif action == "load":
        prog = cmd.get("program", "")
        return await loop.run_in_executor(executor, dashboard_cmd, f"load /programs/{prog}.urp")
    return f"unknown action: {action}"

async def ws_handler(ws):
    connected_clients.add(ws)
    log.info(f"Dashboard connected ({len(connected_clients)} clients)")
    try:
        await ws.send(json.dumps(latest_payload))
        async for raw in ws:
            try:
                cmd = json.loads(raw)
                result = await handle_ws_command(cmd)
                await ws.send(json.dumps({"ack": cmd.get("action"), "result": result}))
                log.info(f"WS command: {cmd.get('action')} → {result}")
            except Exception as e:
                log.debug(f"WS command error: {e}")
    except Exception:
        pass
    finally:
        connected_clients.discard(ws)

async def broadcast(payload):
    global latest_payload
    latest_payload = payload
    if connected_clients:
        msg = json.dumps(payload)
        await asyncio.gather(
            *[ws.send(msg) for ws in list(connected_clients)],
            return_exceptions=True,
        )


# ── Main polling loop ────────────────────────────────────────────

async def ur5e_poll_loop():
    program_name = "—"
    counter = 0

    while True:
        sock = None
        try:
            log.info(f"Connecting to UR5e RTDE at {UR_IP}:{RTDE_PORT}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((UR_IP, RTDE_PORT))
            rtde_setup(sock)
            sock.settimeout(2.0)
            log.info("UR5e connected and streaming ✓")

            while True:
                cmd, payload = rtde_recv(sock)
                if cmd == RTDE_CMD_DATA_PACKAGE:
                    data = parse_data_package(payload)

                    counter += 1
                    if counter >= 50:
                        counter = 0
                        program_name = await asyncio.get_event_loop().run_in_executor(
                            None, get_program_name
                        )

                    dashboard_msg = build_dashboard_payload(data, program_name)
                    await broadcast(dashboard_msg)

                await asyncio.sleep(POLL_INTERVAL)

        except (ConnectionError, OSError, socket.error, RuntimeError) as e:
            log.warning(f"UR5e connection issue: {e}. Retrying in {RECONNECT_WAIT}s...")
            await broadcast({"machine": "ur5e", "status": "offline", "alarms": [str(e)]})
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        await asyncio.sleep(RECONNECT_WAIT)


# ── Flask Siri/HTTP bridge ────────────────────────────────────────

def make_flask_app():
    try:
        from flask import Flask, request, jsonify, abort
    except ImportError:
        log.warning("Flask not installed — Siri HTTP bridge disabled.  Run: pip install flask")
        return None

    app = Flask(__name__)

    def check_key():
        if request.headers.get("X-API-Key") != API_KEY:
            abort(401)

    @app.route("/play", methods=["POST"])
    def play():
        check_key()
        return jsonify({"status": dashboard_cmd("play"), "timestamp": datetime.now().isoformat()})

    @app.route("/stop", methods=["POST"])
    def stop():
        check_key()
        return jsonify({"status": dashboard_cmd("stop"), "timestamp": datetime.now().isoformat()})

    @app.route("/pause", methods=["POST"])
    def pause():
        check_key()
        return jsonify({"status": dashboard_cmd("pause"), "timestamp": datetime.now().isoformat()})

    @app.route("/home", methods=["POST"])
    def home():
        check_key()
        try:
            send_urscript(HOME_SCRIPT)
            result = "moving to home"
        except Exception as e:
            result = f"error: {e}"
        return jsonify({"status": result, "timestamp": datetime.now().isoformat()})

    @app.route("/load/<program_name>", methods=["POST"])
    def load(program_name):
        check_key()
        result = dashboard_cmd(f"load /programs/{program_name}.urp")
        return jsonify({"status": result, "timestamp": datetime.now().isoformat()})

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify({**latest_payload, "timestamp": datetime.now().isoformat()})

    return app


# ── Entry point ──────────────────────────────────────────────────

async def main():
    log.info(f"UR5e bridge starting")
    log.info(f"  Robot:     {UR_IP}:{RTDE_PORT}")
    log.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    log.info(f"  Siri HTTP: http://0.0.0.0:{HTTP_PORT}")

    # Start Flask in a background daemon thread
    flask_app = make_flask_app()
    if flask_app:
        threading.Thread(
            target=lambda: flask_app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, threaded=True),
            daemon=True,
        ).start()
        log.info(f"Siri endpoints (header X-API-Key: {API_KEY}):")
        log.info(f"  POST http://192.168.1.16:{HTTP_PORT}/play   → 'Start the robot'")
        log.info(f"  POST http://192.168.1.16:{HTTP_PORT}/stop   → 'Stop the robot'")
        log.info(f"  POST http://192.168.1.16:{HTTP_PORT}/pause  → 'Pause the robot'")
        log.info(f"  POST http://192.168.1.16:{HTTP_PORT}/home   → 'Home the robot'")
        log.info(f"  GET  http://192.168.1.16:{HTTP_PORT}/status → no auth required")

    try:
        from websockets.asyncio.server import serve
        async with serve(ws_handler, WS_HOST, WS_PORT):
            log.info(f"WebSocket live on ws://0.0.0.0:{WS_PORT} ✓")
            await ur5e_poll_loop()
    except ImportError:
        import websockets
        async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
            log.info(f"WebSocket live on ws://0.0.0.0:{WS_PORT} ✓")
            await ur5e_poll_loop()

if __name__ == "__main__":
    asyncio.run(main())
