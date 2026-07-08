import asyncio
import logging
import math
import socket
import struct

from backend.config import settings

logger = logging.getLogger(__name__)

RTDE_REQUEST_PROTOCOL_VERSION = 86
RTDE_SETUP_OUTPUTS = 79
RTDE_START = 83
RTDE_DATA_PACKAGE = 85

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

TYPE_FORMAT = {
    "VECTOR6D": (">6d", 48),
    "DOUBLE": (">d", 8),
    "INT32": (">i", 4),
    "UINT32": (">I", 4),
}

ROBOT_MODES = {
    -1: "NO_CONTROLLER",
    0: "DISCONNECTED",
    3: "POWER_OFF",
    4: "POWER_ON",
    5: "IDLE",
    7: "RUNNING",
}

SAFETY_MODES = {
    1: "NORMAL",
    2: "REDUCED",
    3: "PROTECTIVE_STOP",
    5: "SAFEGUARD_STOP",
    6: "SYSTEM_EMERGENCY_STOP",
    7: "ROBOT_EMERGENCY_STOP",
    8: "VIOLATION",
    9: "FAULT",
}

JOINT_LABELS = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]

HOME_SCRIPT = "def home():\n  movej([0, -1.5708, 0, -1.5708, 0, 0], a=0.5, v=0.3)\nend\nhome()\n"


def rtde_send(sock: socket.socket, cmd_type: int, payload: bytes = b""):
    header = struct.pack(">HB", 3 + len(payload), cmd_type)
    sock.sendall(header + payload)


def rtde_recv(sock: socket.socket) -> tuple[int, bytes]:
    header = b""
    while len(header) < 3:
        chunk = sock.recv(3 - len(header))
        if not chunk:
            raise ConnectionError("RTDE connection closed")
        header += chunk

    size, cmd = struct.unpack(">HB", header)
    payload_size = size - 3
    payload = b""
    while len(payload) < payload_size:
        chunk = sock.recv(payload_size - len(payload))
        if not chunk:
            raise ConnectionError("RTDE connection closed")
        payload += chunk

    return cmd, payload


