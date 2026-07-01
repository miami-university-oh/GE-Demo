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
UR_IP = "192.168.1.15"
RTDE_PORT = 30004
DASHBOARD_PORT = 29999
SCRIPT_PORT = 30001
WS_HOST = "0.0.0.0"
WS_PORT = 8766
HTTP_PORT = 5000
API_KEY = "makino-lab"
POLL_INTERVAL = 0.1
RECONNECT_WAIT = 5.0

executor = ThreadPoolExecutor(max_workers=4)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [UR5e] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ur5e_bridge")

# ── RTDE Constants ───────────────────────────────────────────────
RTDE_CMD_REQUEST_PROTOCOL_VERSION = 86  # 'V'
RTDE_CMD_CONTROL_PACKAGE_SETUP_OUTPUTS = 79  # 'O'
RTDE_CMD_CONTROL_PACKAGE_START = 83  # 'S'
RTDE_CMD_DATA_PACKAGE = 85  # 'U'

ROBOT_MODE_NAMES = {
    -1: "NO_CONTROLLER",
    0: "DISCONNECTED",
    1: "CONFIRM_SAFETY",
    2: "BOOTING",
    3: "POWER_OFF",
    4: "POWER_ON",
    5: "IDLE",
    6: "BACKDRIVE",
    7: "RUNNING",
    8: "UPDATING_FIRMWARE",
}
SAFETY_MODE_NAMES = {
    1: "NORMAL",
    2: "REDUCED",
    3: "PROTECTIVE_STOP",
    4: "RECOVERY",
    5: "SAFEGUARD_STOP",
    6: "SYSTEM_EMERGENCY_STOP",
    7: "ROBOT_EMERGENCY_STOP",
    8: "VIOLATION",
    9: "FAULT",
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
    """Send a single command to the UR Dashboard Server and return its response.

    Opens a new TCP connection to ``UR_IP:DASHBOARD_PORT`` for each call,
    discards the initial welcome banner, sends *cmd* terminated with ``\\n``,
    and reads back up to 1024 bytes of response.

    Args:
        cmd (str): Dashboard Server command string, e.g. ``"play"``,
            ``"stop"``, or ``"get loaded program"``.

    Returns:
        str: The server's response decoded as UTF-8 and stripped of surrounding
            whitespace.  Returns ``"ERROR: <reason>"`` if the connection or
            send fails.
    """
    try:
        with socket.create_connection((UR_IP, DASHBOARD_PORT), timeout=3.0) as s:
            s.recv(1024)  # welcome banner
            s.sendall((cmd + "\n").encode())
            return s.recv(1024).decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"ERROR: {e}"


def send_urscript(script: str) -> None:
    """Upload a URScript program to the robot's primary client interface.

    Connects to ``UR_IP:SCRIPT_PORT`` (port 30001), sends the full script
    encoded as UTF-8 followed by a newline, then closes the socket.  The
    controller starts executing the script immediately on receipt.

    Args:
        script (str): Complete URScript source code to execute on the robot.
    """
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
    "VECTOR6D": 48,  # 6 doubles
    "DOUBLE": 8,
    "INT32": 4,
    "UINT32": 4,
    "NOT_FOUND": 0,  # excluded from data packet
}

# ── Socket helpers ───────────────────────────────────────────────


def recv_exact(sock, n):
    """Read exactly *n* bytes from *sock*, blocking until all bytes arrive.

    Loops over ``sock.recv`` to handle short reads that can occur on
    streaming sockets.  Raises immediately if the connection drops before
    *n* bytes have been received.

    Args:
        sock (socket.socket): Connected TCP socket to read from.
        n (int): Exact number of bytes required.

    Returns:
        bytes: Exactly *n* bytes read from the socket.

    Raises:
        ConnectionError: If the remote end closes the connection before
            *n* bytes have been delivered.
    """
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed")
        data += chunk
    return data


def rtde_send(sock, cmd, payload=b""):
    """Pack and transmit a single RTDE frame over *sock*.

    RTDE wire format: 2-byte big-endian total size (header + payload),
    followed by 1-byte command byte, followed by *payload* bytes.

    Args:
        sock (socket.socket): Connected RTDE socket (port 30004).
        cmd (int): RTDE command byte, one of the ``RTDE_CMD_*`` constants.
        payload (bytes): Optional binary payload for the command.  Defaults
            to an empty byte string (header-only frame).
    """
    size = 3 + len(payload)
    sock.sendall(struct.pack(">HB", size, cmd) + payload)


def rtde_recv(sock):
    """Read one complete RTDE frame from *sock* and return its command and payload.

    Reads the 3-byte header to determine the total frame size, then reads the
    remaining payload bytes with :func:`recv_exact`.

    Args:
        sock (socket.socket): Connected RTDE socket with an incoming frame
            ready to read.

    Returns:
        tuple[int, bytes]: A ``(cmd, payload)`` pair where *cmd* is the
            1-byte RTDE command identifier and *payload* is the raw binary
            body (empty bytes for header-only frames).
    """
    header = recv_exact(sock, 3)
    size, cmd = struct.unpack(">HB", header[:3])
    payload = recv_exact(sock, size - 3) if size > 3 else b""
    return cmd, payload


# ── RTDE Setup ───────────────────────────────────────────────────

# Set after setup — list of (var_name, type_string) for parsing
recipe_layout = []


def rtde_setup(sock):
    """Negotiate RTDE protocol version 2, subscribe to output variables, and start streaming.

    Performs the full RTDE handshake in three steps:

    1. **Protocol negotiation** — requests version 2; raises ``RuntimeError``
       if the controller rejects it.
    2. **Output subscription** — sends all ``RTDE_VARIABLES`` in a single
       ``CONTROL_PACKAGE_SETUP_OUTPUTS`` request and parses the returned type
       list.  Variables the firmware does not recognise are marked
       ``NOT_FOUND`` and excluded from subsequent data packets.  The resulting
       ``(name, type)`` pairs are stored in the module-level
       ``recipe_layout``.
    3. **Stream start** — sends ``CONTROL_PACKAGE_START``; raises
       ``RuntimeError`` if rejected.

    Args:
        sock (socket.socket): Connected TCP socket to the RTDE port
            (``UR_IP:RTDE_PORT``).

    Raises:
        RuntimeError: If protocol version 2 is rejected, if no variables are
            supported, or if streaming cannot be started.
    """
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
    """Deserialise a binary RTDE DATA_PACKAGE into a dict of variable values.

    Walks the module-level ``recipe_layout`` in order, consuming the correct
    number of bytes for each type (``VECTOR6D`` = 48, ``DOUBLE`` = 8,
    ``INT32``/``UINT32`` = 4).  Variables whose type is ``NOT_FOUND`` are
    absent from the binary payload and are mapped to ``None`` without
    advancing the offset.  On a ``struct.error`` mid-packet the remaining
    variables are also set to ``None`` and parsing stops.

    Args:
        payload (bytes): Raw payload bytes from an RTDE ``DATA_PACKAGE``
            frame, including the leading recipe-ID byte.

    Returns:
        dict[str, Any]: Mapping of variable name to parsed value.  Numeric
            scalars are Python ``int`` or ``float``; ``VECTOR6D`` entries are
            6-element lists of floats; ``NOT_FOUND`` entries are ``None``.
    """
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
    """Convert a parsed RTDE data dict to the JSON structure expected by the dashboard.

    Derives a human-readable robot status (``"running"`` / ``"idle"`` /
    ``"alarm"`` / ``"offline"``) from ``robot_mode``, ``safety_mode``, and
    ``runtime_state``.  Builds an alarm list from elevated safety modes.
    Converts TCP pose from metres/radians to millimetres/degrees, computes
    TCP speed magnitude (mm/s), maps joint currents to approximate torques
    (A × 3.0 Nm/A), and estimates total power from bus voltage and current.

    Args:
        rtde_data (dict): Output of :func:`parse_data_package` — a dict of
            RTDE variable names to values.  Missing keys are treated as zero
            or their safe defaults.
        program_name (str): Name of the currently loaded ``.urp`` program,
            obtained via :func:`get_program_name`.  Defaults to ``"—"``.

    Returns:
        dict: JSON-serialisable dashboard payload with keys including
            ``machine``, ``status``, ``program``, ``robotMode``,
            ``safetyMode``, ``tcpPosition``, ``tcpSpeed``, ``speedFraction``,
            ``joints``, ``powerKw``, ``voltage``, ``current``, ``alarms``,
            and ``digitalOutputs``.
    """
    robot_mode = rtde_data.get("robot_mode") or -1
    safety_mode = rtde_data.get("safety_mode") or 1
    runtime = rtde_data.get("runtime_state") or 0

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
        alarms.append(
            f"SAFETY FAULT: {SAFETY_MODE_NAMES.get(safety_mode, safety_mode)}"
        )

    # TCP
    tcp = rtde_data.get("actual_TCP_pose") or [0] * 6
    tcp_speed_vec = rtde_data.get("actual_TCP_speed") or [0] * 6
    tcp_speed = round(math.sqrt(sum(v**2 for v in tcp_speed_vec[:3])) * 1000, 1)

    # Joints
    joints_q = rtde_data.get("actual_q") or [0] * 6
    joints_qd = rtde_data.get("actual_qd") or [0] * 6
    joints_cur = rtde_data.get("actual_current") or [0] * 6

    joints = [
        {
            "id": f"J{i + 1}",
            "label": JOINT_LABELS[i],
            "angle": round(math.degrees(joints_q[i]), 2)
            if joints_q[i] is not None
            else 0,
            "speed": round(math.degrees(joints_qd[i]), 2)
            if joints_qd[i] is not None
            else 0,
            "torque": round(abs(joints_cur[i]) * 3.0, 1)
            if joints_cur[i] is not None
            else 0,
        }
        for i in range(6)
    ]

    voltage = rtde_data.get("actual_robot_voltage") or 0.0
    current = rtde_data.get("actual_robot_current") or 0.0

    return {
        "machine": "ur5e",
        "name": "UR5e Cobot",
        "type": "Collaborative Robot Arm",
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "program": program_name,
        "robotMode": ROBOT_MODE_NAMES.get(robot_mode, str(robot_mode)),
        "safetyMode": SAFETY_MODE_NAMES.get(safety_mode, str(safety_mode)),
        "runtimeState": [
            "STOPPED",
            "STOPPED",
            "PLAYING",
            "PAUSING",
            "PAUSED",
            "RESUMING",
        ][min(runtime, 5)]
        if isinstance(runtime, int)
        else "STOPPED",
        "tcpPosition": {
            "x": round(tcp[0] * 1000, 2),
            "y": round(tcp[1] * 1000, 2),
            "z": round(tcp[2] * 1000, 2),
            "rx": round(math.degrees(tcp[3]), 2),
            "ry": round(math.degrees(tcp[4]), 2),
            "rz": round(math.degrees(tcp[5]), 2),
        },
        "tcpSpeed": tcp_speed,
        "speedFraction": round(
            (rtde_data.get("target_speed_fraction") or 0.0) * 100, 1
        ),
        "joints": joints,
        "powerKw": round(voltage * current / 1000.0, 3),
        "voltage": round(voltage, 1),
        "current": round(current, 2),
        "alarms": alarms,
        "digitalOutputs": rtde_data.get("output_bit_registers0_to_31") or 0,
    }