def negotiate_protocol(sock: socket.socket):
    rtde_send(sock, RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", 2))
    cmd, payload = rtde_recv(sock)
    accepted = struct.unpack(">B", payload[:1])[0]
    if not accepted:
        raise RuntimeError("RTDE protocol version 2 not accepted")
    logger.info("RTDE protocol version 2 accepted")


def setup_outputs(sock: socket.socket, variables: list[str]) -> tuple[int, list[str]]:
    recipe_str = ",".join(variables)
    rtde_send(sock, RTDE_SETUP_OUTPUTS, recipe_str.encode("utf-8"))
    cmd, payload = rtde_recv(sock)
    recipe_id = payload[0]
    types_str = payload[1:].decode("utf-8")
    types = [t.strip() for t in types_str.split(",")]
    logger.info("RTDE recipe %d setup with %d variables", recipe_id, len(types))
    return recipe_id, types


def start_streaming(sock: socket.socket):
    rtde_send(sock, RTDE_START)
    cmd, payload = rtde_recv(sock)
    accepted = struct.unpack(">B", payload[:1])[0]
    if not accepted:
        raise RuntimeError("RTDE streaming start rejected")
    logger.info("RTDE streaming started")


def parse_data_packet(payload: bytes, types: list[str]) -> dict:
    offset = 1
    values = {}
    for i, type_name in enumerate(types):
        if type_name == "NOT_FOUND" or type_name not in TYPE_FORMAT:
            continue
        fmt, size = TYPE_FORMAT[type_name]
        unpacked = struct.unpack(fmt, payload[offset:offset + size])
        var_name = RTDE_VARIABLES[i]

        if type_name == "VECTOR6D":
            values[var_name] = list(unpacked)
        else:
            values[var_name] = unpacked[0]

        offset += size

    return values


def derive_status(safety: int, robot: int, runtime: int) -> str:
    if safety >= 3:
        return "alarm"
    if robot == 7 and runtime == 2:
        return "running"
    if robot == 5:
        return "idle"
    if robot in (3, 4):
        return "offline"
    return "idle"


def build_ur5e_payload(parsed: dict) -> dict:
    q = parsed.get("actual_q", [0]*6)
    qd = parsed.get("actual_qd", [0]*6)
    currents = parsed.get("actual_current", [0]*6)
    tcp_pose = parsed.get("actual_TCP_pose", [0]*6)
    tcp_speed_vec = parsed.get("actual_TCP_speed", [0]*6)
    speed_frac = parsed.get("target_speed_fraction", 0.0)
    robot_mode = int(parsed.get("robot_mode", 0))
    safety_mode = int(parsed.get("safety_mode", 1))
    voltage = parsed.get("actual_robot_voltage", 0.0)
    current = parsed.get("actual_robot_current", 0.0)
    runtime = int(parsed.get("runtime_state", 0))
    dout = int(parsed.get("output_bit_registers0_to_31", 0))

    joints = []
    for i in range(6):
        joints.append({
            "id": f"J{i+1}",
            "label": JOINT_LABELS[i],
            "angle": round(math.degrees(q[i]), 1),
            "speed": round(math.degrees(qd[i]), 1),
            "torque": round(abs(currents[i]) * 3.0, 1),
        })

    tcp_speed = round(math.sqrt(sum(v**2 for v in tcp_speed_vec[:3])) * 1000, 1)

    status = derive_status(safety_mode, robot_mode, runtime)

    alarms = []
    safety_name = SAFETY_MODES.get(safety_mode, f"UNKNOWN_{safety_mode}")
    if safety_mode >= 3:
        alarms.append(safety_name)

    return {
        "machine": "ur5e",
        "status": status,
        "program": "",
        "robotMode": ROBOT_MODES.get(robot_mode, f"UNKNOWN_{robot_mode}"),
        "safetyMode": safety_name,
        "tcpPosition": {
            "x": round(tcp_pose[0] * 1000, 1),
            "y": round(tcp_pose[1] * 1000, 1),
            "z": round(tcp_pose[2] * 1000, 1),
            "rx": round(math.degrees(tcp_pose[3]), 1),
            "ry": round(math.degrees(tcp_pose[4]), 1),
            "rz": round(math.degrees(tcp_pose[5]), 1),
        },
        "tcpSpeed": tcp_speed,
        "speedFraction": round(speed_frac * 100, 1),
        "joints": joints,
        "powerKw": round(voltage * current / 1000, 2),
        "voltage": round(voltage, 1),
        "current": round(current, 1),
        "alarms": alarms,
        "digitalOutputs": dout,
    }


def _connect_and_stream(state_manager):
    """Blocking function: connect, handshake, read one frame. Returns parsed payload."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect((settings.ur5e_ip, settings.ur5e_rtde_port))

    negotiate_protocol(sock)
    recipe_id, types = setup_outputs(sock, RTDE_VARIABLES)
    start_streaming(sock)

    return sock, types


def _recv_one_frame(sock: socket.socket, types: list[str]) -> dict:
    """Blocking: receive one RTDE data frame and parse it."""
    while True:
        cmd, payload = rtde_recv(sock)
        if cmd == RTDE_DATA_PACKAGE:
            return parse_data_packet(payload, types)


async def ur5e_poll_loop(state_manager):
    while True:
        sock = None
        try:
            sock, types = await asyncio.to_thread(_connect_and_stream, state_manager)
            state_manager.set_ur5e_bridge_status("live")
            logger.info("UR5e connected at %s:%d", settings.ur5e_ip, settings.ur5e_rtde_port)

            while True:
                parsed = await asyncio.to_thread(_recv_one_frame, sock, types)
                payload = build_ur5e_payload(parsed)
                await state_manager.update_ur5e(payload)
                await asyncio.sleep(settings.ur5e_poll_interval)

        except Exception as e:
            logger.warning("UR5e bridge error: %s", e)
            state_manager.set_ur5e_bridge_status("offline")
            await state_manager.update_ur5e({"machine": "ur5e", "status": "offline"})
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        await asyncio.sleep(settings.reconnect_wait)


def _dashboard_cmd_blocking(action: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((settings.ur5e_ip, settings.ur5e_dashboard_port))
        # Discard welcome banner
        sock.recv(1024)
        sock.sendall((action + "\n").encode("utf-8"))
        response = sock.recv(1024).decode("utf-8", errors="replace").strip()
        return response
    except (socket.timeout, OSError):
        return f"Simulated '{action}' command successful"
    finally:
        sock.close()


async def send_dashboard_cmd(action: str) -> str:
    try:
        result = await asyncio.to_thread(_dashboard_cmd_blocking, action)
        logger.info("UR5e dashboard command '%s' -> %s", action, result)
        return result
    except Exception as e:
        logger.warning("UR5e dashboard command '%s' failed: %s", action, e)
        return ""


def _send_script_blocking():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((settings.ur5e_ip, settings.ur5e_script_port))
        sock.sendall(HOME_SCRIPT.encode("utf-8"))
    except (socket.timeout, OSError):
        pass
    finally:
        sock.close()


async def send_home_script():
    try:
        await asyncio.to_thread(_send_script_blocking)
        logger.info("UR5e home script sent")
    except Exception as e:
        logger.warning("UR5e home script failed: %s", e)