# ── Dashboard Server query ───────────────────────────────────────


def get_program_name() -> str:
    """Query the Dashboard Server for the currently loaded program name.

    Connects to ``UR_IP:DASHBOARD_PORT``, sends ``"get loaded program"``,
    and parses the colon-separated response to extract the bare filename
    (without the full path or ``.urp`` extension path prefix).

    Returns:
        str: The loaded program filename, or ``"—"`` if the query fails or
            no program is loaded.
    """
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
    """Parse and dispatch a robot-control action received from a WebSocket client.

    Runs blocking Dashboard Server and URScript calls in the thread-pool
    executor so the asyncio event loop is not blocked.  Supported actions:

    * ``"play"`` / ``"stop"`` / ``"pause"`` — forwarded directly to the
      Dashboard Server via :func:`dashboard_cmd`.
    * ``"home"`` — uploads ``HOME_SCRIPT`` via :func:`send_urscript`.
    * ``"load"`` — loads a ``.urp`` program by name from ``/programs/``.

    Args:
        cmd (dict): Parsed JSON object from the WebSocket client.  Must
            contain an ``"action"`` key.  The ``"load"`` action also reads
            a ``"program"`` key for the program filename.

    Returns:
        str: A short result/status string suitable for echoing back to the
            client as an acknowledgement.
    """
    loop = asyncio.get_event_loop()
    action = cmd.get("action", "")
    if action in ("play", "stop", "pause"):
        return await loop.run_in_executor(executor, dashboard_cmd, action)
    elif action == "home":
        await loop.run_in_executor(executor, send_urscript, HOME_SCRIPT)
        return "moving to home"
    elif action == "load":
        prog = cmd.get("program", "")
        return await loop.run_in_executor(
            executor, dashboard_cmd, f"load /programs/{prog}.urp"
        )
    return f"unknown action: {action}"


async def ws_handler(ws):
    """Manage the lifecycle of a single WebSocket client connection.

    Registers the client, sends the last-known payload immediately so the
    dashboard is populated on connect, then forwards each inbound JSON
    message to :func:`handle_ws_command` and echoes the result back as an
    ``{"ack": action, "result": ...}`` JSON object.  The client is removed
    from ``connected_clients`` on disconnect, whether clean or abrupt.

    Args:
        ws: The WebSocket connection object provided by the ``websockets``
            server library.
    """
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
    """Update the cached latest state and push *payload* to all connected WebSocket clients.

    Stores *payload* in the module-level ``latest_payload`` so new connections
    receive it immediately, then concurrently sends a JSON-serialised copy to
    every entry in ``connected_clients``.  Uses ``asyncio.gather`` with
    ``return_exceptions=True`` so that one closed or stale connection does not
    prevent delivery to the others.

    Args:
        payload (dict): JSON-serialisable dict to broadcast (typically the
            output of :func:`build_dashboard_payload`).
    """
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
    """Main RTDE polling loop: connect, set up the stream, and broadcast telemetry.

    Establishes a TCP connection to ``UR_IP:RTDE_PORT``, calls
    :func:`rtde_setup` to negotiate protocol and subscribe to
    ``RTDE_VARIABLES``, then continuously reads ``DATA_PACKAGE`` frames,
    parses them with :func:`parse_data_package`, and broadcasts the result
    via :func:`broadcast`.  The program name is refreshed every 50 frames
    (~5 s at 10 Hz) via a background executor call to avoid blocking the
    event loop.  On any connection or parsing error the loop waits
    ``RECONNECT_WAIT`` seconds before retrying from scratch.
    """
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
            await broadcast(
                {"machine": "ur5e", "status": "offline", "alarms": [str(e)]}
            )
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
        await asyncio.sleep(RECONNECT_WAIT)


# ── Flask Siri/HTTP bridge ────────────────────────────────────────


def make_flask_app():
    """Create and return a Flask application exposing Siri / REST robot-control endpoints.

    All mutating routes (``/play``, ``/stop``, ``/pause``, ``/home``,
    ``/load/<program_name>``) require the ``X-API-Key`` header to equal
    ``API_KEY``; the ``/status`` GET route is unauthenticated.

    Route inner functions:

    * **check_key()** — aborts with HTTP 401 if the API-key header is absent
      or wrong.
    * **play()** / **stop()** / **pause()** — POST; forward the matching
      Dashboard Server command and return a JSON status + timestamp.
    * **home()** — POST; uploads ``HOME_SCRIPT`` via :func:`send_urscript`
      to move the robot to the home configuration.
    * **load(program_name)** — POST; loads the named ``.urp`` program from
      the controller's ``/programs/`` directory.
    * **status()** — GET; returns the most recent ``latest_payload`` without
      requiring authentication.

    Returns:
        Flask | None: A configured Flask app instance, or ``None`` if Flask
            is not installed.
    """
    try:
        from flask import Flask, abort, jsonify, request
    except ImportError:
        log.warning(
            "Flask not installed — Siri HTTP bridge disabled.  Run: pip install flask"
        )
        return None

    app = Flask(__name__)

    def check_key():
        if request.headers.get("X-API-Key") != API_KEY:
            abort(401)

    @app.route("/play", methods=["POST"])
    def play():
        check_key()
        return jsonify(
            {"status": dashboard_cmd("play"), "timestamp": datetime.now().isoformat()}
        )

    @app.route("/stop", methods=["POST"])
    def stop():
        check_key()
        return jsonify(
            {"status": dashboard_cmd("stop"), "timestamp": datetime.now().isoformat()}
        )

    @app.route("/pause", methods=["POST"])
    def pause():
        check_key()
        return jsonify(
            {"status": dashboard_cmd("pause"), "timestamp": datetime.now().isoformat()}
        )

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
    """Async entry point: start the Flask HTTP server, WebSocket server, and RTDE poll loop.

    1. Calls :func:`make_flask_app` and, if Flask is available, starts it in
       a background daemon thread bound to ``0.0.0.0:HTTP_PORT``.
    2. Binds a ``websockets`` server on ``WS_HOST:WS_PORT`` (falls back to
       the legacy ``websockets.serve`` API if the newer
       ``websockets.asyncio.server.serve`` is not available).
    3. Runs :func:`ur5e_poll_loop` indefinitely inside the same event loop.
    """
    log.info(f"UR5e bridge starting")
    log.info(f"  Robot:     {UR_IP}:{RTDE_PORT}")
    log.info(f"  WebSocket: ws://0.0.0.0:{WS_PORT}")
    log.info(f"  Siri HTTP: http://0.0.0.0:{HTTP_PORT}")

    # Start Flask in a background daemon thread
    flask_app = make_flask_app()
    if flask_app:
        threading.Thread(
            target=lambda: flask_app.run(
                host="0.0.0.0", port=HTTP_PORT, debug=False, threaded=True
            ),
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
