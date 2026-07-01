#!/usr/bin/env python3
"""
ur5e_dashboard.py — Unified UR5e Dashboard, Pipeline, Control & Digital Twin
================================================================================

A single Python application that provides:

1.  Full RTDE Data Pipeline — streams all telemetry from the UR5e at high frequency
2.  Persistent Logging — CSV + JSONL logging of the complete data stream
3.  Web Dashboard — rich interactive UI with Plotly charts (NiceGUI framework)
4.  Robot Control — jog, move, I/O, freedrive, program control from the browser
5.  RealSense L515 — MJPEG camera stream embedded in a Digital Twin tab
6.  Digital Twin Viewport — placeholder for Omniverse / VR stream embed

Architecture:

    ┌─────────────┐                    ┌───────────────────────┐
    │  Browser    │  ◄── NiceGUI ───►  │  ur5e_dashboard.py    │
    │  (any)      │   WebSocket/HTTP   │     (this file)       │
    └─────────────┘                    │                       │
                                       │  ┌─ RTDE Pipeline     │     ┌───────┐
                                       │  ├─ Command Dispatch  │◄───►│ UR5e  │
                                       │  ├─ CSV/JSONL Logger  │     └───────┘
                                       │  ├─ Plotly Dashboard  │
                                       │  └─ RealSense Stream  │     ┌───────┐
                                       │                       │◄───►│ L515  │
                                       └───────────────────────┘     └───────┘

Usage:
    python3 ur5e_dashboard.py --ip 192.168.1.15 --rate 10

Dependencies:
    pip install nicegui plotly websockets

    Optional (robot):   pip install ur-rtde
    Optional (camera):  pip install pyrealsense2 opencv-python

Version : 6.2 — Patched: fixed _log_event infinite recursion, removed
                RTDEControlInterface reads from telemetry loop to prevent
                thread-safety crashes during concurrent control commands.
                Torque sourced from getActualCurrentAsTorque (receive interface).
"""

# ══════════════════════════════════════════════════════════════════════════════
#  STANDARD LIBRARY
# ══════════════════════════════════════════════════════════════════════════════

import argparse
import asyncio
import csv
import io
import json
import logging
import math
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ══════════════════════════════════════════════════════════════════════════════
#  THIRD-PARTY — REQUIRED
# ══════════════════════════════════════════════════════════════════════════════

try:
    from nicegui import ui, app, run
except ImportError:
    print("ERROR: nicegui not installed. Run: pip install nicegui")
    sys.exit(1)

try:
    import plotly.graph_objects as go
except ImportError:
    print("ERROR: plotly not installed. Run: pip install plotly")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  THIRD-PARTY — OPTIONAL
# ══════════════════════════════════════════════════════════════════════════════

try:
    import rtde_control
    import rtde_io
    import rtde_receive
    import dashboard_client
    HAS_RTDE = True
except ImportError:
    HAS_RTDE = False

try:
    import pyrealsense2 as rs
    import cv2
    import numpy as np
    HAS_REALSENSE = True
except ImportError:
    HAS_REALSENSE = False

try:
    from openvino.runtime import Core as OVCore
    HAS_OPENVINO = True
except ImportError:
    HAS_OPENVINO = False

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ur5e_dashboard")

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

JOINT_NAMES   = ["base", "shoulder", "elbow", "wrist1", "wrist2", "wrist3"]
JOINT_LABELS  = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
CART_AXES     = ["x", "y", "z", "rx", "ry", "rz"]
FORCE_AXES    = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]
MAX_TORQUES   = [150, 150, 75, 28, 28, 28]

J_COLORS      = ["#00D4AA", "#00B4D8", "#4895EF", "#7B61FF", "#F472B6", "#FBBF24"]
F_COLORS      = {"Fx": "#FF6B6B", "Fy": "#EE5A24", "Fz": "#F8B739",
                 "Mx": "#A29BFE", "My": "#6C5CE7", "Mz": "#B8E994"}

DIGITAL_INPUT_LABELS = (
    [f"std_din_{i}" for i in range(8)] +
    [f"cfg_din_{i}" for i in range(8)] +
    ["tool_din_0", "tool_din_1"]
)
DIGITAL_OUTPUT_LABELS = (
    [f"std_dout_{i}" for i in range(8)] +
    [f"cfg_dout_{i}" for i in range(8)] +
    ["tool_dout_0", "tool_dout_1"]
)

ROBOT_MODE_MAP = {
    0: "DISCONNECTED",  1: "CONFIRM_SAFETY",  2: "BOOTING",
    3: "POWER_OFF",     4: "POWER_ON",        5: "IDLE",
    6: "BACKDRIVE",     7: "RUNNING",         8: "UPDATING",
    9: "POWERING_OFF",  10: "ARM_BOOTING",    11: "ARM_UPDATING",
}
SAFETY_MODE_MAP = {
    1: "NORMAL",        2: "REDUCED",         3: "PROTECTIVE_STOP",
    4: "RECOVERY",      5: "SAFEGUARD_STOP",  6: "SYS_EMERGENCY_STOP",
    7: "ROBOT_EMERGENCY_STOP", 8: "VIOLATION", 9: "FAULT",
}
SAFETY_STATUS_MAP = {
    1: "NORMAL",                    2: "REDUCED",
    3: "PROTECTIVE_STOP",           4: "RECOVERY",
    5: "SAFEGUARD_STOP",            6: "SYSTEM_EMERGENCY_STOP",
    7: "ROBOT_EMERGENCY_STOP",      8: "VIOLATION",
    9: "FAULT",                     12: "AUTOMATIC_MODE_SAFEGUARD_STOP",
    13: "SYSTEM_THREE_POSITION_ENABLING_STOP",
    14: "TP_THREE_POSITION_ENABLING_STOP",
    15: "IMMI_EMERGENCY_STOP",      16: "IMMI_SAFEGUARD_STOP",
    17: "PROFISAFE_WAITING_FOR_PARAMETERS",
    18: "PROFISAFE_AUTOMATIC_MODE_SAFEGUARD_STOP",
    19: "PROFISAFE_SAFEGUARD_STOP", 20: "PROFISAFE_EMERGENCY_STOP",
    22: "SAFETY_API_SAFEGUARD_STOP",
}
TIME_SCALE_SOURCE_MAP = {
    -1: "OTHER",                0: "NOT_RUNNING",
    1:  "NOT_SCALED",           2: "JOINT_TORQUE_LIMIT",
    3:  "JOINT_ACCEL_LIMIT",    4: "POWER_SUPPLY_LIMIT",
    5:  "MOMENTUM_LIMIT",       6: "STOPPING_TIME_LIMIT",
    7:  "STOPPING_DIST_LIMIT",  8: "TOOL_SPEED_LIMIT",
    9:  "ELBOW_SPEED_LIMIT",    10: "JOINT_SPEED_LIMIT",
    11: "SMOOTH_SAFETY_TRANS",  12: "STOP_DIST_SAFETY_API",
    13: "TOOL_WRENCH_LIMIT",    14: "EXT_AXIS_SPEED_LIMIT",
    15: "EXT_AXIS_STOPPING",
}
RUNTIME_STATE_MAP = {
    0: "STOPPING", 1: "STOPPED", 2: "RUNNING",
    3: "PAUSING",  4: "PAUSED",  5: "RESUMING",
}
SAFETY_BIT_LABELS = [
    "normal_mode", "reduced_mode", "protective_stopped", "recovery_mode",
    "safeguard_stopped", "sys_emergency_stopped", "robot_emergency_stopped",
    "emergency_stopped", "violation", "fault", "stopped_due_to_safety",
    "3pe_input_active",
]
ROBOT_BIT_LABELS = [
    "power_on", "program_running", "teach_button_pressed", "power_button_pressed",
]

HISTORY_LEN = 200
CHART_LEN   = 60   # number of samples to plot — keep low to reduce browser render cost

# ══════════════════════════════════════════════════════════════════════════════
#  ROBOT GEOMETRY — UR5e DH PARAMETERS + CAMERA → ROBOT TRANSFORM
# ══════════════════════════════════════════════════════════════════════════════
# Source: Universal Robots DH parameters for UR5e
# https://www.universal-robots.com/articles/ur/application-installation/dh-parameters-for-calculations-of-kinematics-and-dynamics/
UR5E_DH = [
    # (a,        alpha,    d,       theta_offset)
    (0.0,        math.pi/2, 0.1625,  0.0),        # base → shoulder
    (-0.425,     0.0,       0.0,     0.0),        # shoulder → elbow
    (-0.3922,    0.0,       0.0,     0.0),        # elbow → wrist1
    (0.0,        math.pi/2, 0.1333,  0.0),        # wrist1 → wrist2
    (0.0,       -math.pi/2, 0.0997,  0.0),        # wrist2 → wrist3
    (0.0,        0.0,       0.0996,  0.0),        # wrist3 → TCP flange
]

# ── CAMERA POSE IN ROBOT BASE FRAME ──
# Manual transform (Option A) — tune these for your actual setup.
# Frame convention: robot base is at origin, +X forward, +Y left, +Z up.
# Camera is mounted on a wall ~3.8 m in front of the robot, ~1.5 m high,
# aimed down and slightly toward the workcell.
#
# Camera optical frame convention: +X right, +Y down, +Z forward (into scene).
# So if the camera is aimed from the wall toward the robot, its +Z points
# in the robot's -X direction.
CAMERA_POS_IN_BASE     = (3.8, 0.0, 1.5)    # (x, y, z) meters in robot base frame
CAMERA_LOOK_AT_IN_BASE = (0.0, 0.0, 0.3)    # point the camera is aimed at (table/robot center)
CAMERA_ROLL_DEG        = 0.0                # roll around optical axis

HISTORY_LEN_KIN = 200  # unused but kept for clarity


def _mat_mul(A, B):
    """4x4 matrix multiplication without numpy."""
    R = [[0.0]*4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            R[i][j] = sum(A[i][k] * B[k][j] for k in range(4))
    return R


def _dh_transform(a, alpha, d, theta):
    """Build a 4x4 DH transform for one link."""
    ct, st = math.cos(theta), math.sin(theta)
    ca, sa = math.cos(alpha), math.sin(alpha)
    return [
        [ct,    -st*ca,  st*sa,   a*ct],
        [st,     ct*ca, -ct*sa,   a*st],
        [0.0,    sa,     ca,      d],
        [0.0,    0.0,    0.0,     1.0],
    ]


def forward_kinematics_ur5e(q):
    """Return list of 7 (x, y, z) points in robot base frame:
    [base, shoulder, elbow, wrist1, wrist2, wrist3, tcp_flange].
    q: list of 6 joint angles in radians.
    """
    if q is None or len(q) != 6:
        # Fallback: all joints at origin
        return [(0.0, 0.0, 0.0)] * 7

    T = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    points = [(T[0][3], T[1][3], T[2][3])]  # base at origin

    for i, (a, alpha, d, theta_offset) in enumerate(UR5E_DH):
        Ti = _dh_transform(a, alpha, d, q[i] + theta_offset)
        T = _mat_mul(T, Ti)
        points.append((T[0][3], T[1][3], T[2][3]))

    return points


def _point_to_segment_distance(p, a, b):
    """Distance from point p to line segment ab (all 3D tuples)."""
    ax, ay, az = a
    bx, by, bz = b
    px, py, pz = p
    dx, dy, dz = bx - ax, by - ay, bz - az
    seg_len_sq = dx*dx + dy*dy + dz*dz
    if seg_len_sq < 1e-9:
        ex, ey, ez = px - ax, py - ay, pz - az
        return math.sqrt(ex*ex + ey*ey + ez*ez)
    t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / seg_len_sq
    t = max(0.0, min(1.0, t))
    cx, cy, cz = ax + t*dx, ay + t*dy, az + t*dz
    ex, ey, ez = px - cx, py - cy, pz - cz
    return math.sqrt(ex*ex + ey*ey + ez*ez)


def nearest_link_distance(person_xyz_base, joint_points):
    """Minimum distance from a point to any robot link segment.
    person_xyz_base: (x, y, z) in robot base frame.
    joint_points: list of 7 (x, y, z) points from forward_kinematics_ur5e.
    Returns (min_distance, index_of_nearest_link).
    """
    min_d = float("inf")
    min_i = -1
    for i in range(len(joint_points) - 1):
        d = _point_to_segment_distance(person_xyz_base, joint_points[i], joint_points[i+1])
        if d < min_d:
            min_d = d
            min_i = i
    return min_d, min_i


def _build_camera_to_base_transform(cam_pos, look_at, roll_deg=0.0):
    """Build a 4x4 transform from camera optical frame to robot base frame.

    Camera optical: +X right, +Y down, +Z forward.
    Robot base: +X forward, +Y left, +Z up.

    The camera is positioned at cam_pos and aimed at look_at, both in base frame.
    """
    # Camera +Z direction (from camera toward scene) in base frame
    fx = look_at[0] - cam_pos[0]
    fy = look_at[1] - cam_pos[1]
    fz = look_at[2] - cam_pos[2]
    fn = math.sqrt(fx*fx + fy*fy + fz*fz)
    if fn < 1e-9:
        fx, fy, fz = 1.0, 0.0, 0.0
        fn = 1.0
    zx, zy, zz = fx/fn, fy/fn, fz/fn

    # Camera +Y (down in image) — project world -Z onto plane perp to Z axis
    wx, wy, wz = 0.0, 0.0, -1.0
    dot = wx*zx + wy*zy + wz*zz
    yx, yy, yz = wx - dot*zx, wy - dot*zy, wz - dot*zz
    yn = math.sqrt(yx*yx + yy*yy + yz*yz)
    if yn < 1e-9:
        # Camera looking straight up or down — pick arbitrary Y
        yx, yy, yz = 0.0, 1.0, 0.0
        yn = 1.0
    yx, yy, yz = yx/yn, yy/yn, yz/yn

    # Camera +X = Y cross Z
    xx = yy*zz - yz*zy
    xy = yz*zx - yx*zz
    xz = yx*zy - yy*zx

    # Apply roll around optical axis (Z)
    if abs(roll_deg) > 1e-6:
        cr, sr = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))
        nxx, nxy, nxz = xx*cr + yx*sr, xy*cr + yy*sr, xz*cr + yz*sr
        nyx, nyy, nyz = -xx*sr + yx*cr, -xy*sr + yy*cr, -xz*sr + yz*cr
        xx, xy, xz = nxx, nxy, nxz
        yx, yy, yz = nyx, nyy, nyz

    return [
        [xx, yx, zx, cam_pos[0]],
        [xy, yy, zy, cam_pos[1]],
        [xz, yz, zz, cam_pos[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


# Precompute the transform at startup (fixed mount, never changes)
T_CAMERA_TO_BASE = _build_camera_to_base_transform(
    CAMERA_POS_IN_BASE, CAMERA_LOOK_AT_IN_BASE, CAMERA_ROLL_DEG
)


def camera_pixel_to_base(px, py, depth_m, intrinsics):
    """Convert a pixel + depth from the camera into a point in the robot base frame.

    intrinsics: dict with fx, fy, cx, cy (RealSense color intrinsics).
    Returns (x, y, z) in robot base frame, or None if depth invalid.
    """
    if depth_m is None or depth_m <= 0 or depth_m > 10:
        return None
    fx = intrinsics.get("fx", 600.0)
    fy = intrinsics.get("fy", 600.0)
    cx = intrinsics.get("cx", 320.0)
    cy = intrinsics.get("cy", 240.0)
    # Camera frame: +X right, +Y down, +Z forward
    X = (px - cx) * depth_m / fx
    Y = (py - cy) * depth_m / fy
    Z = depth_m
    # Apply camera → base transform
    T = T_CAMERA_TO_BASE
    xb = T[0][0]*X + T[0][1]*Y + T[0][2]*Z + T[0][3]
    yb = T[1][0]*X + T[1][1]*Y + T[1][2]*Z + T[1][3]
    zb = T[2][0]*X + T[2][1]*Y + T[2][2]*Z + T[2][3]
    return (xb, yb, zb)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def safe_get(obj, method_name, fallback=None):
    fn = getattr(obj, method_name, None)
    if fn is None:
        return fallback
    try:
        return fn()
    except Exception:
        return fallback

def unpack_bits(bitmask, labels):
    if bitmask is None:
        return {lbl: None for lbl in labels}
    return {lbl: int((bitmask >> i) & 1) for i, lbl in enumerate(labels)}

def vec_to_dict(vec, keys):
    if vec is None:
        return {k: None for k in keys}
    return {k: round(float(v), 6) for k, v in zip(keys, vec)}

def scalar(v, n=6):
    return round(float(v), n) if v is not None else None

def flatten_dict(d, parent_key="", sep="__"):
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items

# ══════════════════════════════════════════════════════════════════════════════
#  ROBOT INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

class RobotInterface:
    """Wraps all ur_rtde interfaces for telemetry and control."""

    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        self.rtde_r = None
        self.rtde_c = None
        self.rtde_io_iface = None
        self.dash = None
        self.connected = False

    def connect(self):
        if not HAS_RTDE:
            log.warning("ur_rtde not installed — DEMO mode")
            return False
        log.info(f"Connecting to UR5e at {self.robot_ip} ...")
        try:
            self.rtde_r = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            log.info("  RTDEReceiveInterface connected")
            self.rtde_c = rtde_control.RTDEControlInterface(self.robot_ip)
            log.info("  RTDEControlInterface connected")
            self.rtde_io_iface = rtde_io.RTDEIOInterface(self.robot_ip)
            log.info("  RTDEIOInterface connected")
            self.dash = dashboard_client.DashboardClient(self.robot_ip)
            self.dash.connect()
            log.info("  DashboardClient connected")
            self.connected = True
            return True
        except Exception as e:
            log.error(f"Connection failed: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        if self.rtde_c and self.rtde_c.isConnected():
            self.rtde_c.stopScript()
        if self.rtde_r and self.rtde_r.isConnected():
            self.rtde_r.disconnect()
        if self.rtde_c and self.rtde_c.isConnected():
            self.rtde_c.disconnect()
        if self.rtde_io_iface and self.rtde_io_iface.isConnected():
            self.rtde_io_iface.disconnect()
        if self.dash and self.dash.isConnected():
            self.dash.disconnect()
        self.connected = False
        log.info("All interfaces disconnected.")

    def collect_sample(self, elapsed: float, idx: int) -> Dict:
        """Collect RTDE output variables using only the real ur_rtde API surface.

        Methods called are verified against the ur_rtde 1.6.3 API reference at
        https://sdurobotics.gitlab.io/ur_rtde/api/api.html

        Fields that are not exposed by ur_rtde (elbow position, encoders,
        euromap, tool I/O modes, collision ratio, etc.) are set to None.
        These RTDE variables exist in the underlying protocol but the Python
        wrapper does not expose getters for them.
        """
        if not self.connected or self.rtde_r is None:
            return {}
        con = self.rtde_r
        # NOTE: We do NOT read from rtde_c (RTDEControlInterface) here because
        # the UI thread sends commands through rtde_c concurrently. ur-rtde is
        # not thread-safe for concurrent access to the same interface.
        # Torque data comes from actual_current_as_torque_Nm (RTDEReceiveInterface)
        # and TCP offset is not available from the receive interface.

        # 1. Timing
        timing = {
            "sample_index": idx,
            "elapsed_time_s": round(elapsed, 6),
            "wall_clock_iso": datetime.now().isoformat(timespec="milliseconds"),
            "controller_timestamp_s":    scalar(safe_get(con, "getTimestamp")),
            "actual_execution_time_ms":  scalar(safe_get(con, "getActualExecutionTime")),
        }

        # 2. Joints — all methods below use RTDEReceiveInterface only
        joints = {
            "actual_position_rad":         vec_to_dict(safe_get(con, "getActualQ"), JOINT_NAMES),
            "actual_velocity_rad_s":       vec_to_dict(safe_get(con, "getActualQd"), JOINT_NAMES),
            "actual_current_A":            vec_to_dict(safe_get(con, "getActualCurrent"), JOINT_NAMES),
            "actual_current_as_torque_Nm": vec_to_dict(safe_get(con, "getActualCurrentAsTorque"), JOINT_NAMES),
            "actual_voltage_V":            vec_to_dict(safe_get(con, "getActualJointVoltage"), JOINT_NAMES),
            "temperature_C":               vec_to_dict(safe_get(con, "getJointTemperatures"), JOINT_NAMES),
            "joint_mode":                  vec_to_dict(safe_get(con, "getJointMode"), JOINT_NAMES),
            "control_output":              vec_to_dict(safe_get(con, "getJointControlOutput"), JOINT_NAMES),
            "target_position_rad":         vec_to_dict(safe_get(con, "getTargetQ"), JOINT_NAMES),
            "target_velocity_rad_s":       vec_to_dict(safe_get(con, "getTargetQd"), JOINT_NAMES),
            "target_accel_rad_s2":         vec_to_dict(safe_get(con, "getTargetQdd"), JOINT_NAMES),
            "target_current_A":            vec_to_dict(safe_get(con, "getTargetCurrent"), JOINT_NAMES),
            "target_moment_Nm":            vec_to_dict(safe_get(con, "getTargetMoment"), JOINT_NAMES),
            "joint_torques_Nm":            vec_to_dict(None, JOINT_NAMES),
        }

        # 3. TCP / Cartesian — RTDEReceiveInterface only
        tcp = {
            "actual_pose_m_rad":   vec_to_dict(safe_get(con, "getActualTCPPose"), CART_AXES),
            "actual_speed_m_s":    vec_to_dict(safe_get(con, "getActualTCPSpeed"), CART_AXES),
            "actual_force_N_Nm":   vec_to_dict(safe_get(con, "getActualTCPForce"), FORCE_AXES),
            "target_pose_m_rad":   vec_to_dict(safe_get(con, "getTargetTCPPose"), CART_AXES),
            "target_speed_m_s":    vec_to_dict(safe_get(con, "getTargetTCPSpeed"), CART_AXES),
            "tcp_offset_m_rad":    vec_to_dict(None, CART_AXES),
            "ft_raw_wrench_N_Nm":  vec_to_dict(safe_get(con, "getFtRawWrench"), FORCE_AXES),
        }

        # 4. Tool Accelerometer
        ta_raw = safe_get(con, "getActualToolAccelerometer")
        tool_accel = vec_to_dict(ta_raw, ["ax", "ay", "az"]) if ta_raw else {"ax": None, "ay": None, "az": None}

        # 5. Analog I/O (only the four that ur_rtde exposes as getters)
        analog_io = {
            "standard_analog_input_0":  scalar(safe_get(con, "getStandardAnalogInput0")),
            "standard_analog_input_1":  scalar(safe_get(con, "getStandardAnalogInput1")),
            "standard_analog_output_0": scalar(safe_get(con, "getStandardAnalogOutput0")),
            "standard_analog_output_1": scalar(safe_get(con, "getStandardAnalogOutput1")),
        }

        # 6. Digital I/O (only the two bitmasks ur_rtde exposes)
        di_bits = safe_get(con, "getActualDigitalInputBits")
        do_bits = safe_get(con, "getActualDigitalOutputBits")
        digital_io = {
            "digital_inputs":      unpack_bits(di_bits, DIGITAL_INPUT_LABELS),
            "digital_outputs":     unpack_bits(do_bits, DIGITAL_OUTPUT_LABELS),
            "digital_inputs_raw":  di_bits,
            "digital_outputs_raw": do_bits,
        }

        # 7. Power
        power = {
            "main_voltage_V":            scalar(safe_get(con, "getActualMainVoltage")),
            "robot_voltage_48V":         scalar(safe_get(con, "getActualRobotVoltage")),
            "robot_current_A":           scalar(safe_get(con, "getActualRobotCurrent")),
            "cartesian_momentum_kg_m_s": scalar(safe_get(con, "getActualMomentum")),
        }

        # 8. Motion Scaling
        motion = {
            "speed_scaling_factor":   scalar(safe_get(con, "getSpeedScaling")),
            "target_speed_fraction":  scalar(safe_get(con, "getTargetSpeedFraction")),
            "speed_scaling_combined": scalar(safe_get(con, "getSpeedScalingCombined")),
        }

        # 9. Payload
        payload = {
            "mass_kg":              scalar(safe_get(con, "getPayload")),
            "center_of_gravity":    vec_to_dict(safe_get(con, "getPayloadCog"), ["x", "y", "z"]),
            "inertia_matrix_kg_m2": vec_to_dict(safe_get(con, "getPayloadInertia"),
                                                ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]),
        }

        # 10. Robot & Safety Status
        # getRobotStatus() returns a uint32 bitmask with bits 0-3 giving:
        #   bit 0 = power_on, bit 1 = program_running,
        #   bit 2 = teach_button_pressed, bit 3 = power_button_pressed
        # getSafetyStatusBits() returns a uint32 bitmask per the SafetyStatus enum
        # in the ur_rtde docs (IS_NORMAL_MODE, IS_REDUCED_MODE, IS_PROTECTIVE_STOPPED,
        #   IS_RECOVERY_MODE, IS_SAFEGUARD_STOPPED, IS_SYSTEM_EMERGENCY_STOPPED,
        #   IS_ROBOT_EMERGENCY_STOPPED, IS_EMERGENCY_STOPPED, IS_VIOLATION,
        #   IS_FAULT, IS_STOPPED_DUE_TO_SAFETY).
        robot_mode_val  = safe_get(con, "getRobotMode")
        safety_mode_val = safe_get(con, "getSafetyMode")
        safety_bits_val = safe_get(con, "getSafetyStatusBits")
        robot_status_val = safe_get(con, "getRobotStatus")
        runtime_val     = safe_get(con, "getRuntimeState")

        # Determine safety status from the safety bits (highest-priority bit set wins)
        safety_status_desc = "UNKNOWN"
        if safety_bits_val is not None:
            bits = safety_bits_val
            # Priority order: faults > emergency > protective > safeguard > reduced > normal
            if (bits >> 9) & 1:
                safety_status_desc = "FAULT"
            elif (bits >> 8) & 1:
                safety_status_desc = "VIOLATION"
            elif (bits >> 7) & 1:
                safety_status_desc = "EMERGENCY_STOPPED"
            elif (bits >> 6) & 1:
                safety_status_desc = "ROBOT_EMERGENCY_STOPPED"
            elif (bits >> 5) & 1:
                safety_status_desc = "SYS_EMERGENCY_STOPPED"
            elif (bits >> 4) & 1:
                safety_status_desc = "SAFEGUARD_STOPPED"
            elif (bits >> 2) & 1:
                safety_status_desc = "PROTECTIVE_STOPPED"
            elif (bits >> 3) & 1:
                safety_status_desc = "RECOVERY"
            elif (bits >> 1) & 1:
                safety_status_desc = "REDUCED"
            elif (bits >> 0) & 1:
                safety_status_desc = "NORMAL"

        status = {
            "robot_mode_code":        robot_mode_val,
            "robot_mode_desc":        ROBOT_MODE_MAP.get(robot_mode_val, "UNKNOWN"),
            "safety_mode_code":       safety_mode_val,
            "safety_mode_desc":       SAFETY_MODE_MAP.get(safety_mode_val, "UNKNOWN"),
            "safety_status_code":     safety_bits_val,
            "safety_status_desc":     safety_status_desc,
            "safety_status_bits":     unpack_bits(safety_bits_val, SAFETY_BIT_LABELS),
            "robot_status_bits":      unpack_bits(robot_status_val, ROBOT_BIT_LABELS),
            "robot_status_raw":       robot_status_val,
            "runtime_state_code":     runtime_val,
            "runtime_state_desc":     RUNTIME_STATE_MAP.get(runtime_val, "UNKNOWN"),
            "is_protective_stopped":  safe_get(con, "isProtectiveStopped"),
            "is_emergency_stopped":   safe_get(con, "isEmergencyStopped"),
        }

        return {
            "timing": timing,
            "joints": joints,
            "tcp": tcp,
            "tool_accelerometer": tool_accel,
            "analog_io": analog_io,
            "digital_io": digital_io,
            "power": power,
            "motion_scaling": motion,
            "payload": payload,
            "status": status,
        }

    def dispatch_command(self, command: str, params: Dict) -> Dict:
        if not self.connected:
            return {"status": "error", "message": "Not connected to robot"}
        try:
            if command == "moveJ":
                self.rtde_c.moveJ(params["target"], params["speed"], params["acceleration"])
            elif command == "moveL":
                self.rtde_c.moveL(params["target"], params["speed"], params["acceleration"])
            elif command == "jogStart":
                # jogStart(speeds, feature=FEATURE_BASE (0), acc=0.5, custom_frame={})
                feature = params.get("feature", 0)  # 0=base, 1=tool, 2=custom
                self.rtde_c.jogStart(params["speeds"], feature, params["acceleration"])
            elif command == "jogStop":
                self.rtde_c.jogStop()
            elif command == "stopJ":
                self.rtde_c.stopJ(params.get("acceleration", 2.0))
            elif command == "stopL":
                self.rtde_c.stopL(params.get("deceleration", 10.0), params.get("asynchronous", True))
            elif command == "stopScript":
                self.rtde_c.stopScript()
            elif command == "freedriveMode":
                self.rtde_c.freedriveMode()
            elif command == "endFreedriveMode":
                self.rtde_c.endFreedriveMode()
            elif command == "zeroFtSensor":
                self.rtde_c.zeroFtSensor()
            elif command == "setPayload":
                self.rtde_c.setPayload(params["mass"], params["cog"])
            elif command == "setTcp":
                self.rtde_c.setTcp(params["offset"])
            elif command == "reuploadScript":
                self.rtde_c.reuploadScript()
            elif command == "setStandardDigitalOut":
                self.rtde_io_iface.setStandardDigitalOut(params["id"], params["level"])
            elif command == "setConfigurableDigitalOut":
                self.rtde_io_iface.setConfigurableDigitalOut(params["id"], params["level"])
            elif command == "setToolDigitalOut":
                self.rtde_io_iface.setToolDigitalOut(params["id"], params["level"])
            elif command == "setSpeedSlider":
                self.rtde_io_iface.setSpeedSlider(params["speed"])
            elif command == "setAnalogOutputVoltage":
                self.rtde_io_iface.setAnalogOutputVoltage(params["id"], params["ratio"])
            elif command == "powerOn":
                self.dash.powerOn()
            elif command == "powerOff":
                self.dash.powerOff()
            elif command == "brakeRelease":
                self.dash.brakeRelease()
            elif command == "unlockProtectiveStop":
                self.dash.unlockProtectiveStop()
            elif command == "restartSafety":
                self.dash.restartSafety()
            elif command == "activateGripper":
                self.rtde_c.sendCustomScript(
                    "def activate_gripper():\n"
                    "  rq_activate_and_wait()\n"
                    "end\n"
                )
            elif command == "loadProgram":
                program = params.get("program", "")
                if not program.endswith(".urp"):
                    program += ".urp"
                self.dash.loadURP(program)
            elif command == "play":
                self.dash.play()
            elif command == "pause":
                self.dash.pause()
            elif command == "stop":
                self.dash.stop()
            else:
                return {"status": "error", "message": f"Unknown command: {command}"}
            return {"status": "ok"}
        except Exception as e:
            log.error(f"Command '{command}' failed: {e}")
            return {"status": "error", "message": str(e)}

# ══════════════════════════════════════════════════════════════════════════════
#  REALSENSE CAPTURE
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  SAFETY MONITOR — Person Detection + Hand Gestures + Depth Zone
# ══════════════════════════════════════════════════════════════════════════════

class SafetyMonitor:
    """Processes frames for person detection, hand gestures, and depth-based safety zones.

    Uses OpenVINO for person detection and MediaPipe for hand gesture recognition.
    Both are optional — if not installed, that feature is silently disabled.
    """

    # Safety zone colors
    COLOR_SAFE    = (0, 200, 0)    # Green
    COLOR_WARNING = (0, 180, 255)  # Orange
    COLOR_DANGER  = (0, 0, 220)    # Red
    COLOR_TEXT    = (255, 255, 255) # White

    def __init__(self, safety_radius: float = 1.5, warning_radius: float = 2.5,
                 confidence_threshold: float = 0.55, model_path: Optional[str] = None):
        self.safety_radius = safety_radius
        self.warning_radius = warning_radius
        self.confidence_threshold = confidence_threshold

        # State
        self.persons_detected: List[Dict] = []
        self.person_in_zone = False
        self.closest_distance = float("inf")      # distance from nearest robot link (base frame)
        self.closest_link_index = -1              # which link is closest (0=base..5=wrist3)
        self.gesture = None  # "stop", "resume", or None
        self.safety_status = "CLEAR"  # "CLEAR", "WARNING", "DANGER"
        self.robot_paused_by_safety = False

        # Camera intrinsics (populated by RealSenseCapture on start)
        self.intrinsics: Optional[Dict] = None

        # Latest joint angles from the telemetry loop — used for forward kinematics
        # Default pose: home position so fallback distance computation still works
        self.latest_q = [0.0, -1.57, 0.0, 0.0, 1.57, 0.0]
        self.latest_joint_points = forward_kinematics_ur5e(self.latest_q)

        # Gesture latch: stop gesture latches ON until a resume gesture is seen
        self.gesture_hold_stop = False    # True = stop gesture was seen, robot must stay stopped
        self.gesture_hold_resume = False  # True = resume gesture was seen this frame

        # OpenVINO person detection
        self.ov_model = None
        self.ov_input_shape = None
        self.ov_output_layer = None
        if HAS_OPENVINO:
            self._init_openvino(model_path)

        # YOLO object detection
        self.yolo_model = None
        self._yolo_cache = []
        self._init_yolo()

        # MediaPipe hand detection
        self.mp_hands = None
        self.mp_drawing = None
        if HAS_MEDIAPIPE:
            self._init_mediapipe()

        log.info(f"SafetyMonitor: person_detect={'ON' if self.ov_model else 'OFF'}, "
                 f"yolo={'ON' if self.yolo_model else 'OFF'}, "
                 f"hand_gesture={'ON' if self.mp_hands else 'OFF'}, "
                 f"safety_radius={safety_radius}m, warning_radius={warning_radius}m")
        log.info(f"SafetyMonitor: camera at {CAMERA_POS_IN_BASE} in robot base frame, "
                 f"aimed at {CAMERA_LOOK_AT_IN_BASE}")

    def update_joint_state(self, q: Optional[List[float]]):
        """Called by the telemetry loop with the latest joint angles.
        Used to compute nearest-link distances in the robot base frame."""
        if q is not None and len(q) == 6:
            self.latest_q = list(q)
            self.latest_joint_points = forward_kinematics_ur5e(self.latest_q)

    def _init_openvino(self, model_path: Optional[str] = None):
        """Initialize OpenVINO person detection model."""
        # Try to find the model in common locations
        search_paths = [
            model_path,
            "intel/person-detection-retail-0013/FP16/person-detection-retail-0013.xml",
            "person-detection-retail-0013.xml",
            os.path.join(os.path.dirname(__file__), "models", "person-detection-retail-0013.xml"),
        ]
        xml_path = None
        for p in search_paths:
            if p and os.path.isfile(p):
                xml_path = p
                break

        if xml_path is None:
            log.warning("SafetyMonitor: OpenVINO model not found. Person detection disabled.")
            log.warning("  Download with: omz_downloader --name person-detection-retail-0013")
            return

        try:
            ie = OVCore()
            model = ie.read_model(model=xml_path)
            self.ov_compiled = ie.compile_model(model=model, device_name="CPU")
            self.ov_input_layer = self.ov_compiled.input(0)
            self.ov_output_layer = self.ov_compiled.output(0)
            _, _, self.ov_h, self.ov_w = self.ov_input_layer.shape
            log.info(f"SafetyMonitor: OpenVINO model loaded from {xml_path} "
                     f"(input: {self.ov_w}x{self.ov_h})")
            self.ov_model = True
        except Exception as e:
            log.error(f"SafetyMonitor: Failed to load OpenVINO model: {e}")
            self.ov_model = None

    def _init_yolo(self):
        """Initialize YOLO model for object detection."""
        yolo_path = os.path.join(os.path.dirname(__file__), "..", "weights (3).pt")
        if not os.path.isfile(yolo_path):
            yolo_path = os.path.join(os.path.dirname(__file__), "weights (3).pt")
        if not os.path.isfile(yolo_path):
            search = [
                r"C:\Users\yousifi\Documents\GE Demo\weights (3).pt",
                os.path.join(os.getcwd(), "weights (3).pt"),
            ]
            for p in search:
                if os.path.isfile(p):
                    yolo_path = p
                    break
        try:
            from ultralytics import YOLO
            self.yolo_model = YOLO(yolo_path)
            log.info(f"SafetyMonitor: YOLO model loaded from {yolo_path}")
        except Exception as e:
            log.warning(f"SafetyMonitor: YOLO init failed: {e}")
            self.yolo_model = None

    def _detect_yolo(self, color_img, h, w):
        """Run YOLO inference on a downscaled copy, cache results."""
        try:
            scale = 640 / max(h, w)
            small = cv2.resize(color_img, (int(w * scale), int(h * scale)))
            results = self.yolo_model(small, verbose=False, conf=0.25, imgsz=640)[0]
            inv_scale = 1.0 / scale
            self._yolo_cache = []
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = int(x1 * inv_scale), int(y1 * inv_scale), int(x2 * inv_scale), int(y2 * inv_scale)
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = results.names.get(cls_id, f"cls{cls_id}")
                self._yolo_cache.append((x1, y1, x2, y2, label, conf))
            log.debug(f"YOLO: {len(self._yolo_cache)} detections")
        except Exception as e:
            log.warning(f"YOLO detection error: {e}")
            self._yolo_cache = []

    def _draw_yolo(self, color_img, h, w):
        """Draw cached YOLO detections onto a frame."""
        cache = getattr(self, '_yolo_cache', [])
        for (x1, y1, x2, y2, label, conf) in cache:
            color = (0, 255, 128)
            cv2.rectangle(color_img, (x1, y1), (x2, y2), color, 2)
            text = f"{label} {conf:.0%}"
            (tw, th_t), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
            cv2.rectangle(color_img, (x1, y1 - th_t - 12), (x1 + tw + 10, y1), color, -1)
            cv2.putText(color_img, text, (x1 + 5, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(color_img, f"YOLO: {len(cache)} obj", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2, cv2.LINE_AA)

    def _init_mediapipe(self):
        """Initialize MediaPipe hand detection. Handles both legacy and new API."""
        try:
            # Try legacy API first (mp.solutions.hands)
            if hasattr(mp, 'solutions'):
                self.mp_hands_module = mp.solutions.hands
                self.mp_drawing = mp.solutions.drawing_utils
                self.mp_hands = self.mp_hands_module.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.5,
                )
                self._mp_api = "legacy"
                log.info("SafetyMonitor: MediaPipe Hands initialized (legacy API)")
            else:
                # New API (mediapipe >= 0.10.21 task-based)
                from mediapipe.tasks.python import vision as mp_vision
                from mediapipe.tasks.python import BaseOptions
                import urllib.request, ssl, tempfile, os

                # Download hand landmarker model if needed
                model_path = os.path.join(tempfile.gettempdir(), "hand_landmarker.task")
                if not os.path.exists(model_path):
                    log.info("SafetyMonitor: Downloading MediaPipe hand landmarker model...")
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, context=ssl_ctx) as resp:
                        with open(model_path, "wb") as f:
                            f.write(resp.read())
                    log.info(f"SafetyMonitor: Hand model saved to {model_path}")

                options = mp_vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    num_hands=2,
                    min_hand_detection_confidence=0.6,
                    min_tracking_confidence=0.5,
                )
                self.mp_hands = mp_vision.HandLandmarker.create_from_options(options)
                self.mp_drawing = None
                self.mp_hands_module = None
                self._mp_api = "tasks"
                log.info("SafetyMonitor: MediaPipe Hands initialized (tasks API)")

        except Exception as e:
            log.error(f"SafetyMonitor: Failed to init MediaPipe: {e}")
            self.mp_hands = None
            self._mp_api = None

    def process_frame(self, color_img: 'np.ndarray', depth_frame) -> 'np.ndarray':
        """Process a frame: detect persons, check depth, detect gestures, draw overlays.

        Args:
            color_img: BGR image from RealSense (will be modified in-place with overlays)
            depth_frame: RealSense depth frame (aligned to color)

        Returns:
            The annotated color_img with all safety overlays drawn
        """
        h, w = color_img.shape[:2]
        self.persons_detected = []
        self.closest_distance = float("inf")
        self.gesture = None

        # ── Person Detection (OpenVINO) ──
        if self.ov_model:
            self._detect_persons(color_img, depth_frame, h, w)

        # ── Hand Gesture Detection (MediaPipe) ──
        if self.mp_hands:
            self._detect_gestures(color_img, h, w)

        # ── Determine safety status based on nearest-link distance (robot frame) ──
        if self.persons_detected:
            distances = [p["distance"] for p in self.persons_detected if p["distance"] < 20.0]
            if distances:
                self.closest_distance = min(distances)
                nearest = min(self.persons_detected, key=lambda p: p["distance"])
                self.closest_link_index = nearest.get("link_index", -1)
            else:
                # Persons detected but no valid depth / no intrinsics — treat as unknown, not danger
                self.closest_distance = float("inf")
                self.closest_link_index = -1

        if self.closest_distance < self.safety_radius:
            self.safety_status = "DANGER"
            self.person_in_zone = True
        elif self.closest_distance < self.warning_radius:
            self.safety_status = "WARNING"
            self.person_in_zone = False
        else:
            self.safety_status = "CLEAR"
            self.person_in_zone = False

        # ── Gesture latch logic ──
        # Stop gesture LATCHES — robot stays stopped until explicit resume gesture
        # Resume gesture ONLY works when zone is also clear
        self.gesture_hold_resume = False  # Reset each frame

        if self.gesture == "stop":
            self.gesture_hold_stop = True
            self.gesture_hold_resume = False
            log.debug("Gesture: STOP latch ON")
        elif self.gesture == "resume":
            if not self.person_in_zone:
                # Only allow resume if zone is clear
                self.gesture_hold_stop = False
                self.gesture_hold_resume = True
                log.debug("Gesture: RESUME accepted, latch OFF")
            else:
                # Can't resume while someone is in the zone
                self.gesture_hold_resume = False
                log.debug("Gesture: RESUME rejected — person still in zone")

        # Override safety status if gesture latch is active
        if self.gesture_hold_stop:
            self.safety_status = "DANGER"
            self.person_in_zone = True  # Force pause regardless of distance

        # ── Draw safety status banner ──
        self._draw_status_banner(color_img, w)

        return color_img

    def _detect_persons(self, color_img, depth_frame, h, w):
        """Run OpenVINO person detection, transform to robot base frame,
        and compute nearest-link distance."""
        try:
            resized = cv2.resize(color_img, (self.ov_w, self.ov_h))
            input_blob = np.expand_dims(resized.transpose(2, 0, 1), 0)
            results = self.ov_compiled([input_blob])[self.ov_output_layer]

            for obj in results[0][0]:
                confidence = float(obj[2])
                if confidence < self.confidence_threshold:
                    continue
                class_id = int(obj[1])
                if class_id != 1:  # 1 = person
                    continue

                xmin = max(0, int(obj[3] * w))
                ymin = max(0, int(obj[4] * h))
                xmax = min(w, int(obj[5] * w))
                ymax = min(h, int(obj[6] * h))

                # Sample depth — median of a grid around center for robustness
                cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
                depth_m = self._sample_depth(depth_frame, cx, cy, w, h)

                # ── Convert pixel + depth into robot base frame ──
                person_base = None
                link_distance = float("inf")
                link_index = -1
                if depth_m > 0 and self.intrinsics:
                    person_base = camera_pixel_to_base(cx, cy, depth_m, self.intrinsics)
                    if person_base is not None:
                        link_distance, link_index = nearest_link_distance(
                            person_base, self.latest_joint_points
                        )

                person = {
                    "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                    "cx": cx, "cy": cy,
                    "depth_cam_m": depth_m,              # raw distance from camera
                    "position_base": person_base,        # (x,y,z) in robot base frame
                    "distance": link_distance,           # min distance to any robot link
                    "link_index": link_index,            # 0=base..5=wrist3
                    "confidence": confidence,
                }
                self.persons_detected.append(person)

                # Color based on nearest-link distance (robot frame), not camera depth
                if link_distance < self.safety_radius:
                    box_color = self.COLOR_DANGER
                    thickness = 3
                elif link_distance < self.warning_radius:
                    box_color = self.COLOR_WARNING
                    thickness = 2
                else:
                    box_color = self.COLOR_SAFE
                    thickness = 2

                cv2.rectangle(color_img, (xmin, ymin), (xmax, ymax), box_color, thickness)
                cv2.circle(color_img, (cx, cy), 4, (0, 0, 255), -1)

                # Distance label shows BOTH camera distance and robot-link distance
                link_names = ["base", "shldr", "elbow", "wrist1", "wrist2", "wrist3"]
                link_name = link_names[link_index] if 0 <= link_index < 6 else "?"
                if link_distance < float("inf"):
                    dist_text = f"{link_distance:.2f}m to {link_name}"
                else:
                    dist_text = f"cam:{depth_m:.2f}m (no FK)"
                conf_text = f"{confidence:.0%}"
                label = f"Person {dist_text} ({conf_text})"
                label_bg_y = max(ymin - 28, 0)
                cv2.rectangle(color_img, (xmin, label_bg_y), (xmin + len(label) * 9 + 10, label_bg_y + 24),
                              box_color, -1)
                cv2.putText(color_img, label, (xmin + 5, label_bg_y + 17),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_TEXT, 1, cv2.LINE_AA)

        except Exception as e:
            log.warning(f"SafetyMonitor person detection error: {e}")

    def _sample_depth(self, depth_frame, cx, cy, w, h, grid_size=7):
        """Sample a grid of depth values around the center point, return median valid distance.
        Uses a wider grid at 1080p to ensure we hit the person's body, not gaps."""
        if depth_frame is None:
            return 0.0
        samples = []
        half = grid_size // 2
        # Spacing proportional to image size (wider at higher res)
        spacing = max(8, w // 120)
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                px = max(0, min(w - 1, cx + dx * spacing))
                py = max(0, min(h - 1, cy + dy * spacing))
                try:
                    d = depth_frame.get_distance(px, py)
                    if 0.1 < d < 9.0:  # L515 valid range
                        samples.append(d)
                except Exception:
                    pass
        if samples:
            samples.sort()
            return samples[len(samples) // 2]  # median
        return 0.0

    def _detect_gestures(self, color_img, h, w):
        """Detect hand gestures using MediaPipe (handles both legacy and tasks API)."""
        try:
            rgb = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)

            if self._mp_api == "legacy":
                results = self.mp_hands.process(rgb)
                if not results.multi_hand_landmarks:
                    return
                for hand_landmarks in results.multi_hand_landmarks:
                    if self.mp_drawing:
                        self.mp_drawing.draw_landmarks(
                            color_img, hand_landmarks, self.mp_hands_module.HAND_CONNECTIONS,
                            self.mp_drawing.DrawingSpec(color=(0, 200, 0), thickness=2, circle_radius=2),
                            self.mp_drawing.DrawingSpec(color=(200, 200, 200), thickness=1),
                        )
                    gesture = self._classify_gesture(hand_landmarks)
                    if gesture:
                        self.gesture = gesture
                        wrist = hand_landmarks.landmark[0]
                        gx, gy = int(wrist.x * w), int(wrist.y * h) - 30
                        icon = "STOP" if gesture == "stop" else "RESUME"
                        color = self.COLOR_DANGER if gesture == "stop" else self.COLOR_SAFE
                        cv2.putText(color_img, icon, (gx - 30, max(gy, 20)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

            elif self._mp_api == "tasks":
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self.mp_hands.detect(mp_image)
                if result.hand_landmarks:
                    for hand_lms in result.hand_landmarks:
                        # Draw landmarks manually
                        pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms]
                        for pt in pts:
                            cv2.circle(color_img, pt, 3, (0, 200, 0), -1)
                        connections = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
                                       (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
                                       (13,17),(17,18),(18,19),(19,20),(0,17)]
                        for i1, i2 in connections:
                            if i1 < len(pts) and i2 < len(pts):
                                cv2.line(color_img, pts[i1], pts[i2], (200, 200, 200), 1)
                        # Classify gesture
                        gesture = self._classify_gesture_tasks(hand_lms)
                        if gesture:
                            self.gesture = gesture
                            gx, gy = pts[0][0], pts[0][1] - 30
                            icon = "STOP" if gesture == "stop" else "RESUME"
                            color = self.COLOR_DANGER if gesture == "stop" else self.COLOR_SAFE
                            cv2.putText(color_img, icon, (gx - 30, max(gy, 20)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

        except Exception as e:
            log.warning(f"SafetyMonitor gesture detection error: {e}")

    def _classify_gesture_tasks(self, hand_lms) -> Optional[str]:
        """Classify gesture from tasks API hand landmarks (list of NormalizedLandmark)."""
        tips = [4, 8, 12, 16, 20]
        pips = [3, 6, 10, 14, 18]
        lm = hand_lms
        fingers_up = []
        thumb_extended = abs(lm[tips[0]].x - lm[pips[0]].x) > 0.05
        fingers_up.append(thumb_extended)
        for i in range(1, 5):
            fingers_up.append(lm[tips[i]].y < lm[pips[i]].y)
        num_extended = sum(fingers_up)
        if num_extended >= 4:
            return "stop"
        if fingers_up[0] and num_extended == 1:
            return "resume"
        return None

    def _classify_gesture(self, hand_landmarks) -> Optional[str]:
        """Classify hand gesture from MediaPipe landmarks.

        - Open palm (all fingers extended) = "stop"
        - Thumbs up (only thumb extended) = "resume"
        """
        lm = hand_landmarks.landmark

        # Finger tip and pip indices
        tips = [4, 8, 12, 16, 20]    # thumb, index, middle, ring, pinky tips
        pips = [3, 6, 10, 14, 18]    # corresponding PIP joints

        # Check which fingers are extended (tip above pip in y, except thumb uses x)
        fingers_up = []

        # Thumb — compare x (depends on handedness, simplified)
        thumb_extended = abs(lm[tips[0]].x - lm[pips[0]].x) > 0.05
        fingers_up.append(thumb_extended)

        # Other fingers — tip.y < pip.y means extended (y is inverted in image coords)
        for i in range(1, 5):
            fingers_up.append(lm[tips[i]].y < lm[pips[i]].y)

        num_extended = sum(fingers_up)

        # Open palm: all 5 fingers extended
        if num_extended >= 4:
            return "stop"

        # Thumbs up: only thumb extended
        if fingers_up[0] and num_extended == 1:
            return "resume"

        return None

    def _draw_status_banner(self, color_img, w):
        """Draw safety status banner at the top of the frame."""
        dist_str = f"{self.closest_distance:.2f}m" if self.closest_distance < 100 else "N/A"
        if self.safety_status == "DANGER":
            bg_color = self.COLOR_DANGER
            if self.gesture_hold_stop:
                text = "STOPPED — GESTURE OVERRIDE (show thumbs-up to resume)"
            elif self.gesture == "stop":
                text = "DANGER — STOP GESTURE DETECTED"
            else:
                text = f"DANGER — PERSON IN ZONE ({dist_str})"
        elif self.safety_status == "WARNING":
            bg_color = self.COLOR_WARNING
            text = f"WARNING — PERSON NEARBY ({dist_str})"
        else:
            bg_color = self.COLOR_SAFE
            n = len(self.persons_detected)
            text = "ZONE CLEAR" if n == 0 else f"ZONE CLEAR — {n} person(s) detected"

        cv2.rectangle(color_img, (0, 0), (w, 36), bg_color, -1)
        cv2.putText(color_img, text, (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    self.COLOR_TEXT, 2, cv2.LINE_AA)

        # Persons count + closest distance on right side
        dist_disp = f"{self.closest_distance:.2f}m" if self.closest_distance < 100 else "N/A"
        info = f"Persons: {len(self.persons_detected)} | Closest: {dist_disp}"
        text_size = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        cv2.putText(color_img, info, (w - text_size[0] - 12, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TEXT, 1, cv2.LINE_AA)

    def should_pause_robot(self) -> bool:
        """Returns True if the robot should be paused based on current safety state."""
        return self.person_in_zone or self.gesture_hold_stop

    def should_resume_robot(self) -> bool:
        """Returns True if the robot can safely resume.
        Requires: zone clear AND explicit thumbs-up gesture (no auto-resume)."""
        return not self.person_in_zone and self.gesture_hold_resume and not self.gesture_hold_stop


# ══════════════════════════════════════════════════════════════════════════════
#  REALSENSE CAPTURE (with integrated safety monitoring)
# ══════════════════════════════════════════════════════════════════════════════

class RealSenseCapture:
    """Background capture from Intel RealSense L515 with integrated safety monitoring.
    Uses 1920x1080 color + 1024x768 depth (L515 native resolutions)."""

    def __init__(self, safety_radius=1.5, warning_radius=2.5, model_path=None):
        self.pipeline = None
        self.align = None
        self.colorizer = None
        self.running = False
        self.lock = threading.Lock()
        self.color_frame = None
        self.depth_colormap = None
        self.frame_count = 0
        self.start_time = None

        # Safety monitor
        self.safety = SafetyMonitor(
            safety_radius=safety_radius,
            warning_radius=warning_radius,
            model_path=model_path,
        )

    def start(self):
        if not HAS_REALSENSE:
            log.warning("pyrealsense2/opencv not installed — camera disabled")
            return False
        try:
            self.pipeline = rs.pipeline()
            self.has_depth = False
            configs = [
                ("1280x720 color + 640x480 depth", True, lambda c: (
                    c.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30),
                    c.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30),
                )),
                ("1280x720 color only", False, lambda c: (
                    c.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30),
                )),
                ("1920x1080 color only", False, lambda c: (
                    c.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30),
                )),
            ]
            profile = None
            for desc, has_depth, setup_fn in configs:
                try:
                    config = rs.config()
                    setup_fn(config)
                    self.pipeline = rs.pipeline()
                    profile = self.pipeline.start(config)
                    self.has_depth = has_depth
                    log.info(f"RealSense: using {desc}")
                    break
                except RuntimeError as e:
                    log.warning(f"RealSense: {desc} failed — {e}")
                    continue
            if profile is None:
                raise RuntimeError("No camera configuration worked")
            self.align = rs.align(rs.stream.color) if self.has_depth else None
            self.colorizer = rs.colorizer()
            self.running = True
            self.start_time = time.time()
            device = profile.get_device()
            log.info(f"RealSense: {device.get_info(rs.camera_info.name)} connected")

            # ── Extract color stream intrinsics for pixel → 3D conversion ──
            try:
                color_stream = profile.get_stream(rs.stream.color)
                intrin = color_stream.as_video_stream_profile().get_intrinsics()
                self.safety.intrinsics = {
                    "fx": intrin.fx, "fy": intrin.fy,
                    "cx": intrin.ppx, "cy": intrin.ppy,
                    "width": intrin.width, "height": intrin.height,
                }
                log.info(f"RealSense intrinsics: fx={intrin.fx:.1f} fy={intrin.fy:.1f} "
                         f"cx={intrin.ppx:.1f} cy={intrin.ppy:.1f}")
            except Exception as e:
                log.warning(f"Could not read RealSense intrinsics: {e}")

            threading.Thread(target=self._capture_loop, daemon=True).start()
            return True
        except Exception as e:
            log.error(f"RealSense start failed: {e}")
            log.error("  - Close Intel RealSense Viewer if open (it locks the camera)")
            return False

    def _capture_loop(self):
        # Run heavy safety processing (OpenVINO + MediaPipe) every Nth frame to reduce CPU load.
        # Person position barely changes between frames; the previous detection persists in
        # self.safety.persons_detected so the overlay stays on screen.
        SAFETY_PROCESS_EVERY_N = 3   # process 1 of every 3 frames → ~10 Hz on a 30 FPS camera
        process_counter = 0
        while self.running:
            try:
                frames = self.pipeline.wait_for_frames()
                if self.align:
                    aligned = self.align.process(frames)
                    cf = aligned.get_color_frame()
                    df = aligned.get_depth_frame()
                else:
                    cf = frames.get_color_frame()
                    df = None
                if not cf:
                    continue

                color_img = np.asanyarray(cf.get_data())

                if df:
                    depth_colored_frame = self.colorizer.colorize(df)
                    depth_img = np.asanyarray(depth_colored_frame.get_data())
                    depth_img = cv2.resize(depth_img, (color_img.shape[1], color_img.shape[0]))
                else:
                    depth_img = None

                # ── YOLO detection (every 5th frame) + draw cached results every frame ──
                if self.safety.yolo_model:
                    if process_counter % 5 == 0:
                        self.safety._detect_yolo(color_img, color_img.shape[0], color_img.shape[1])
                    self.safety._draw_yolo(color_img, color_img.shape[0], color_img.shape[1])

                # ── Run safety monitoring at reduced rate ──
                if process_counter % SAFETY_PROCESS_EVERY_N == 0:
                    color_img = self.safety.process_frame(color_img, df)
                else:
                    self.safety._draw_status_banner(color_img, color_img.shape[1])
                process_counter += 1

                # FPS overlay (below safety banner)
                self.frame_count += 1
                elapsed = time.time() - self.start_time
                fps_actual = self.frame_count / max(elapsed, 0.001)
                cv2.putText(color_img, f"L515 | {fps_actual:.1f} FPS | {datetime.now().strftime('%H:%M:%S')}",
                            (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

                with self.lock:
                    self.color_frame = color_img.copy()
                    self.depth_colormap = depth_img.copy() if depth_img is not None else None
            except Exception as e:
                if self.running:
                    log.warning(f"Capture error: {e}")
                    time.sleep(0.1)

    def get_jpeg(self, mode="color", quality=70, max_width=960):
        """Returns a JPEG-encoded frame, downsized to max_width for browser streaming.
        Downsizing halves the width (1920→960) which reduces JPEG encode time and
        network payload by ~4x with no visible quality loss on a dashboard panel."""
        with self.lock:
            if mode == "combined" and self.color_frame is not None and self.depth_colormap is not None:
                frame = np.hstack((self.color_frame, self.depth_colormap))
            elif mode == "depth" and self.depth_colormap is not None:
                frame = self.depth_colormap
            elif self.color_frame is not None:
                frame = self.color_frame
            else:
                return None
        # Downsize for browser streaming
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes()

    def stop(self):
        self.running = False
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass

# ══════════════════════════════════════════════════════════════════════════════
#  DEMO DATA GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_demo(t: float, prev: Optional[Dict] = None) -> Dict:
    """Generate realistic fake telemetry for demo mode."""
    p = t * 0.3
    q  = [round(math.sin(p + i * 0.8) * 1.2 + (-1.57 if i == 1 else 0), 4) for i in range(6)]
    qd = [round(math.cos(p + i * 0.8) * 0.36, 4) for i in range(6)]
    cur = [round(abs(math.sin(p + i * 0.5)) * 1.8 + 0.3, 4) for i in range(6)]
    torque = [round(cur[i] * (8 + i * 2), 2) for i in range(6)]
    temps = [round(32 + i * 3 + math.sin(t * 0.01 + i) * 2 + t * 0.002, 1) for i in range(6)]
    track_err = [round((hash(f"{t}{i}") % 1000 - 500) / 500000, 6) for i in range(6)]
    forces = {
        "Fx": round(math.sin(p * 1.1) * 5, 2), "Fy": round(math.cos(p * 0.9) * 4, 2),
        "Fz": round(-9.8 + math.sin(p * 0.7) * 2, 2),
        "Mx": round(math.sin(p * 1.3) * 0.8, 3), "My": round(math.cos(p * 1.1) * 0.6, 3),
        "Mz": round(math.sin(p * 0.8) * 0.3, 3),
    }
    force_scalar = round(math.sqrt(forces["Fx"]**2 + forces["Fy"]**2 + forces["Fz"]**2), 1)
    v48 = round(47.8 + math.sin(t * 0.05) * 0.3, 2)
    i_robot = round(sum(cur) * 0.4 + 0.5, 2)
    prev_energy = prev.get("energy", 0) if prev else 0
    return {
        "t": round(t, 2), "q": q, "qd": qd, "cur": cur, "torque": torque,
        "temps": temps, "trackErr": track_err,
        "tcp": {"x": round(0.4 + math.sin(p) * 0.15, 4), "y": round(-0.2 + math.cos(p) * 0.1, 4),
                "z": round(0.35 + math.sin(p * 0.5) * 0.05, 4), "rx": 3.14, "ry": 0.01, "rz": -0.01},
        "tcpSpeed": round(abs(math.cos(p) * 0.045) + 0.001, 4),
        "forces": forces, "forceScalar": force_scalar,
        "v48": v48, "iRobot": i_robot, "power": round(v48 * i_robot, 1),
        "energy": round(prev_energy + v48 * i_robot * 0.001 / 3600, 4),
        "momentum": round(abs(math.sin(p)) * 3.5, 2),
        "speedScaling": round(0.98 + (hash(str(t)) % 20) / 1000, 2),
        "timeScaleDesc": "NOT_SCALED",
        "collisionRatio": round(abs(math.sin(p * 0.2)) * 0.15, 3),
        "deviationRatio": round(abs(math.cos(p * 0.3)) * 0.08, 3),
        "vibRMS": round(abs(math.sin(t * 0.7)) * 0.4, 3),
        "toolTemp": round(28 + math.sin(t * 0.02) * 3, 1),
        "robotMode": 7, "robotModeDesc": "RUNNING",
        "safetyStatus": 1, "safetyStatusDesc": "NORMAL", "safetyModeDesc": "NORMAL",
        "runtimeState": 2, "runtimeStateDesc": "RUNNING",
        "safetyBits": {k: (1 if k == "normal_mode" else 0) for k in SAFETY_BIT_LABELS},
        "robotBits": {"power_on": 1, "program_running": 1, "teach_button_pressed": 0, "power_button_pressed": 0},
        "payloadMass": 1.2, "isProtStopped": False, "isEmStopped": False,
    }


def parse_rtde_record(r: Dict) -> Dict:
    """Parse a raw RTDE record dict into the flat dashboard format.

    Consumes the cleaned-up collect_sample output which only uses real
    ur_rtde API methods. Fields not exposed by ur_rtde (energy, tool temp,
    collision ratio, deviation ratio) default to 0 and are labeled "N/A"
    in the UI rather than treated as real zeros.
    """
    j  = r.get("joints", {})
    tc = r.get("tcp", {})
    pw = r.get("power", {})
    ms = r.get("motion_scaling", {})
    st = r.get("status", {})
    ti = r.get("timing", {})
    ta = r.get("tool_accelerometer", {})
    pl = r.get("payload", {})

    q_dict  = j.get("actual_position_rad", {}) or {}
    qd_dict = j.get("actual_velocity_rad_s", {}) or {}
    cur_dict = j.get("actual_current_A", {}) or {}
    temp_dict = j.get("temperature_C", {}) or {}
    tgt_dict = j.get("target_position_rad", {}) or {}

    # Torque source priority:
    #  1. actual_current_as_torque_Nm — from RTDEReceiveInterface, firmware 5.23+/10.11+
    #  2. target_moment_Nm — controller setpoint, always available as last resort
    #  NOTE: getJointTorques (RTDEControlInterface) is not used here to avoid
    #        thread-safety issues with concurrent control commands.
    joint_torques_dict = j.get("joint_torques_Nm", {}) or {}
    actual_torque_dict = j.get("actual_current_as_torque_Nm", {}) or {}
    target_moment_dict = j.get("target_moment_Nm", {}) or {}

    q  = [q_dict.get(k, 0) or 0 for k in JOINT_NAMES]
    qd = [qd_dict.get(k, 0) or 0 for k in JOINT_NAMES]
    cur = [cur_dict.get(k, 0) or 0 for k in JOINT_NAMES]
    temps = [temp_dict.get(k, 0) or 0 for k in JOINT_NAMES]
    tgt = [tgt_dict.get(k, 0) or 0 for k in JOINT_NAMES]

    torque = []
    for k in JOINT_NAMES:
        t_jt = joint_torques_dict.get(k)
        t_actual = actual_torque_dict.get(k)
        t_target = target_moment_dict.get(k)
        if t_jt is not None and abs(t_jt) > 1e-4:
            torque.append(t_jt)
        elif t_actual is not None and abs(t_actual) > 1e-4:
            torque.append(t_actual)
        elif t_target is not None:
            torque.append(t_target)
        else:
            torque.append(0.0)

    track_err = [q[i] - tgt[i] for i in range(6)]

    tcp_pose = tc.get("actual_pose_m_rad", {}) or {}
    tcp_spd  = tc.get("actual_speed_m_s", {}) or {}
    sv = [tcp_spd.get(k, 0) or 0 for k in CART_AXES]
    tcp_speed = math.sqrt(sv[0]**2 + sv[1]**2 + sv[2]**2)

    f_src = tc.get("actual_force_N_Nm", {}) or {}
    forces = {k: (f_src.get(k, 0) or 0) for k in FORCE_AXES}
    force_scalar = math.sqrt(forces["Fx"]**2 + forces["Fy"]**2 + forces["Fz"]**2)

    ax = (ta.get("ax") or 0) if ta else 0
    ay = (ta.get("ay") or 0) if ta else 0
    az = (ta.get("az") or 0) if ta else 0
    # Vibration proxy: magnitude of acceleration minus gravity.
    # Works regardless of tool flange orientation.
    a_mag = math.sqrt(ax*ax + ay*ay + az*az)
    vib_rms = abs(a_mag - 9.81) if a_mag > 0.1 else 0

    v48 = pw.get("robot_voltage_48V", 0) or 0
    i_robot = pw.get("robot_current_A", 0) or 0

    return {
        "t": round(ti.get("elapsed_time_s", 0) or 0, 2),
        "q": q, "qd": qd, "cur": cur, "torque": torque, "temps": temps, "trackErr": track_err,
        "tcp": tcp_pose, "tcpSpeed": round(tcp_speed, 4),
        "forces": forces, "forceScalar": round(force_scalar, 1),
        "v48": round(v48, 2), "iRobot": round(i_robot, 2), "power": round(v48 * i_robot, 1),
        "energy": 0.0,            # getActualRobotEnergyConsumed not in ur_rtde
        "momentum": round((pw.get("cartesian_momentum_kg_m_s", 0) or 0), 2),
        "speedScaling": round((ms.get("speed_scaling_factor", 1) or 1), 2),
        "timeScaleDesc": "N/A",   # getTimeScaleSource not in ur_rtde
        "collisionRatio": 0.0,    # getCollisionDetectionRatio not in ur_rtde
        "deviationRatio": 0.0,    # getJointPositionDeviationRatio not in ur_rtde
        "vibRMS": round(vib_rms, 3),
        "toolTemp": 0.0,          # getToolTemperature not in ur_rtde
        "robotMode": st.get("robot_mode_code", -1),
        "robotModeDesc": st.get("robot_mode_desc", "UNKNOWN"),
        "safetyStatus": st.get("safety_status_code", -1),
        "safetyStatusDesc": st.get("safety_status_desc", "UNKNOWN"),
        "safetyModeDesc": st.get("safety_mode_desc", "UNKNOWN"),
        "runtimeState": st.get("runtime_state_code", -1),
        "runtimeStateDesc": st.get("runtime_state_desc", "UNKNOWN"),
        "safetyBits": st.get("safety_status_bits", {}) or {},
        "robotBits": st.get("robot_status_bits", {}) or {},
        "payloadMass": round((pl.get("mass_kg", 0) or 0), 2),
        "isProtStopped": bool(st.get("is_protective_stopped", False)),
        "isEmStopped": bool(st.get("is_emergency_stopped", False)),
    }

# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOGGER
# ══════════════════════════════════════════════════════════════════════════════

class DataLogger:
    def __init__(self, enabled=True, outdir=None, buffer_size=50):
        self.enabled = enabled
        self.buffer_size = buffer_size
        self.csv_file = None
        self.json_file = None
        self.csv_writer = None
        self.csv_buffer = deque()
        self.json_buffer = deque()
        self.outdir = outdir

    def setup(self, first_sample: Dict) -> bool:
        if not self.enabled:
            return True
        log_dir = self.outdir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "UR5_data_logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(log_dir, f"ur5e_data_{ts}.csv")
        json_path = os.path.join(log_dir, f"ur5e_data_{ts}.jsonl")
        try:
            flat = flatten_dict(first_sample)
            self.csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            self.json_file = open(json_path, "w", encoding="utf-8")
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=list(flat.keys()), extrasaction="ignore")
            self.csv_writer.writeheader()
            self.csv_writer.writerow(flat)
            self.json_file.write(json.dumps(first_sample, default=str) + "\n")
            log.info(f"Logging: {csv_path}")
            return True
        except Exception as e:
            log.error(f"Logger setup failed: {e}")
            return False

    def log_record(self, raw_record: Dict):
        if not self.enabled or not self.csv_writer:
            return
        self.csv_buffer.append(flatten_dict(raw_record))
        self.json_buffer.append(json.dumps(raw_record, default=str))
        if len(self.csv_buffer) >= self.buffer_size:
            self.flush()

    def flush(self):
        if self.csv_buffer and self.csv_writer:
            self.csv_writer.writerows(self.csv_buffer)
            self.csv_file.flush()
            self.csv_buffer.clear()
        if self.json_buffer and self.json_file:
            self.json_file.write("\n".join(self.json_buffer) + "\n")
            self.json_file.flush()
            self.json_buffer.clear()

    def close(self):
        self.flush()
        if self.csv_file:
            self.csv_file.close()
        if self.json_file:
            self.json_file.close()

# ══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET SERVER (for React dashboard)
# ══════════════════════════════════════════════════════════════════════════════

_ws_clients = set()
_ws_lock    = threading.Lock()
_ws_loop    = None


async def _ws_handler(websocket):
    with _ws_lock:
        _ws_clients.add(websocket)
    addr = websocket.remote_address
    log.info(f"[WS] Dashboard connected: {addr[0]}:{addr[1]} ({len(_ws_clients)} client(s))")
    try:
        await websocket.wait_closed()
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)
        log.info(f"[WS] Dashboard disconnected: {addr[0]}:{addr[1]} ({len(_ws_clients)} client(s))")


async def _ws_serve(port):
    async with websockets.serve(_ws_handler, "0.0.0.0", port):
        log.info(f"[WS] React dashboard WebSocket server on ws://0.0.0.0:{port}")
        await asyncio.Future()


def _start_ws_thread(port=8765):
    global _ws_loop
    if not HAS_WEBSOCKETS:
        log.warning("websockets not installed — React dashboard bridge disabled (pip install websockets)")
        return
    def _run():
        global _ws_loop
        _ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_ws_loop)
        _ws_loop.run_until_complete(_ws_serve(port))
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.3)


def broadcast_ws(record: Dict):
    if not _ws_clients or _ws_loop is None:
        return
    msg = json.dumps(record, default=str)
    with _ws_lock:
        clients = list(_ws_clients)
    for ws in clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send(msg), _ws_loop)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  APPLICATION STATE
# ══════════════════════════════════════════════════════════════════════════════

class AppState:
    """Shared state across all browser sessions."""

    def __init__(self, args):
        self.args = args
        self.robot = RobotInterface(args.ip)
        self.camera = RealSenseCapture(
            safety_radius=args.safety_radius,
            warning_radius=args.warning_radius,
            model_path=args.model_path,
        )
        self.logger = DataLogger(enabled=args.log, outdir=args.outdir, buffer_size=args.buffer_size)

        self.history: deque = deque(maxlen=HISTORY_LEN)
        self.sample: Optional[Dict] = None
        self.sample_count = 0
        self.start_time = 0
        self.running = False
        self.is_live = False

        self.ctrl_log: List[Dict] = []
        self.ctrl_log_lock = threading.Lock()
        self.freedrive_active = False

    def _log_event(self, ts: str, msg: str, type: str):
        """Thread-safe append to ctrl_log with automatic truncation."""
        with self.ctrl_log_lock:
            self.ctrl_log.insert(0, {"t": ts, "msg": msg, "type": type})
            if len(self.ctrl_log) > 50:
                del self.ctrl_log[50:]

    def start(self):
        self.start_time = time.time()
        self.running = True
        self.is_live = self.robot.connect()
        self.camera.start()

        # Start WebSocket server for React dashboard
        _start_ws_thread(port=getattr(self.args, 'ws_port', 8767))

        # First sample for logger
        if self.is_live:
            raw = self.robot.collect_sample(0, 0)
            if raw:
                self.logger.setup(raw)

        threading.Thread(target=self._telemetry_loop, daemon=True).start()
        log.info(f"Telemetry loop started ({'LIVE' if self.is_live else 'DEMO'} mode @ {self.args.rate} Hz)")

        # Safety auto-control loop (only when robot is connected)
        if self.is_live and self.args.safety_auto:
            threading.Thread(target=self._safety_control_loop, daemon=True).start()
            log.info(f"Safety auto-control loop started (radius={self.args.safety_radius}m)")

    def _safety_control_loop(self):
        """Continuously monitors safety state and pauses/resumes robot automatically.

        Stop priority:
        1. ✋ Stop gesture → immediate stopJ (hard stop, overrides everything)
        2. Person in zone → stopL (smooth deceleration)

        Resume requires:
        1. Zone must be clear (no person within safety radius)
        2. 👍 Resume gesture must be shown (no auto-resume)
        """
        while self.running:
            try:
                safety = self.camera.safety

                if safety.should_pause_robot() and not safety.robot_paused_by_safety:
                    ts = datetime.now().strftime("%H:%M:%S")

                    if safety.gesture_hold_stop:
                        # GESTURE OVERRIDE — hard stop, immediate
                        log.warning("SAFETY: STOP gesture — hard stopping robot")
                        self.robot.dispatch_command("stopJ", {"acceleration": 5.0})
                        self.robot.dispatch_command("stopScript", {})
                        self._log_event(ts, "⚠ GESTURE STOP — robot halted immediately", "error")
                    else:
                        # PROXIMITY — smooth deceleration
                        dist_str = f"{safety.closest_distance:.2f}m" if safety.closest_distance < 100 else "N/A"
                        log.warning(f"SAFETY: Person in zone ({dist_str}) — pausing robot")
                        self.robot.dispatch_command("stopL", {"deceleration": 10.0})
                        self._log_event(ts, f"⚠ SAFETY STOP — person at {dist_str}", "error")

                    safety.robot_paused_by_safety = True

                elif safety.should_resume_robot() and safety.robot_paused_by_safety:
                    # CLEAR + RESUME GESTURE — allow robot to continue
                    log.info("SAFETY: Zone clear + resume gesture — robot can resume")
                    safety.robot_paused_by_safety = False
                    ts = datetime.now().strftime("%H:%M:%S")
                    self._log_event(ts, "✓ RESUME GESTURE — robot unlocked", "ok")

                time.sleep(0.1)  # 10 Hz safety check
            except Exception as e:
                log.error(f"Safety control loop error: {e}")
                time.sleep(0.5)

    def _telemetry_loop(self):
        interval = 1.0 / self.args.rate
        ws_send_every = max(1, int(self.args.rate / 10))  # ~10 FPS to React dashboard
        accumulated_energy_Wh = 0.0  # derived via power × dt since RTDE doesn't expose it
        last_loop_start = None
        while self.running:
            loop_start = time.time()
            elapsed = loop_start - self.start_time

            if self.is_live:
                raw = self.robot.collect_sample(elapsed, self.sample_count)
                if raw:
                    self.logger.log_record(raw)
                    # Broadcast raw record to React dashboard via WebSocket
                    if self.sample_count % ws_send_every == 0:
                        broadcast_ws(raw)
                    sample = parse_rtde_record(raw)
                    # Accumulate energy: power (W) * dt (s) / 3600 = Wh
                    if last_loop_start is not None:
                        dt = loop_start - last_loop_start
                        accumulated_energy_Wh += sample.get("power", 0) * dt / 3600.0
                    sample["energy"] = round(accumulated_energy_Wh, 4)
                    # Feed joint angles to safety monitor for nearest-link distance
                    self.camera.safety.update_joint_state(sample.get("q"))
                else:
                    time.sleep(interval)
                    continue
            else:
                sample = generate_demo(elapsed, self.sample)
                # Feed demo joint angles to safety monitor too
                self.camera.safety.update_joint_state(sample.get("q"))

            self.sample = sample
            self.history.append(sample)
            self.sample_count += 1
            last_loop_start = loop_start

            sleep_time = interval - (time.time() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def send_command(self, command: str, params: Optional[Dict] = None) -> Dict:
        params = params or {}
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_event(ts, f"→ {command}", "cmd")

        result = self.robot.dispatch_command(command, params)
        status = result.get("status", "error")
        if status == "ok":
            self._log_event(ts, f"✓ {command}", "ok")
        else:
            self._log_event(ts, f"✗ {command}: {result.get('message','')}", "error")
        return result

    def send_command_verified(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Send a command and verify the robot actually reached the expected state.
        Returns {"status": "ok"/"error", "message": "...", "verified": True/False}"""
        params = params or {}

        # Step 1: send the command
        result = self.send_command(command, params)
        if result.get("status") != "ok":
            return {**result, "verified": False}

        # Step 2: for state-change commands, poll to verify
        if not self.connected_and_can_poll():
            return {**result, "verified": False, "message": "Cannot poll — not connected"}

        try:
            if command == "powerOn":
                return self._poll_robot_mode([4, 5, 7], timeout=5.0, desc="POWER_ON/IDLE/RUNNING")
            elif command == "powerOff":
                return self._poll_robot_mode([3], timeout=5.0, desc="POWER_OFF")
            elif command == "brakeRelease":
                return self._poll_robot_mode([5, 7], timeout=5.0, desc="IDLE/RUNNING")
            elif command in ("moveJ", "moveL"):
                target = params.get("target", [])
                if command == "moveJ":
                    return self._poll_joint_target(target, timeout=60.0)
                else:
                    return self._poll_tcp_target(target, timeout=60.0)
            elif command in ("stopJ", "stopScript"):
                # E-stop commands: verified by checking robot is no longer moving
                return self._poll_stopped(timeout=3.0)
            else:
                # For other commands (play, pause, stop, IO, etc.) — accept the dispatch ACK
                return {**result, "verified": True}
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_event(ts, f"⚠ verify failed: {e}", "error")
            return {"status": "ok", "verified": False, "message": f"Command sent but verify failed: {e}"}

    def connected_and_can_poll(self) -> bool:
        return self.is_live and self.robot.connected and self.robot.rtde_r is not None

    def _poll_robot_mode(self, target_modes: list, timeout: float, desc: str) -> Dict:
        """Poll getRobotMode until it matches one of the target modes."""
        start = time.time()
        while time.time() - start < timeout:
            mode = safe_get(self.robot.rtde_r, "getRobotMode")
            if mode in target_modes:
                ts = datetime.now().strftime("%H:%M:%S")
                mode_name = ROBOT_MODE_MAP.get(mode, str(mode))
                self._log_event(ts, f"✓ Verified: {mode_name}", "ok")
                return {"status": "ok", "verified": True, "message": f"Robot is {mode_name}"}
            time.sleep(0.2)
        return {"status": "error", "verified": False,
                "message": f"Timeout waiting for {desc} (still mode {ROBOT_MODE_MAP.get(mode, mode)})"}

    def _poll_joint_target(self, target: list, timeout: float, tolerance: float = 0.01) -> Dict:
        """Poll getActualQ until all joints are within tolerance of target."""
        if len(target) != 6:
            return {"status": "ok", "verified": False, "message": "Invalid target"}
        start = time.time()
        errors = [999.0] * 6  # initialize so it's always defined
        while time.time() - start < timeout:
            q = safe_get(self.robot.rtde_r, "getActualQ")
            if q and len(q) == 6:
                errors = [abs(q[i] - target[i]) for i in range(6)]
                if all(e < tolerance for e in errors):
                    ts = datetime.now().strftime("%H:%M:%S")
                    self._log_event(ts, f"✓ moveJ reached target", "ok")
                    return {"status": "ok", "verified": True, "message": "Target reached"}
            time.sleep(0.1)
        max_err = max(errors)
        return {"status": "error", "verified": False,
                "message": f"Timeout — max joint error: {max_err:.4f} rad"}

    def _poll_tcp_target(self, target: list, timeout: float, tolerance: float = 0.002) -> Dict:
        """Poll getActualTCPPose until within tolerance of target."""
        if len(target) != 6:
            return {"status": "ok", "verified": False, "message": "Invalid target"}
        start = time.time()
        while time.time() - start < timeout:
            pose = safe_get(self.robot.rtde_r, "getActualTCPPose")
            if pose and len(pose) == 6:
                errors = [abs(pose[i] - target[i]) for i in range(6)]
                # Position tolerance: 2mm, orientation tolerance: 0.01 rad
                tols = [tolerance]*3 + [0.01]*3
                if all(errors[i] < tols[i] for i in range(6)):
                    ts = datetime.now().strftime("%H:%M:%S")
                    self._log_event(ts, f"✓ moveL reached target", "ok")
                    return {"status": "ok", "verified": True, "message": "Target reached"}
            time.sleep(0.1)
        return {"status": "error", "verified": False, "message": "Timeout — target not reached"}

    def _poll_stopped(self, timeout: float = 3.0) -> Dict:
        """Poll until joint velocities are near zero (robot stopped)."""
        start = time.time()
        while time.time() - start < timeout:
            qd = safe_get(self.robot.rtde_r, "getActualQd")
            if qd and all(abs(v) < 0.001 for v in qd):
                ts = datetime.now().strftime("%H:%M:%S")
                self._log_event(ts, f"✓ Robot stopped", "ok")
                return {"status": "ok", "verified": True, "message": "Robot stopped"}
            time.sleep(0.05)  # Fast poll for safety
        return {"status": "error", "verified": False, "message": "Timeout — robot may still be moving"}

    def shutdown(self):
        self.running = False
        self.camera.stop()
        self.robot.disconnect()
        self.logger.close()


# ══════════════════════════════════════════════════════════════════════════════
#  PLOTLY CHART HELPERS
# ══════════════════════════════════════════════════════════════════════════════

PLOTLY_LAYOUT_BASE = dict(
    template="plotly_dark",
    margin=dict(l=40, r=15, t=30, b=30),
    font=dict(family="Inter, sans-serif", size=10, color="#C9D1D9"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9, color="#8B949E")),
    xaxis=dict(title="", gridcolor="#1C2333", showgrid=True, zeroline=False),
    yaxis=dict(title="", gridcolor="#1C2333", showgrid=True, zeroline=False),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(11,17,32,0.6)",
    height=240,
    hoverlabel=dict(bgcolor="#1C2333", font_size=11, font_family="Inter, sans-serif", bordercolor="#30363D"),
)


def make_joint_pos_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Joint Positions (rad)", font=dict(size=12, color="#E6EDF3"))})
    ts = [s["t"] for s in history]
    for i, jn in enumerate(JOINT_LABELS):
        fig.add_trace(go.Scatter(x=ts, y=[s["q"][i] for s in history], mode="lines",
                                 name=jn, line=dict(color=J_COLORS[i], width=1.5)))
    return fig


def make_joint_vel_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Joint Velocities (rad/s)", font=dict(size=12, color="#E6EDF3"))})
    ts = [s["t"] for s in history]
    for i, jn in enumerate(JOINT_LABELS):
        fig.add_trace(go.Scatter(x=ts, y=[s["qd"][i] for s in history], mode="lines",
                                 name=jn, line=dict(color=J_COLORS[i], width=1.5)))
    return fig


def make_force_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="TCP Force / Torque", font=dict(size=12, color="#E6EDF3"))})
    ts = [s["t"] for s in history]
    for k, c in F_COLORS.items():
        fig.add_trace(go.Scatter(x=ts, y=[s["forces"][k] for s in history], mode="lines",
                                 name=k, line=dict(color=c, width=1.5)))
    return fig


def make_power_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Power Draw (W)", font=dict(size=12, color="#E6EDF3"))})
    ts = [s["t"] for s in history]
    fig.add_trace(go.Scatter(x=ts, y=[s["power"] for s in history], mode="lines",
                             fill="tozeroy", name="Power",
                             line=dict(color="#F8B739", width=2), fillcolor="rgba(248,183,57,0.15)"))
    return fig


def make_energy_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Cumulative Energy (Wh)", font=dict(size=12, color="#E6EDF3"))})
    ts = [s["t"] for s in history]
    fig.add_trace(go.Scatter(x=ts, y=[s["energy"] for s in history], mode="lines",
                             fill="tozeroy", name="Energy",
                             line=dict(color="#00D4AA", width=2), fillcolor="rgba(0,212,170,0.15)"))
    return fig


def make_temp_chart(history: list) -> go.Figure:
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Joint Temperatures (°C)", font=dict(size=12, color="#E6EDF3")),
                            "yaxis": dict(title="", gridcolor="#1C2333", range=[25, 65])})
    ts = [s["t"] for s in history]
    for i, jn in enumerate(JOINT_LABELS):
        fig.add_trace(go.Scatter(x=ts, y=[s["temps"][i] for s in history], mode="lines",
                                 name=jn, line=dict(color=J_COLORS[i], width=1.5)))
    fig.add_hline(y=50, line_dash="dash", line_color="#FBBF24", annotation_text="Warning",
                  annotation_position="top right", annotation_font_size=9, annotation_font_color="#FBBF24")
    return fig


def make_safety_chart(history: list) -> go.Figure:
    """Safety-relevant metrics over time, using only real RTDE data."""
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Safety & Motion Metrics", font=dict(size=12, color="#E6EDF3")),
                            "yaxis": dict(title="", gridcolor="#1C2333")})
    ts = [s["t"] for s in history]
    # Speed scaling: 0-1 from getSpeedScaling (real)
    fig.add_trace(go.Scatter(x=ts, y=[s["speedScaling"] for s in history], mode="lines",
                             name="Speed Scaling", line=dict(color="#4895EF", width=2)))
    # TCP Speed magnitude (m/s * 10 to share scale with speed scaling)
    fig.add_trace(go.Scatter(x=ts, y=[s["tcpSpeed"] * 10 for s in history], mode="lines",
                             name="TCP Speed ×10 (m/s)", line=dict(color="#00D4AA", width=2)))
    # Max joint tracking error magnitude in mrad (real, from actual - target position)
    fig.add_trace(go.Scatter(x=ts,
                             y=[max([abs(e) for e in s["trackErr"]]) * 1000 if s["trackErr"] else 0 for s in history],
                             mode="lines",
                             name="Max Tracking Err (mrad)", line=dict(color="#FBBF24", width=2)))
    return fig


def make_torque_bar(sample: Dict) -> go.Figure:
    pcts = [round(abs(sample["torque"][i]) / MAX_TORQUES[i] * 100, 1) for i in range(6)]
    colors = ["#FF6B6B" if p > 80 else "#FBBF24" if p > 50 else J_COLORS[i] for i, p in enumerate(pcts)]
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Torque Utilization (%)", font=dict(size=12, color="#E6EDF3")),
                            "xaxis": dict(range=[0, 100], title=""), "height": 220})
    fig.add_trace(go.Bar(y=JOINT_LABELS, x=pcts, orientation="h", marker_color=colors,
                         text=[f"{p}%" for p in pcts], textposition="auto"))
    return fig


def make_tracking_error_chart(sample: Dict) -> go.Figure:
    errs = [round(abs(sample["trackErr"][i]) * 1000, 2) for i in range(6)]
    colors = ["#FF6B6B" if e > 1.0 else "#FBBF24" if e > 0.5 else J_COLORS[i] for i, e in enumerate(errs)]
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Tracking Error (mrad)", font=dict(size=12, color="#E6EDF3")),
                            "yaxis": dict(title="", gridcolor="#1C2333"), "height": 220})
    fig.add_trace(go.Bar(x=JOINT_LABELS, y=errs, marker_color=colors,
                         text=[f"{e:.2f}" for e in errs], textposition="auto",
                         textfont=dict(color="#E6EDF3", size=10)))
    return fig


def make_radar_chart(sample: Dict) -> go.Figure:
    cats = JOINT_LABELS + [JOINT_LABELS[0]]
    pos = [abs(sample["q"][i]) / 6.28 * 100 for i in range(6)] + [abs(sample["q"][0]) / 6.28 * 100]
    vel = [abs(sample["qd"][i]) / 3.14 * 100 for i in range(6)] + [abs(sample["qd"][0]) / 3.14 * 100]
    cur = [sample["cur"][i] / 5 * 100 for i in range(6)] + [sample["cur"][0] / 5 * 100]
    fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Joint Radar", font=dict(size=12, color="#E6EDF3")),
                            "polar": dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(visible=True, range=[0, 100], gridcolor="#1C2333", tickfont=dict(color="#8B949E")), angularaxis=dict(gridcolor="#1C2333", tickfont=dict(color="#8B949E"))), "height": 240})
    fig.add_trace(go.Scatterpolar(r=pos, theta=cats, fill="toself", name="Position", opacity=0.4, line_color="#00D4AA"))
    fig.add_trace(go.Scatterpolar(r=vel, theta=cats, fill="toself", name="Velocity", opacity=0.3, line_color="#4895EF"))
    fig.add_trace(go.Scatterpolar(r=cur, theta=cats, fill="toself", name="Current", opacity=0.2, line_color="#FF6B6B"))
    return fig


def make_gauge(value, title, max_val, color="#4895EF", warn=None, crit=None) -> go.Figure:
    bar_color = "#FF6B6B" if (crit and value >= crit) else "#FBBF24" if (warn and value >= warn) else color
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, title=dict(text=title, font=dict(size=11, color="#C9D1D9")),
        number=dict(font=dict(size=18, color="#E6EDF3")),
        gauge=dict(
            axis=dict(range=[0, max_val], tickfont=dict(size=8, color="#8B949E"), tickcolor="#30363D"),
            bar=dict(color=bar_color),
            bgcolor="#0D1117",
            borderwidth=0,
            steps=[
                dict(range=[0, max_val * 0.5], color="rgba(0,212,170,0.08)"),
                dict(range=[max_val * 0.5, max_val * 0.8], color="rgba(251,191,36,0.10)" if warn else "rgba(0,212,170,0.08)"),
                dict(range=[max_val * 0.8, max_val], color="rgba(255,107,107,0.12)" if crit else "rgba(0,212,170,0.08)"),
            ],
            threshold=dict(line=dict(color="#FF6B6B", width=2), thickness=0.75, value=crit if crit else max_val) if crit else None,
        ),
    ))
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=10), height=160, paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#C9D1D9"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  NICEGUI DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

# Global CSS
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root {
    --bg: #0B1120; --card: #111827; --border: #1E293B; --text: #E6EDF3;
    --muted: #8B949E; --subtle: #6E7681; --accent: #4895EF;
    --green: #00D4AA; --orange: #FBBF24; --red: #FF6B6B; --purple: #7B61FF;
    --teal: #00D4AA; --dark: #0D1117;
}
body { font-family: 'Inter', sans-serif !important; background: var(--bg) !important; color: var(--text) !important; }
.q-tab { text-transform: uppercase !important; letter-spacing: 0.5px !important; font-size: 12px !important;
    font-weight: 600 !important; color: var(--muted) !important; }
.q-tab--active { color: var(--accent) !important; }
.q-tabs__content { background: var(--card) !important; }
.q-tab-panel { background: transparent !important; }
.q-tab-panels { background: transparent !important; }
.q-table { background: var(--card) !important; color: var(--text) !important; }
.q-table th { background: #0D1117 !important; color: var(--muted) !important; border-color: var(--border) !important; }
.q-table td { border-color: var(--border) !important; color: var(--text) !important; }
.q-table tbody tr:hover { background: rgba(72,149,239,0.06) !important; }
.q-field__control { background: #1C2333 !important; color: var(--text) !important; }
.q-field__label { color: var(--muted) !important; }
.q-field__native { color: var(--text) !important; }
.q-slider__track-container { color: var(--accent) !important; }
.q-toggle__inner { color: var(--accent) !important; }
.q-btn-toggle { border-color: var(--border) !important; }
.q-btn-toggle .q-btn { color: var(--muted) !important; background: var(--card) !important; }
.q-btn-toggle .q-btn--active { color: var(--text) !important; background: var(--accent) !important; }
.nicegui-content { padding: 0 !important; }
.kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.kpi-label { font-size: 10.5px; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase; }
.kpi-value { font-size: 22px; font-weight: 700; color: var(--text); font-family: 'JetBrains Mono', monospace; }
.kpi-unit { font-size: 11px; color: var(--muted); }
.section-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.section-header { padding: 10px 16px; border-bottom: 1px solid var(--border); background: #0D1117;
    font-size: 11.5px; font-weight: 700; color: var(--text); letter-spacing: 0.8px; text-transform: uppercase; }
.ctrl-log { background: #0D1117; border: 1px solid var(--border); border-radius: 8px; padding: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 10.5px; max-height: 260px; overflow-y: auto; }
.status-badge { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 8px; }
.bit-indicator { display: flex; align-items: center; gap: 8px; padding: 5px 10px; border-radius: 6px;
    font-size: 10.5px; border: 1px solid var(--border); }
.dark-panel { background: #0d1117; border: 1px solid #1E293B; border-radius: 12px; overflow: hidden; }
.dark-panel-header { padding: 10px 16px; background: linear-gradient(135deg, #0d1117, #161b22);
    border-bottom: 1px solid #1E293B; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.fs-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid transparent; background: transparent;
    cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s;
    color: #8b949e; font-size: 15px; padding: 0; flex-shrink: 0; }
.fs-btn:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.15); }
.fs-btn.light { color: var(--muted); }
.fs-btn.light:hover { background: rgba(255,255,255,0.08); border-color: var(--border); }
.fs-panel:fullscreen, .fs-panel:-webkit-full-screen { width: 100vw !important; height: 100vh !important;
    border-radius: 0 !important; z-index: 9999; }
.fs-panel:fullscreen .dark-panel-header, .fs-panel:-webkit-full-screen .dark-panel-header,
.fs-panel:fullscreen .section-header-row, .fs-panel:-webkit-full-screen .section-header-row { flex-shrink: 0; }
*::-webkit-scrollbar { width: 6px; }
*::-webkit-scrollbar-track { background: var(--bg); }
*::-webkit-scrollbar-thumb { background: #30363D; border-radius: 3px; }
*::-webkit-scrollbar-thumb:hover { background: #484F58; }
"""

FULLSCREEN_JS = """
function toggleFullscreen(el) {
    if (!document.fullscreenElement) {
        el.requestFullscreen().catch(function(err) { console.log('Fullscreen error:', err); });
    } else {
        document.exitFullscreen();
    }
}
"""


def build_dashboard(state: AppState):
    """Build the NiceGUI dashboard page."""

    # ── Inject custom styles and fullscreen JS ──
    ui.add_head_html(f"<style>{CSS}</style>")
    ui.add_body_html(f"<script>{FULLSCREEN_JS}</script>")

    # ── HEADER ──
    with ui.element("div").style(
        "background: linear-gradient(135deg, #0B1120 0%, #111827 50%, #0D1117 100%); padding: 14px 24px;"
        "display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #4895EF;"
    ):
        with ui.column().style("gap: 2px"):
            ui.label("UR5e RTDE Monitoring Dashboard").style(
                "font-size: 17px; font-weight: 700; color: white; letter-spacing: 0.5px")
            with ui.row().style("gap: 12px; align-items: center"):
                ui.label("Real-Time Data Exchange — 270 Parameters").style(
                    "font-size: 11px; color: #8B949E; letter-spacing: 0.3px")
                mode_badge = ui.label("● DEMO").style(
                    "padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600;"
                    "background: #FBBF2430; color: #FBBF24;")

        with ui.row().style("gap: 10px; align-items: center"):
            robot_badge = ui.label("UNKNOWN").style(
                "padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"
                "background: rgba(251,191,36,0.08); color: var(--text); border: 1px solid rgba(251,191,36,0.2);")
            safety_badge = ui.label("UNKNOWN").style(
                "padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600;"
                "background: rgba(0,212,170,0.08); color: var(--text); border: 1px solid rgba(0,212,170,0.2);")
            elapsed_label = ui.label("0:00").style(
                "padding: 8px 14px; border-radius: 8px; font-size: 15px; font-weight: 700;"
                "font-family: 'JetBrains Mono', monospace; color: white;"
                "background: rgba(72,149,239,0.15); border: 1px solid rgba(72,149,239,0.3);")

    # ── TABS ──
    with ui.tabs().classes("w-full").style("background: #111827; border-bottom: 1px solid #1E293B; padding: 0 24px;") as tabs:
        tab_overview  = ui.tab("Overview")
        tab_joints    = ui.tab("Joint Analysis")
        tab_tcp       = ui.tab("TCP & Force")
        tab_power     = ui.tab("Power & Thermal")
        tab_safety    = ui.tab("Safety & Status")
        tab_control   = ui.tab("Robot Control")
        tab_twin      = ui.tab("Digital Twin")

    # ── CONTENT PANELS ──
    with ui.tab_panels(tabs, value=tab_overview).classes("w-full").style(
            "max-width: 1440px; margin: 0 auto; padding: 16px 24px; background: transparent;"):

        # ═══════════════════════════════════════════════════════════════
        #  TAB 0: OVERVIEW
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_overview):
            with ui.row().classes("w-full").style("gap: 12px; flex-wrap: wrap"):
                kpi_speed  = _kpi("TCP Speed",  "—", "m/s")
                kpi_force  = _kpi("Force",      "—", "N")
                kpi_power  = _kpi("Power Draw", "—", "W")
                kpi_temp   = _kpi("Max Temp",   "—", "°C")
                kpi_energy = _kpi("Energy",     "—", "Wh")
                kpi_vib    = _kpi("Vibration",  "—", "m/s²")

            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                gauge_scaling   = ui.plotly(make_gauge(0, "Speed Scaling", 1, "#4895EF")).classes("flex-1")
                gauge_current   = ui.plotly(make_gauge(0, "Robot Current", 10, "#00D4AA", 7, 9)).classes("flex-1")
                gauge_maxtemp   = ui.plotly(make_gauge(0, "Max Joint Temp", 80, "#4895EF", 50, 70)).classes("flex-1")
                gauge_momentum  = ui.plotly(make_gauge(0, "Momentum", 25, "#7B61FF", 15, 20)).classes("flex-1")
                gauge_payload   = ui.plotly(make_gauge(0, "Payload", 5, "#4895EF", 4.5, 5.0)).classes("flex-1")

            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_jpos_overview = ui.plotly(make_joint_pos_chart([])).classes("flex-1")
                chart_force_overview = ui.plotly(make_force_chart([])).classes("flex-1")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 1: JOINT ANALYSIS
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_joints):
            with ui.row().classes("w-full").style("gap: 12px"):
                chart_jpos = ui.plotly(make_joint_pos_chart([])).classes("flex-1")
                chart_jvel = ui.plotly(make_joint_vel_chart([])).classes("flex-1")
            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_torque_bar = ui.plotly(make_torque_bar(generate_demo(0))).classes("flex-1")
                chart_track_err = ui.plotly(make_tracking_error_chart(generate_demo(0))).classes("flex-1")
                chart_radar = ui.plotly(make_radar_chart(generate_demo(0))).classes("flex-1")

            # Joint state table
            with ui.element("div").classes("section-card").style("margin-top: 12px"):
                ui.label("Current Joint State").classes("section-header")
                joint_table = ui.table(
                    columns=[
                        {"name": "joint", "label": "Joint", "field": "joint", "align": "left"},
                        {"name": "pos", "label": "Position (rad)", "field": "pos", "align": "right"},
                        {"name": "vel", "label": "Velocity (rad/s)", "field": "vel", "align": "right"},
                        {"name": "cur", "label": "Current (A)", "field": "cur", "align": "right"},
                        {"name": "torque", "label": "Torque (Nm)", "field": "torque", "align": "right"},
                        {"name": "temp", "label": "Temp (°C)", "field": "temp", "align": "right"},
                        {"name": "err", "label": "Track Err (mrad)", "field": "err", "align": "right"},
                    ],
                    rows=[{"joint": JOINT_LABELS[i], "pos": "—", "vel": "—", "cur": "—",
                           "torque": "—", "temp": "—", "err": "—"} for i in range(6)],
                ).style("width: 100%")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 2: TCP & FORCE
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_tcp):
            tcp_kpi_labels = {}
            with ui.row().classes("w-full").style("gap: 12px"):
                for a in ["x", "y", "z", "rx", "ry", "rz"]:
                    tcp_kpi_labels[a] = _kpi(f"TCP {a.upper()}", "—", "m" if a in "xyz" else "rad")
            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_force_detail = ui.plotly(make_force_chart([])).classes("flex-[2]")
                gauge_force_scalar = ui.plotly(make_gauge(0, "Force Magnitude", 150, "#FF6B6B", 80, 120)).classes("flex-1")
            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_tcp_speed = ui.plotly(go.Figure(layout={**PLOTLY_LAYOUT_BASE,
                    "title": dict(text="TCP Speed (m/s)", font=dict(size=12, color="#E6EDF3"))})).classes("flex-1")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 3: POWER & THERMAL
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_power):
            with ui.row().classes("w-full").style("gap: 12px"):
                kpi_v48   = _kpi("48V Bus",     "—", "V")
                kpi_ibot  = _kpi("Robot Current","—", "A")
                kpi_pow2  = _kpi("Power",       "—", "W")
                kpi_en2   = _kpi("Energy",      "—", "Wh")
                kpi_mom2  = _kpi("Momentum",    "—", "kg·m/s")
            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_power = ui.plotly(make_power_chart([])).classes("flex-1")
                chart_energy = ui.plotly(make_energy_chart([])).classes("flex-1")
            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_temp = ui.plotly(make_temp_chart([])).classes("flex-[2]")
                chart_temp_bar = ui.plotly(go.Figure(layout={**PLOTLY_LAYOUT_BASE,
                    "title": dict(text="Current Temperature (°C)", font=dict(size=12, color="#E6EDF3"))})).classes("flex-1")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 4: SAFETY & STATUS
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_safety):
            with ui.row().classes("w-full").style("gap: 12px"):
                kpi_pstop = _kpi("Protective Stops", "0", "events")
                kpi_estop = _kpi("Emergency Stops", "0", "events")
                kpi_viol  = _kpi("Violations", "0", "events")
                kpi_scl   = _kpi("Speed Scaling", "—", "")

            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                gauge_maxcur2    = ui.plotly(make_gauge(0, "Max Joint Current", 5, "#00D4AA", 3, 4.5)).classes("flex-1")
                gauge_maxtemp2   = ui.plotly(make_gauge(0, "Max Joint Temp", 80, "#4895EF", 50, 70)).classes("flex-1")
                gauge_momentum2  = ui.plotly(make_gauge(0, "Momentum", 25, "#7B61FF", 15, 20)).classes("flex-1")

            with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                chart_safety = ui.plotly(make_safety_chart([])).classes("flex-1")
                with ui.element("div").classes("section-card flex-1"):
                    ui.label("Safety Status Bits").classes("section-header")
                    safety_bits_content = ui.html("").style("padding: 12px")

            with ui.element("div").classes("section-card").style("margin-top: 12px"):
                ui.label("Robot Status Bits").classes("section-header")
                robot_bits_content = ui.html("").style("padding: 12px")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 5: ROBOT CONTROL
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_control):
            # Emergency stop bar
            with ui.row().classes("w-full").style("gap: 12px; align-items: stretch"):
                async def _estop_main():
                    await run.io_bound(state.send_command, "stopJ", {})
                    await run.io_bound(state.send_command, "stopScript", {})
                ui.button("⚠ EMERGENCY STOP", on_click=_estop_main).style(
                    "flex: 0 0 200px; padding: 16px 24px; font-size: 16px; font-weight: 800;"
                    "color: white; background: linear-gradient(135deg, #DC2626, #EF4444);"
                    "border: 3px solid #991B1B; border-radius: 12px; letter-spacing: 1px;"
                    "box-shadow: 0 4px 20px rgba(220,38,38,0.4);")

                with ui.row().style("flex: 1; gap: 8px; flex-wrap: wrap"):
                    _ctrl_btn("⚡ Power On",     lambda: state.send_command("powerOn"),             "#00D4AA")
                    _ctrl_btn("⏻ Power Off",     lambda: state.send_command("powerOff"),            "#6E7681")
                    _ctrl_btn("🔓 Brake Release", lambda: state.send_command("brakeRelease"),       "#4895EF")
                    _ctrl_btn("🔑 Unlock P-Stop", lambda: state.send_command("unlockProtectiveStop"), "#FBBF24")
                    _ctrl_btn("🔄 Restart Safety", lambda: state.send_command("restartSafety"),     "#7B61FF")

            # Control sub-tabs
            with ui.tabs().classes("w-full").style("margin-top: 12px") as ctrl_tabs:
                ctrl_tab_jog  = ui.tab("Jog & Move")
                ctrl_tab_io   = ui.tab("I/O Control")
                ctrl_tab_set  = ui.tab("Settings & Tools")

            # ── Live State Summary (TCP + Speed + Force) ──
            with ui.row().classes("w-full").style("gap: 8px; margin-top: 12px"):
                ctrl_tcp_labels = {}
                for a in ["x", "y", "z", "rx", "ry", "rz"]:
                    with ui.element("div").style(
                        "flex: 1; padding: 8px 10px; background: #111827; border-radius: 8px;"
                        "border: 1px solid #1E293B; text-align: center;"):
                        ui.label(f"TCP {a.upper()}").style(
                            "font-size: 9px; color: #8B949E; text-transform: uppercase; letter-spacing: 0.5px")
                        ctrl_tcp_labels[a] = ui.label("—").style(
                            "font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #E6EDF3")
                        ui.label("m" if a in "xyz" else "rad").style("font-size: 9px; color: #6E7681")
                with ui.element("div").style(
                    "flex: 1; padding: 8px 10px; background: #fff; border-radius: 8px;"
                    "border: 1px solid #e4e9f0; text-align: center;"):
                    ui.label("SPEED").style("font-size: 9px; color: #8B949E; text-transform: uppercase; letter-spacing: 0.5px")
                    ctrl_speed_label = ui.label("—").style(
                        "font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #E6EDF3")
                    ui.label("m/s").style("font-size: 9px; color: #6E7681")
                with ui.element("div").style(
                    "flex: 1; padding: 8px 10px; background: #fff; border-radius: 8px;"
                    "border: 1px solid #e4e9f0; text-align: center;"):
                    ui.label("FORCE").style("font-size: 9px; color: #8B949E; text-transform: uppercase; letter-spacing: 0.5px")
                    ctrl_force_label = ui.label("—").style(
                        "font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #E6EDF3")
                    ui.label("N").style("font-size: 9px; color: #6E7681")

            with ui.tab_panels(ctrl_tabs, value=ctrl_tab_jog).classes("w-full"):

                # ── Jog & Move ──
                with ui.tab_panel(ctrl_tab_jog):
                    with ui.row().classes("w-full").style("gap: 12px"):

                        # Joint Jog
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🦾 Joint Jog").classes("section-header")
                            with ui.column().style("padding: 16px; gap: 8px"):
                                with ui.row().style("gap: 12px"):
                                    jog_speed_input = ui.number("Jog Speed (rad/s)", value=0.1, min=0.01, max=3.14, step=0.01).style("width: 140px")
                                    jog_accel_input = ui.number("Acceleration (rad/s²)", value=0.5, min=0.1, max=5.0, step=0.1).style("width: 160px")
                                jog_pos_label_refs = []
                                for i, jn in enumerate(JOINT_LABELS):
                                    with ui.row().style("align-items: center; gap: 8px"):
                                        ui.label(jn).style(f"width: 70px; font-weight: 600; color: {J_COLORS[i]}; font-size: 12px")
                                        _jog_btn("−", state, i, -1, jog_speed_input, jog_accel_input)
                                        jpl = ui.label("0.0000 rad").style(
                                            "flex: 1; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 12px")
                                        jog_pos_label_refs.append(jpl)
                                        _jog_btn("+", state, i, 1, jog_speed_input, jog_accel_input)

                        # Cartesian Jog
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🎯 Cartesian Jog").classes("section-header")
                            with ui.column().style("padding: 16px; gap: 8px"):
                                with ui.row().style("gap: 12px"):
                                    cart_speed_input = ui.number("Speed (m/s)", value=0.1, min=0.001, max=0.5, step=0.001).style("width: 120px")
                                    cart_accel_input = ui.number("Accel (m/s²)", value=0.5, min=0.1, max=5.0, step=0.1).style("width: 120px")
                                cart_pos_label_refs = []
                                for i, ax in enumerate(["X", "Y", "Z", "Rx", "Ry", "Rz"]):
                                    color = "#4895EF" if i < 3 else "#7B61FF"
                                    with ui.row().style("align-items: center; gap: 8px"):
                                        ui.label(ax).style(f"width: 30px; font-weight: 700; color: {color};"
                                                          "font-family: 'JetBrains Mono', monospace; font-size: 12px")
                                        _cart_jog_btn("−", state, i, -1, cart_speed_input, cart_accel_input)
                                        cpl = ui.label("0.0000").style(
                                            "flex: 1; text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 12px")
                                        cart_pos_label_refs.append(cpl)
                                        _cart_jog_btn("+", state, i, 1, cart_speed_input, cart_accel_input)

                    # Move Command
                    with ui.element("div").classes("section-card").style("margin-top: 12px"):
                        ui.label("📍 Move Command").classes("section-header")
                        with ui.row().style("padding: 16px; gap: 12px; align-items: flex-end; flex-wrap: wrap"):
                            move_mode = ui.toggle(["moveJ", "moveL"], value="moveJ").style("font-family: 'JetBrains Mono', monospace")
                            move_speed = ui.number("Speed", value=0.5, step=0.01).style("width: 80px")
                            move_accel = ui.number("Accel", value=1.0, step=0.1).style("width: 80px")
                            move_targets = [ui.number(JOINT_LABELS[i] if True else ["X","Y","Z","Rx","Ry","Rz"][i],
                                                      value=[-0.0, -1.57, 0, 0, 1.57, 0][i], step=0.001).style("width: 80px")
                                           for i in range(6)]
                            async def _exec_move():
                                await run.io_bound(state.send_command,
                                    move_mode.value, {"target": [mt.value for mt in move_targets],
                                                      "speed": move_speed.value, "acceleration": move_accel.value})
                            ui.button("▶ Execute", on_click=_exec_move).style("background: #00D4AA; color: #0B1120; font-weight: 600")

                            def _copy_current():
                                s = state.sample
                                if not s:
                                    return
                                if move_mode.value == "moveJ":
                                    for i in range(6):
                                        move_targets[i].value = round(s["q"][i], 4)
                                else:
                                    axes = ["x", "y", "z", "rx", "ry", "rz"]
                                    for i in range(6):
                                        move_targets[i].value = round(s["tcp"].get(axes[i], 0), 4)
                                move_targets[0].update()  # trigger UI refresh
                                state._log_event(datetime.now().strftime("%H:%M:%S"), "Copied current position to target", "info")

                            ui.button("📋 Copy Current", on_click=_copy_current).style(
                                "background: #6E7681; color: white; font-weight: 600")

                    # Speed Slider + Freedrive
                    with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("⚡ Speed Slider").classes("section-header")
                            with ui.column().style("padding: 16px"):
                                speed_slider_label = ui.label("100%").style(
                                    "font-size: 20px; font-weight: 700; font-family: 'JetBrains Mono', monospace")
                                async def _speed_slider_change(e):
                                    speed_slider_label.set_text(f"{int(e.value * 100)}%")
                                    await run.io_bound(state.send_command, "setSpeedSlider", {"speed": e.value})
                                speed_slider = ui.slider(min=0, max=1, step=0.01, value=1.0,
                                    on_change=_speed_slider_change).style("width: 100%")

                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("✋ Freedrive / Teach Mode").classes("section-header")
                            with ui.column().style("padding: 16px; gap: 8px"):
                                freedrive_btn = ui.button("Enable Freedrive")
                                async def _freedrive_handler():
                                    await _toggle_freedrive(state, freedrive_btn)
                                freedrive_btn.on_click(_freedrive_handler)
                                freedrive_btn.style("background: #7B61FF; color: white; font-weight: 600; padding: 12px 24px")

                    # Program Control + Log
                    with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("📋 Program Control").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 8px"):
                                _ctrl_btn("▶ Play",   lambda: state.send_command("play"),   "#00D4AA")
                                _ctrl_btn("⏸ Pause",  lambda: state.send_command("pause"),  "#FBBF24")
                                _ctrl_btn("⏹ Stop",   lambda: state.send_command("stop"),   "#FF6B6B")
                                _ctrl_btn("🔄 Re-upload Script", lambda: state.send_command("reuploadScript"), "#4895EF")
                                _ctrl_btn("⊘ Zero F/T", lambda: state.send_command("zeroFtSensor"), "#6E7681")

                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("📜 Command Log").classes("section-header")
                            ctrl_log_container = ui.element("div").classes("ctrl-log").style("margin: 12px")
                            ctrl_log_content = ui.html("").style("color: #8B949E")

                # ── I/O Control ──
                with ui.tab_panel(ctrl_tab_io):
                    with ui.row().classes("w-full").style("gap: 12px"):
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🔌 Standard Digital Outputs (0–7)").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 8px; flex-wrap: wrap"):
                                for i in range(8):
                                    _dio_switch(f"DO {i}", state, "setStandardDigitalOut", i)

                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🔌 Configurable Digital Outputs (0–7)").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 8px; flex-wrap: wrap"):
                                for i in range(8):
                                    _dio_switch(f"CDO {i}", state, "setConfigurableDigitalOut", i)

                    with ui.row().classes("w-full").style("gap: 12px; margin-top: 12px"):
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🔧 Tool Digital Outputs (0–1)").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 16px"):
                                _dio_switch("TDO 0", state, "setToolDigitalOut", 0)
                                _dio_switch("TDO 1", state, "setToolDigitalOut", 1)

                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("📊 Analog Outputs").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 24px"):
                                with ui.column().style("flex: 1"):
                                    ao0_label = ui.label("AO 0 — 0%").style("font-size: 10px; color: var(--muted)")
                                    ui.slider(min=0, max=1, step=0.01, value=0,
                                        on_change=lambda e: (
                                            ao0_label.set_text(f"AO 0 — {int(e.value*100)}%"),
                                            state.send_command("setAnalogOutputVoltage", {"id": 0, "ratio": e.value})
                                        ))
                                with ui.column().style("flex: 1"):
                                    ao1_label = ui.label("AO 1 — 0%").style("font-size: 10px; color: var(--muted)")
                                    ui.slider(min=0, max=1, step=0.01, value=0,
                                        on_change=lambda e: (
                                            ao1_label.set_text(f"AO 1 — {int(e.value*100)}%"),
                                            state.send_command("setAnalogOutputVoltage", {"id": 1, "ratio": e.value})
                                        ))

                # ── Settings & Tools ──
                with ui.tab_panel(ctrl_tab_set):
                    with ui.row().classes("w-full").style("gap: 12px"):
                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("⚖ Payload Configuration").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 12px; align-items: flex-end; flex-wrap: wrap"):
                                pl_mass = ui.number("Mass (kg)", value=0, min=0, max=5, step=0.01).style("width: 90px")
                                pl_cx = ui.number("CoG X (m)", value=0, step=0.001).style("width: 90px")
                                pl_cy = ui.number("CoG Y (m)", value=0, step=0.001).style("width: 90px")
                                pl_cz = ui.number("CoG Z (m)", value=0, step=0.001).style("width: 90px")
                                async def _set_payload():
                                    await run.io_bound(state.send_command,
                                        "setPayload", {"mass": pl_mass.value, "cog": [pl_cx.value, pl_cy.value, pl_cz.value]})
                                ui.button("Set Payload", on_click=_set_payload).style("background: #4895EF; color: white; font-weight: 600")

                        with ui.element("div").classes("section-card flex-1"):
                            ui.label("🎯 TCP Offset").classes("section-header")
                            with ui.row().style("padding: 16px; gap: 12px; align-items: flex-end; flex-wrap: wrap"):
                                tcp_inputs = [ui.number(a, value=0, step=0.001).style("width: 70px")
                                             for a in ["X", "Y", "Z", "Rx", "Ry", "Rz"]]
                                async def _set_tcp():
                                    await run.io_bound(state.send_command,
                                        "setTcp", {"offset": [inp.value for inp in tcp_inputs]})
                                ui.button("Set TCP", on_click=_set_tcp).style("background: #00D4AA; color: #0B1120; font-weight: 600")

        # ═══════════════════════════════════════════════════════════════
        #  TAB 6: DIGITAL TWIN
        # ═══════════════════════════════════════════════════════════════
        with ui.tab_panel(tab_twin):
            with ui.element("div").style(
                "display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;"
                "gap: 12px; height: calc(100vh - 200px); min-height: 560px;"
            ):
                # ── Top-Left: Emulation Twin (Isaac Sim Viewport) ──
                with ui.element("div").classes("dark-panel fs-panel").style("display: flex; flex-direction: column") as panel_twin:
                    with ui.element("div").classes("dark-panel-header").style(
                        "display: flex; align-items: center; justify-content: space-between"):
                        with ui.row().style("gap: 8px; align-items: center"):
                            ui.label("🌐").style("font-size: 14px")
                            ui.label("ISAAC SIM — DIGITAL TWIN").style(
                                "font-size: 11.5px; font-weight: 700; color: #e6edf3; letter-spacing: 0.8px")
                        with ui.row().style("gap: 6px; align-items: center"):
                            twin_status_label = ui.label("CONNECTING").style(
                                "padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                "background: rgba(251,191,36,0.15); color: #FBBF24; border: 1px solid rgba(251,191,36,0.3);")
                            _fullscreen_btn(panel_twin, dark=True)

                    twin_feed_img = ui.image("http://localhost:8211/feed").style(
                        "flex: 1; object-fit: contain; background: #000; min-height: 0;")

                    async def _check_twin_stream():
                        import aiohttp
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get("http://localhost:8211/snapshot", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                                    if resp.status == 200:
                                        twin_status_label.set_text("● LIVE")
                                        twin_status_label.style(
                                            "padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                            "background: rgba(0,212,170,0.15); color: #00D4AA; border: 1px solid rgba(0,212,170,0.3);")
                                    else:
                                        twin_status_label.set_text("OFFLINE")
                                        twin_status_label.style(
                                            "padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                            "background: #1f293780; color: #8b949e; border: 1px solid #30363d;")
                        except Exception:
                            twin_status_label.set_text("OFFLINE")
                            twin_status_label.style(
                                "padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                "background: #1f293780; color: #8b949e; border: 1px solid #30363d;")

                    ui.timer(5.0, _check_twin_stream)

                # ── Top-Right: RealSense L515 ──
                with ui.element("div").classes("dark-panel fs-panel").style("display: flex; flex-direction: column") as panel_cam:
                    with ui.element("div").classes("dark-panel-header").style(
                        "display: flex; align-items: center; justify-content: space-between"):
                        with ui.row().style("gap: 8px; align-items: center"):
                            ui.label("📷").style("font-size: 14px")
                            ui.label("REALSENSE L515 — 1080p").style(
                                "font-size: 11.5px; font-weight: 700; color: #e6edf3; letter-spacing: 0.8px")
                        with ui.row().style("gap: 6px; align-items: center"):
                            _as = ("padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                   "border: 1px solid #e6edf3; background: rgba(230,237,243,0.13); color: #e6edf3; cursor: pointer;")
                            _is = ("padding: 3px 10px; border-radius: 4px; font-size: 9.5px; font-weight: 600;"
                                   "border: 1px solid #30363d; background: rgba(31,41,55,0.5); color: #8b949e; cursor: pointer;")

                            cam_btn_rgb = ui.button("RGB").style(_as)
                            cam_btn_depth = ui.button("Depth").style(_is)
                            cam_btn_both = ui.button("Both").style(_is)

                            def _switch_feed(feed):
                                feeds = {"color": "/video_feed", "depth": "/depth_feed", "combined": "/combined_feed"}
                                cam_feed_img.set_source(feeds[feed])
                                cam_btn_rgb.style(_as if feed == "color" else _is)
                                cam_btn_depth.style(_as if feed == "depth" else _is)
                                cam_btn_both.style(_as if feed == "combined" else _is)

                            cam_btn_rgb.on("click", lambda: _switch_feed("color"))
                            cam_btn_depth.on("click", lambda: _switch_feed("depth"))
                            cam_btn_both.on("click", lambda: _switch_feed("combined"))

                            ui.element("div").style(
                                "width: 8px; height: 8px; border-radius: 50%; background: #FF6B6B;"
                                "animation: pulse 2s infinite; margin-left: 6px;")
                            ui.label("LIVE").style("font-size: 10px; color: #FF6B6B; font-weight: 600")
                            _fullscreen_btn(panel_cam, dark=True)

                    with ui.element("div").style(
                        "flex: 1; background: #000; overflow: hidden; display: flex;"
                        "align-items: center; justify-content: center;"):
                        cam_feed_img = ui.image("/video_feed").style(
                            "width: 100%; height: 100%; object-fit: contain;")

                # ── Bottom-Left: Telemetry ──
                with ui.element("div").classes("section-card fs-panel").style("display: flex; flex-direction: column") as panel_telem:
                    with ui.element("div").style(
                        "padding: 10px 16px; background: #0D1117; border-bottom: 1px solid #1E293B;"
                        "display: flex; align-items: center; justify-content: space-between;"):
                        with ui.row().style("gap: 8px; align-items: center"):
                            ui.label("📊").style("font-size: 14px")
                            ui.label("TELEMETRY").style(
                                "font-size: 11.5px; font-weight: 700; color: var(--text); letter-spacing: 0.8px")
                        with ui.row().style("gap: 8px; align-items: center"):
                            twin_elapsed_label = ui.label("0.0s").style(
                                "font-size: 10px; color: var(--subtle); font-family: 'JetBrains Mono', monospace")
                            _fullscreen_btn(panel_telem, dark=False)

                    with ui.column().style("flex: 1; padding: 14px; gap: 10px; overflow-y: auto"):
                        # Safety status bar
                        twin_safety_bar = ui.element("div").style(
                            "padding: 8px 12px; border-radius: 8px; background: rgba(0,212,170,0.08); border: 1px solid rgba(0,212,170,0.2);"
                            "display: flex; align-items: center; justify-content: space-between;")
                        with twin_safety_bar:
                            with ui.row().style("gap: 8px; align-items: center"):
                                twin_safety_dot = ui.element("div").style(
                                    "width: 10px; height: 10px; border-radius: 50%; background: #00D4AA;")
                                twin_safety_label = ui.label("ZONE CLEAR").style(
                                    "font-size: 11px; font-weight: 700; color: #E6EDF3; letter-spacing: 0.5px")
                            twin_safety_dist = ui.label("—").style(
                                "font-size: 10px; color: var(--muted); font-family: 'JetBrains Mono', monospace")

                        with ui.row().style("gap: 8px"):
                            twin_kpi_speed = _kpi_mini("TCP Speed", "—", "m/s")
                            twin_kpi_force = _kpi_mini("Force", "—", "N")
                            twin_kpi_power = _kpi_mini("Power", "—", "W")

                        with ui.row().style("gap: 8px"):
                            twin_gauge_temp = ui.plotly(make_gauge(0, "Max Temp", 85, "#F8B739", 50, 70)).classes("flex-1")
                            twin_gauge_cur  = ui.plotly(make_gauge(0, "Max Current", 5, "#00D4AA", 3, 4.5)).classes("flex-1")
                            twin_gauge_mom  = ui.plotly(make_gauge(0, "Momentum", 25, "#7B61FF", 15, 20)).classes("flex-1")

                        twin_chart_force = ui.plotly(make_force_chart([])).classes("flex-1").style("min-height: 100px")

                # ── Bottom-Right: Control ──
                with ui.element("div").classes("section-card fs-panel").style("display: flex; flex-direction: column") as panel_ctrl:
                    with ui.element("div").style(
                        "padding: 10px 16px; background: #0D1117; border-bottom: 1px solid #1E293B;"
                        "display: flex; align-items: center; justify-content: space-between;"):
                        with ui.row().style("gap: 8px; align-items: center"):
                            ui.label("🎮").style("font-size: 14px")
                            ui.label("CONTROL").style(
                                "font-size: 11.5px; font-weight: 700; color: var(--text); letter-spacing: 0.8px")
                        with ui.row().style("gap: 8px; align-items: center"):
                            twin_robot_badge = ui.label("UNKNOWN").style(
                                "padding: 4px 10px; border-radius: 6px; font-size: 10px; font-weight: 600;"
                                "background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.2);")
                            _fullscreen_btn(panel_ctrl, dark=False)

                    with ui.column().style("flex: 1; padding: 14px; gap: 10px; overflow-y: auto"):
                        # Emergency Stop — ALWAYS available, never locked, uses verified stop
                        with ui.element("div").style("position: relative"):
                            estop_btn = ui.button("⚠ EMERGENCY STOP").style(
                                "width: 100%; padding: 12px; font-size: 14px; font-weight: 800;"
                                "color: white; background: linear-gradient(135deg, #DC2626, #EF4444);"
                                "border: 3px solid #991B1B; border-radius: 10px;"
                                "box-shadow: 0 4px 20px rgba(220,38,38,0.4);")
                            estop_indicator = ui.label("").style(
                                "position: absolute; top: -6px; right: -6px; width: 22px; height: 22px;"
                                "border-radius: 50%; display: none; align-items: center; justify-content: center;"
                                "font-size: 13px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);")

                            async def _estop_click():
                                # E-Stop ALWAYS fires, even if panel is locked
                                estop_btn.set_text("⏳ STOPPING...")
                                estop_btn.style(
                                    "width: 100%; padding: 12px; font-size: 14px; font-weight: 800;"
                                    "color: white; background: #991B1B; border: 3px solid #991B1B;"
                                    "border-radius: 10px; opacity: 0.7;")
                                # Send both stop commands
                                await run.io_bound(state.send_command, "stopJ", {})
                                await run.io_bound(state.send_command, "stopScript", {})
                                # Verify robot actually stopped (poll velocities)
                                verify = await run.io_bound(state._poll_stopped, 3.0)
                                verified = verify.get("verified", False)

                                estop_btn.set_text("⚠ EMERGENCY STOP")
                                if verified or not state.is_live:
                                    estop_btn.style(
                                        "width: 100%; padding: 12px; font-size: 14px; font-weight: 800;"
                                        "color: white; background: #00D4AA; border: 3px solid #059669;"
                                        "border-radius: 10px; box-shadow: 0 4px 20px rgba(0,212,170,0.4);")
                                    estop_indicator.set_text("✓")
                                    estop_indicator.style(
                                        "position: absolute; top: -6px; right: -6px; width: 22px; height: 22px;"
                                        "border-radius: 50%; display: flex; align-items: center; justify-content: center;"
                                        "font-size: 13px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"
                                        "background: #00D4AA; color: #0B1120;")
                                else:
                                    estop_btn.style(
                                        "width: 100%; padding: 12px; font-size: 14px; font-weight: 800;"
                                        "color: white; background: #FBBF24; border: 3px solid #D97706;"
                                        "border-radius: 10px;")
                                    estop_indicator.set_text("⚠")
                                    estop_indicator.style(
                                        "position: absolute; top: -6px; right: -6px; width: 22px; height: 22px;"
                                        "border-radius: 50%; display: flex; align-items: center; justify-content: center;"
                                        "font-size: 13px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"
                                        "background: #FBBF24; color: #0B1120;")

                                # Unlock panel if it was locked by another command
                                if _twin_lock and _twin_lock[0].get("locked"):
                                    _twin_lock[0]["locked"] = False
                                    for entry in _twin_lock[1:]:
                                        entry["btn"].set_text(entry["label"])
                                        entry["btn"].style(entry["base_style"])

                            estop_btn.on("click", _estop_click)

                        # Shared lock state: index 0 is the lock flag, rest are button refs
                        _twin_lock = [{"locked": False}]

                        with ui.row().style("gap: 6px; flex-wrap: wrap"):
                            _ack_btn("⚡ Power On",  "powerOn",       state, "#00D4AA", panel_lock=_twin_lock)
                            _ack_btn("⏻ Power Off",  "powerOff",      state, "#6E7681", panel_lock=_twin_lock)
                            _ack_btn("🔓 Brakes",    "brakeRelease",  state, "#4895EF", panel_lock=_twin_lock)
                            _ack_btn("🔑 Unlock P-Stop", "unlockProtectiveStop", state, "#FBBF24", panel_lock=_twin_lock)
                            _ack_btn("🔄 Restart Safety", "restartSafety", state, "#7B61FF", panel_lock=_twin_lock)

                        # Program Control
                        with ui.row().style("gap: 6px; flex-wrap: wrap"):
                            _ack_btn("▶ Play",       "play",          state, "#00D4AA", panel_lock=_twin_lock)
                            _ack_btn("⏸ Pause",      "pause",         state, "#FBBF24", panel_lock=_twin_lock)
                            _ack_btn("⏹ Stop",       "stop",          state, "#FF6B6B", panel_lock=_twin_lock)
                            _ack_btn("🔄 Re-upload",  "reuploadScript", state, "#4895EF", panel_lock=_twin_lock)
                            _ack_btn("⊘ Zero F/T",   "zeroFtSensor",  state, "#6E7681", panel_lock=_twin_lock)

                        # Car Assembly Program
                        with ui.element("div").style(
                            "background: #0D1117; border-radius: 8px; border: 1px solid var(--border); padding: 8px 12px"):
                            car_assembly_btn = ui.button("🚗 Start Car Assembly").style(
                                "background: linear-gradient(135deg, #FF6B00, #FF8C00); color: white; font-weight: 700; padding: 10px 20px;"
                                "border-radius: 8px; width: 100%; font-size: 14px; letter-spacing: 0.5px;")

                            async def _run_car_assembly():
                                style_base = ("color: white; font-weight: 700; padding: 10px 20px;"
                                              "border-radius: 8px; width: 100%; font-size: 14px;")
                                car_assembly_btn.set_text("⏳ Loading Program...")
                                car_assembly_btn.style(f"background: #6E7681; {style_base} pointer-events: none;")
                                result = await run.io_bound(state.send_command, "loadProgram", {"program": "car_assembly"})
                                if result.get("status") == "ok":
                                    await asyncio.sleep(1)
                                    await run.io_bound(state.send_command, "play")
                                    car_assembly_btn.set_text("🚗 Car Assembly Running")
                                    car_assembly_btn.style(f"background: #00D4AA; color: #0B1120; font-weight: 700; padding: 10px 20px;"
                                                           "border-radius: 8px; width: 100%; font-size: 14px;")
                                else:
                                    car_assembly_btn.set_text("❌ Load Failed — Retry")
                                    car_assembly_btn.style(f"background: #FF6B6B; {style_base}")
                                await asyncio.sleep(3)
                                car_assembly_btn.set_text("🚗 Start Car Assembly")
                                car_assembly_btn.style(f"background: linear-gradient(135deg, #FF6B00, #FF8C00); {style_base} letter-spacing: 0.5px;")

                            car_assembly_btn.on("click", _run_car_assembly)

                        # Freedrive Toggle
                        with ui.element("div").style(
                            "background: #0D1117; border-radius: 8px; border: 1px solid var(--border); padding: 8px 12px"):
                            twin_freedrive_btn = ui.button("✋ Enable Freedrive").style(
                                "background: #7B61FF; color: white; font-weight: 600; padding: 8px 16px;"
                                "border-radius: 6px; width: 100%;")

                            async def _twin_toggle_freedrive():
                                if state.freedrive_active:
                                    await run.io_bound(state.send_command, "endFreedriveMode")
                                    state.freedrive_active = False
                                    twin_freedrive_btn.set_text("✋ Enable Freedrive")
                                    twin_freedrive_btn.style(
                                        "background: #7B61FF; color: white; font-weight: 600; padding: 8px 16px;"
                                        "border-radius: 6px; width: 100%;")
                                else:
                                    await run.io_bound(state.send_command, "freedriveMode")
                                    state.freedrive_active = True
                                    twin_freedrive_btn.set_text("🔒 Exit Freedrive")
                                    twin_freedrive_btn.style(
                                        "background: #FF6B6B; color: #0B1120; font-weight: 600; padding: 8px 16px;"
                                        "border-radius: 6px; width: 100%;")

                            twin_freedrive_btn.on("click", _twin_toggle_freedrive)

                        # Move Command (compact)
                        with ui.element("div").style(
                            "background: #0D1117; border-radius: 8px; border: 1px solid var(--border); padding: 10px"):
                            ui.label("MOVE COMMAND").style(
                                "font-size: 9.5px; color: var(--muted); letter-spacing: 0.4px; text-transform: uppercase; margin-bottom: 6px")
                            with ui.row().style("gap: 8px; align-items: flex-end; flex-wrap: wrap"):
                                twin_move_mode = ui.toggle(["moveJ", "moveL"], value="moveJ").style(
                                    "font-family: 'JetBrains Mono', monospace; font-size: 10px")
                                twin_move_speed = ui.number("Speed", value=0.5, step=0.01).style("width: 65px; font-size: 11px")
                                twin_move_accel = ui.number("Accel", value=1.0, step=0.1).style("width: 65px; font-size: 11px")
                            with ui.row().style("gap: 6px; margin-top: 6px; flex-wrap: wrap"):
                                twin_move_targets = []
                                labels_j = ["Base", "Shldr", "Elbow", "W1", "W2", "W3"]
                                defaults = [0, -1.57, 0, 0, 1.57, 0]
                                for i in range(6):
                                    twin_move_targets.append(
                                        ui.number(labels_j[i], value=defaults[i], step=0.001).style("width: 60px; font-size: 10px"))
                            with ui.row().style("gap: 6px; margin-top: 8px"):
                                async def _twin_exec_move():
                                    await run.io_bound(state.send_command,
                                        twin_move_mode.value,
                                        {"target": [mt.value for mt in twin_move_targets],
                                         "speed": twin_move_speed.value,
                                         "acceleration": twin_move_accel.value})
                                ui.button("▶ Execute", on_click=_twin_exec_move).style(
                                    "background: #00D4AA; color: #0B1120; font-weight: 600; font-size: 11px;"
                                    "padding: 6px 14px; border-radius: 6px;")

                                def _twin_copy_current():
                                    s = state.sample
                                    if not s:
                                        return
                                    if twin_move_mode.value == "moveJ":
                                        for i in range(6):
                                            twin_move_targets[i].value = round(s["q"][i], 4)
                                    else:
                                        axes = ["x", "y", "z", "rx", "ry", "rz"]
                                        for i in range(6):
                                            twin_move_targets[i].value = round(s["tcp"].get(axes[i], 0), 4)
                                    twin_move_targets[0].update()

                                ui.button("📋 Copy Current", on_click=_twin_copy_current).style(
                                    "background: #6E7681; color: white; font-weight: 600; font-size: 11px;"
                                    "padding: 6px 14px; border-radius: 6px;")

                        # Speed slider
                        with ui.column().style("background: #0D1117; border-radius: 8px; border: 1px solid var(--border); padding: 10px"):
                            with ui.row().style("justify-content: space-between; align-items: center"):
                                ui.label("SPEED OVERRIDE").style("font-size: 9.5px; color: var(--muted); letter-spacing: 0.4px")
                                twin_speed_label = ui.label("100%").style(
                                    "font-size: 16px; font-weight: 700; font-family: 'JetBrains Mono', monospace")
                            async def _twin_speed_change(e):
                                twin_speed_label.set_text(f"{int(e.value*100)}%")
                                await run.io_bound(state.send_command, "setSpeedSlider", {"speed": e.value})
                            ui.slider(min=0, max=1, step=0.01, value=1.0,
                                on_change=_twin_speed_change)

    # ── FOOTER ──
    with ui.element("div").style(
        "padding: 10px 24px; border-top: 1px solid #1E293B; background: #111827;"
        "display: flex; justify-content: space-between; align-items: center; margin-top: 12px;"
    ):
        ui.label(f"UR5e @ {state.args.ip} — RTDE v2 — ur_rtde").style("font-size: 10px; color: #6E7681")
        footer_info = ui.label("—").style("font-size: 10px; color: #6E7681")
        ui.label("Future Factories Laboratory — Miami University | Powered by BWC").style("font-size: 10px; color: #6E7681")

    # ══════════════════════════════════════════════════════════════════
    #  PERIODIC UPDATE (runs per-client)
    # ══════════════════════════════════════════════════════════════════

    async def update_dashboard():
        while True:
            await asyncio.sleep(1.0 / 5)  # 5 Hz UI refresh
            try:
                s = state.sample
                if s is None:
                    continue

                hist = list(state.history)[-CHART_LEN:]
                if not hist:
                    continue

                # Header badges
                mode_text = "● LIVE" if state.is_live else "● DEMO"
                mode_style = "background: #00D4AA30; color: #00D4AA" if state.is_live else "background: #FBBF2430; color: #FBBF24"
                mode_badge.set_text(mode_text)
                mode_badge.style(f"padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; {mode_style}")

                robot_badge.set_text(f"Robot: {s['robotModeDesc']}")
                safety_badge.set_text(f"Safety: {s['safetyStatusDesc']}")
                mins = int(s["t"]) // 60
                secs = int(s["t"]) % 60
                elapsed_label.set_text(f"{mins}:{secs:02d}")

                footer_info.set_text(
                f"{s['t']:.1f}s elapsed · {len(hist)} samples · {'LIVE' if state.is_live else 'DEMO'}")

                # Overview KPIs
                _update_kpi(kpi_speed, f"{s['tcpSpeed']:.3f}")
                _update_kpi(kpi_force, f"{s['forceScalar']:.1f}")
                _update_kpi(kpi_power, f"{s['power']:.0f}")
                _update_kpi(kpi_temp, f"{max(s['temps']):.1f}")
                _update_kpi(kpi_energy, f"{s['energy']:.2f}")
                _update_kpi(kpi_vib, f"{s['vibRMS']:.3f}")

                # Overview gauges
                gauge_scaling.update_figure(make_gauge(s["speedScaling"], "Speed Scaling", 1))
                gauge_current.update_figure(make_gauge(s["iRobot"], "Robot Current", 10, "#00D4AA", 7, 9))
                gauge_maxtemp.update_figure(make_gauge(max(s["temps"]) if s["temps"] else 0, "Max Joint Temp", 80, "#4895EF", 50, 70))
                gauge_momentum.update_figure(make_gauge(s["momentum"], "Momentum", 25, "#7B61FF", 15, 20))
                gauge_payload.update_figure(make_gauge(s["payloadMass"], "Payload", 5, "#4895EF", 4.5, 5.0))

                # Overview charts
                chart_jpos_overview.update_figure(make_joint_pos_chart(hist))
                chart_force_overview.update_figure(make_force_chart(hist))

                # Joint Analysis
                chart_jpos.update_figure(make_joint_pos_chart(hist))
                chart_jvel.update_figure(make_joint_vel_chart(hist))
                chart_torque_bar.update_figure(make_torque_bar(s))
                chart_track_err.update_figure(make_tracking_error_chart(s))
                chart_radar.update_figure(make_radar_chart(s))
                joint_table.rows = [
                {"joint": JOINT_LABELS[i], "pos": f"{s['q'][i]:.4f}", "vel": f"{s['qd'][i]:.4f}",
                 "cur": f"{s['cur'][i]:.3f}", "torque": f"{s['torque'][i]:.2f}",
                 "temp": f"{s['temps'][i]:.1f}", "err": f"{abs(s['trackErr'][i])*1000:.2f}"}
                for i in range(6)
                ]
                joint_table.update()

                # TCP & Force — KPI values
                for a in ["x", "y", "z", "rx", "ry", "rz"]:
                    _update_kpi(tcp_kpi_labels[a], f"{s['tcp'].get(a, 0):.4f}")
                chart_force_detail.update_figure(make_force_chart(hist))
                gauge_force_scalar.update_figure(make_gauge(s["forceScalar"], "Force Magnitude", 150, "#FF6B6B", 80, 120))
                spd_fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="TCP Speed (m/s)", font=dict(size=12, color="#E6EDF3"))})
                spd_fig.add_trace(go.Scatter(x=[h["t"] for h in hist], y=[h["tcpSpeed"] for h in hist],
                                         mode="lines", fill="tozeroy", line=dict(color="#4895EF", width=2),
                                         fillcolor="rgba(72,149,239,0.15)"))
                chart_tcp_speed.update_figure(spd_fig)

                # Power & Thermal
                _update_kpi(kpi_v48, f"{s['v48']:.1f}")
                _update_kpi(kpi_ibot, f"{s['iRobot']:.2f}")
                _update_kpi(kpi_pow2, f"{s['power']:.0f}")
                _update_kpi(kpi_en2, f"{s['energy']:.3f}")
                _update_kpi(kpi_mom2, f"{s['momentum']:.2f}")
                chart_power.update_figure(make_power_chart(hist))
                chart_energy.update_figure(make_energy_chart(hist))
                chart_temp.update_figure(make_temp_chart(hist))
                tb_fig = go.Figure(layout={**PLOTLY_LAYOUT_BASE, "title": dict(text="Current Temperature (°C)", font=dict(size=12, color="#E6EDF3")),
                                       "yaxis": dict(range=[0, 70])})
                tb_colors = ["#FF6B6B" if s["temps"][i]>50 else "#FBBF24" if s["temps"][i]>40 else "#00D4AA" for i in range(6)]
                tb_fig.add_trace(go.Bar(x=JOINT_LABELS, y=s["temps"], marker_color=tb_colors))
                chart_temp_bar.update_figure(tb_fig)

                # Safety
                _update_kpi(kpi_scl, f"{s['speedScaling']:.2f}")
                gauge_maxcur2.update_figure(make_gauge(max([abs(c) for c in s["cur"]]) if s["cur"] else 0, "Max Joint Current", 5, "#00D4AA", 3, 4.5))
                gauge_maxtemp2.update_figure(make_gauge(max(s["temps"]) if s["temps"] else 0, "Max Joint Temp", 80, "#4895EF", 50, 70))
                gauge_momentum2.update_figure(make_gauge(s["momentum"], "Momentum", 25, "#7B61FF", 15, 20))
                chart_safety.update_figure(make_safety_chart(hist))

                # Safety bits — render as HTML to avoid clear/rebuild DOM thrashing
                bits_html = '<div style="display:flex;gap:6px;flex-wrap:wrap">'
                for key in SAFETY_BIT_LABELS:
                    label = key.replace("_", " ").title()
                    active = s["safetyBits"].get(key, 0) == 1
                    is_good = key == "normal_mode"
                    bg = "rgba(0,212,170,0.12)" if (active and is_good) else "rgba(255,107,107,0.12)" if (active and not is_good) else "#111827"
                    dot = "#00D4AA" if (active and is_good) else "#FF6B6B" if active else "#30363D"
                    fw = "600" if active else "400"
                    tc = "#E6EDF3" if active else "#6E7681"
                    bits_html += (f'<div style="display:flex;align-items:center;gap:6px;padding:4px 8px;'
                             f'border-radius:6px;background:{bg};border:1px solid #1E293B">'
                             f'<div style="width:7px;height:7px;border-radius:50%;background:{dot}"></div>'
                             f'<span style="font-size:10px;font-weight:{fw};color:{tc}">{label}</span></div>')
                bits_html += '</div>'
                safety_bits_content.set_content(bits_html)

                rbits_html = '<div style="display:flex;gap:10px;flex-wrap:wrap">'
                for key in ROBOT_BIT_LABELS:
                    label = key.replace("_", " ").title()
                    active = s["robotBits"].get(key, 0) == 1
                    bg = "rgba(0,212,170,0.12)" if active else "#111827"
                    dot = "#00D4AA" if active else "#30363D"
                    fw = "600" if active else "400"
                    rbits_html += (f'<div style="display:flex;align-items:center;gap:6px;padding:5px 10px;'
                                  f'border-radius:6px;background:{bg};border:1px solid #1E293B">'
                                  f'<div style="width:8px;height:8px;border-radius:50%;background:{dot}"></div>'
                                  f'<span style="font-size:10.5px;font-weight:{fw}">{label}</span></div>')
                rbits_html += '</div>'
                robot_bits_content.set_content(rbits_html)

                # Command log — snapshot under lock to avoid races with writer threads
                with state.ctrl_log_lock:
                    log_snapshot = list(state.ctrl_log[:20])
                log_html = ""
                for entry in log_snapshot:
                    color = {"error": "#FF6B6B", "ok": "#00D4AA", "cmd": "#FBBF24"}.get(entry["type"], "#8B949E")
                    log_html += f'<div style="padding:2px 0; font-size:10.5px"><span style="color:#6E7681; margin-right:8px">{entry["t"]}</span><span style="color:{color}">{entry["msg"]}</span></div>'
                if not log_html:
                    log_html = '<div style="color: #6E7681">No commands sent yet.</div>'
                ctrl_log_content.set_content(log_html)

                # Robot Control tab — Live State Summary
                axes = ["x", "y", "z", "rx", "ry", "rz"]
                for a in axes:
                    ctrl_tcp_labels[a].set_text(f"{s['tcp'].get(a, 0):.4f}")
                ctrl_speed_label.set_text(f"{s['tcpSpeed']:.4f}")
                ctrl_force_label.set_text(f"{s['forceScalar']:.1f}")

                # Robot Control tab — Jog position readouts
                for i in range(6):
                    jog_pos_label_refs[i].set_text(f"{s['q'][i]:.4f} rad")
                # Robot Control tab — Cartesian position readouts
                for i, a in enumerate(axes):
                    cart_pos_label_refs[i].set_text(f"{s['tcp'].get(a, 0):.4f}")

                # Digital Twin tab updates
                twin_elapsed_label.set_text(f"{s['t']:.1f}s · {'LIVE' if state.is_live else 'DEMO'}")
                _update_kpi(twin_kpi_speed, f"{s['tcpSpeed']:.3f}")
                _update_kpi(twin_kpi_force, f"{s['forceScalar']:.1f}")
                _update_kpi(twin_kpi_power, f"{s['power']:.0f}")
                twin_gauge_temp.update_figure(make_gauge(max(s["temps"]), "Max Temp", 85, "#F8B739", 50, 70))
                twin_gauge_cur.update_figure(make_gauge(max([abs(c) for c in s["cur"]]) if s["cur"] else 0, "Max Current", 5, "#00D4AA", 3, 4.5))
                twin_gauge_mom.update_figure(make_gauge(s["momentum"], "Momentum", 25, "#7B61FF", 15, 20))
                short_hist = hist[-60:]
                twin_chart_force.update_figure(make_force_chart(short_hist))
                twin_robot_badge.set_text(s["robotModeDesc"])

                # Safety status in telemetry panel
                safety = state.camera.safety
                ss = safety.safety_status
                if ss == "DANGER":
                    twin_safety_bar.style(
                        "padding: 8px 12px; border-radius: 8px; background: rgba(255,107,107,0.10); border: 1px solid rgba(255,107,107,0.25);"
                        "display: flex; align-items: center; justify-content: space-between;")
                    twin_safety_dot.style("width: 10px; height: 10px; border-radius: 50%; background: #FF6B6B;"
                                          "box-shadow: 0 0 8px rgba(255,107,107,0.6);")
                    twin_safety_label.set_text("⚠ DANGER — PERSON IN ZONE")
                    twin_safety_label.style("font-size: 11px; font-weight: 700; color: #FF6B6B; letter-spacing: 0.5px")
                elif ss == "WARNING":
                    twin_safety_bar.style(
                        "padding: 8px 12px; border-radius: 8px; background: rgba(251,191,36,0.08); border: 1px solid rgba(251,191,36,0.2);"
                        "display: flex; align-items: center; justify-content: space-between;")
                    twin_safety_dot.style("width: 10px; height: 10px; border-radius: 50%; background: #FBBF24;")
                    twin_safety_label.set_text("WARNING — PERSON NEARBY")
                    twin_safety_label.style("font-size: 11px; font-weight: 700; color: #FBBF24; letter-spacing: 0.5px")
                else:
                    twin_safety_bar.style(
                        "padding: 8px 12px; border-radius: 8px; background: #E8F8F0; border: 1px solid #A9DFBF;"
                        "display: flex; align-items: center; justify-content: space-between;")
                    twin_safety_dot.style("width: 10px; height: 10px; border-radius: 50%; background: #00D4AA;")
                    twin_safety_label.set_text("ZONE CLEAR")
                    twin_safety_label.style("font-size: 11px; font-weight: 700; color: #E6EDF3; letter-spacing: 0.5px")

                n_persons = len(safety.persons_detected)
                dist_text = f"{safety.closest_distance:.2f}m" if safety.closest_distance < 100 else "—"
                twin_safety_dist.set_text(f"{n_persons} person(s) | Closest: {dist_text}")
                if safety.gesture:
                    twin_safety_dist.set_text(
                        f"{n_persons} person(s) | Closest: {dist_text} | Gesture: {safety.gesture.upper()}")

            except Exception:
                pass  # Silently skip update cycle to prevent page refresh

    ui.timer(0.5, update_dashboard)  # 2 Hz — Plotly rerenders are expensive, faster rates cause browser disconnects


# ══════════════════════════════════════════════════════════════════════════════
#  UI HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _fullscreen_btn(panel_element, dark=True):
    """Add a fullscreen toggle button that targets the given panel element."""
    css_class = "fs-btn" if dark else "fs-btn light"
    btn = ui.button("⛶", on_click=lambda: ui.run_javascript(
        f'toggleFullscreen(document.getElementById("c{panel_element.id}"))'
    )).classes(css_class)
    return btn

def _kpi(label: str, value: str, unit: str):
    """Create a KPI card and return the value label for updates."""
    with ui.element("div").classes("kpi-card").style("flex: 1; min-width: 120px"):
        ui.label(label).classes("kpi-label")
        with ui.row().style("align-items: baseline; gap: 6px; margin-top: 4px"):
            val_label = ui.label(value).classes("kpi-value")
            ui.label(unit).classes("kpi-unit")
    return val_label


def _kpi_mini(label: str, value: str, unit: str):
    """Smaller KPI for the Digital Twin panel."""
    with ui.element("div").style(
        "flex: 1; padding: 10px 12px; background: #0D1117; border-radius: 8px; border: 1px solid var(--border);"
    ):
        ui.label(label).style("font-size: 9px; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase")
        with ui.row().style("align-items: baseline; gap: 4px; margin-top: 2px"):
            val_label = ui.label(value).style(
                "font-size: 18px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--text)")
            ui.label(unit).style("font-size: 10px; color: var(--subtle)")
    return val_label


def _update_kpi(val_label, new_value: str):
    val_label.set_text(new_value)


def _ctrl_btn(label: str, on_click_coro, color: str):
    """Control button that runs its callback via run.io_bound to avoid blocking the event loop."""
    async def _handler():
        await run.io_bound(on_click_coro)
    ui.button(label, on_click=_handler).style(
        f"background: {color}; color: white; font-weight: 600; font-size: 12px;"
        f"padding: 10px 16px; border-radius: 8px; box-shadow: 0 2px 8px {color}40;")


def _ctrl_btn_sm(label: str, on_click_coro, color: str):
    async def _handler():
        await run.io_bound(on_click_coro)
    ui.button(label, on_click=_handler).style(
        f"background: {color}; color: white; font-weight: 600; font-size: 10.5px;"
        f"padding: 6px 10px; border-radius: 6px;")


def _ack_btn(label: str, command: str, state: AppState, color: str, params: Optional[Dict] = None,
             panel_lock: Optional[list] = None):
    """Control button with ✓/✗ acknowledgment + panel locking for the Digital Twin panel.

    - Sends command immediately
    - For powerOn/powerOff/brakeRelease: polls robot state to verify
    - Locks all other buttons (except E-Stop) during execution
    - Shows ✓ green / ✗ red that stays until next click
    - panel_lock: list shared between all _ack_btn instances, contains [lock_flag, btn_refs]
    """
    base_style = (f"background: {color}; color: white; font-weight: 600; font-size: 10.5px;"
                  f"padding: 6px 10px; border-radius: 6px; min-width: 80px;")
    ok_style = ("background: #00D4AA; color: #0B1120; font-weight: 600; font-size: 10.5px;"
                "padding: 6px 10px; border-radius: 6px; min-width: 80px;")
    err_style = ("background: #FF6B6B; color: #0B1120; font-weight: 600; font-size: 10.5px;"
                 "padding: 6px 10px; border-radius: 6px; min-width: 80px;")
    locked_style = ("background: #1C2333; color: #484F58; font-weight: 600; font-size: 10.5px;"
                    "padding: 6px 10px; border-radius: 6px; min-width: 80px; cursor: not-allowed; opacity: 0.5;")
    pending_style = (f"background: {color}; color: white; font-weight: 600; font-size: 10.5px;"
                     f"padding: 6px 10px; border-radius: 6px; min-width: 80px; opacity: 0.6;")

    with ui.element("div").style("position: relative; display: inline-flex"):
        btn = ui.button(label).style(base_style)
        indicator = ui.label("").style(
            "position: absolute; top: -6px; right: -6px; width: 18px; height: 18px;"
            "border-radius: 50%; display: none; align-items: center; justify-content: center;"
            "font-size: 11px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);")

        # Register this button in the shared lock list
        if panel_lock is not None:
            panel_lock.append({"btn": btn, "label": label, "base_style": base_style})

        async def on_click():
            # Check if panel is locked
            if panel_lock and panel_lock[0].get("locked"):
                return

            # Lock the panel
            if panel_lock:
                panel_lock[0]["locked"] = True
                for entry in panel_lock[1:]:
                    if entry["btn"] is not btn:
                        entry["btn"].style(locked_style)
                        entry["btn"].set_text("🔒 " + entry["label"])

            # Show pending state
            btn.set_text("⏳ " + label)
            btn.style(pending_style)
            indicator.style(
                "position: absolute; top: -6px; right: -6px; width: 18px; height: 18px;"
                "border-radius: 50%; display: none;")

            # Send and verify command
            use_verified = command in ("powerOn", "powerOff", "brakeRelease", "moveJ", "moveL")
            if use_verified:
                result = await run.io_bound(state.send_command_verified, command, params or {})
            else:
                result = await run.io_bound(state.send_command, command, params or {})

            status = result.get("status", "error")
            verified = result.get("verified", status == "ok")

            # Show result
            btn.set_text(label)
            if status == "ok" and verified:
                btn.style(ok_style)
                indicator.set_text("✓")
                indicator.style(
                    "position: absolute; top: -6px; right: -6px; width: 18px; height: 18px;"
                    "border-radius: 50%; display: flex; align-items: center; justify-content: center;"
                    "font-size: 11px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"
                    "background: #00D4AA; color: #0B1120;")
            elif status == "ok" and not verified:
                # Command sent but verification failed/timed out
                btn.style(("background: #FBBF24; color: #0B1120; font-weight: 600; font-size: 10.5px;"
                           "padding: 6px 10px; border-radius: 6px; min-width: 80px;"))
                indicator.set_text("⚠")
                indicator.style(
                    "position: absolute; top: -6px; right: -6px; width: 18px; height: 18px;"
                    "border-radius: 50%; display: flex; align-items: center; justify-content: center;"
                    "font-size: 11px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"
                    "background: #FBBF24; color: #0B1120;")
            else:
                btn.style(err_style)
                indicator.set_text("✗")
                indicator.style(
                    "position: absolute; top: -6px; right: -6px; width: 18px; height: 18px;"
                    "border-radius: 50%; display: flex; align-items: center; justify-content: center;"
                    "font-size: 11px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,0.3);"
                    "background: #FF6B6B; color: #0B1120;")

            # Unlock the panel
            if panel_lock:
                panel_lock[0]["locked"] = False
                for entry in panel_lock[1:]:
                    if entry["btn"] is not btn:
                        entry["btn"].set_text(entry["label"])
                        entry["btn"].style(entry["base_style"])

        btn.on("click", on_click)


def _jog_btn(label, state, axis, direction, speed_input, accel_input):
    async def on_press():
        speeds = [0]*6
        speeds[axis] = direction * speed_input.value
        await run.io_bound(state.send_command, "jogStart", {"speeds": speeds, "acceleration": accel_input.value})
    async def on_release():
        await run.io_bound(state.send_command, "jogStop")
    color = "#4895EF" if direction > 0 else "#FF6B6B"
    ui.button(label, on_click=on_press).style(
        f"padding: 8px 12px; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        f"color: {color}; background: {color}10; border: 1.5px solid {color}40; border-radius: 6px; min-width: 40px")


def _cart_jog_btn(label, state, axis, direction, speed_input, accel_input):
    async def on_press():
        speeds = [0]*6
        speeds[axis] = direction * speed_input.value * (0.1 if axis < 3 else 1.0)
        await run.io_bound(state.send_command, "jogStart", {"speeds": speeds, "acceleration": accel_input.value, "feature": 0})
    color = "#4895EF" if direction > 0 else "#FF6B6B"
    ui.button(label, on_click=on_press).style(
        f"padding: 8px 12px; font-size: 13px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        f"color: {color}; background: {color}10; border: 1.5px solid {color}40; border-radius: 6px; min-width: 40px")


def _dio_switch(label: str, state: AppState, command: str, idx: int):
    async def _on_change(e):
        await run.io_bound(state.send_command, command, {"id": idx, "level": e.value})
    sw = ui.switch(label, on_change=_on_change)
    sw.style("font-size: 11px")


async def _toggle_freedrive(state: AppState, btn):
    if state.freedrive_active:
        await run.io_bound(state.send_command, "endFreedriveMode")
        state.freedrive_active = False
        btn.set_text("Enable Freedrive")
        btn.style("background: #7B61FF; color: white; font-weight: 600; padding: 12px 24px")
    else:
        await run.io_bound(state.send_command, "freedriveMode")
        state.freedrive_active = True
        btn.set_text("Exit Freedrive")
        btn.style("background: #FF6B6B; color: white; font-weight: 600; padding: 12px 24px")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="UR5e Unified Dashboard — NiceGUI + Plotly + RTDE + RealSense",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Robot
    parser.add_argument("--ip", default="192.168.1.15", help="Robot IP address")
    parser.add_argument("--rate", type=int, default=10, help="Telemetry sampling rate (Hz). UI refreshes at 5 Hz.")
    # Logging
    parser.add_argument("--no-log", action="store_false", dest="log", help="Disable CSV/JSONL logging")
    parser.add_argument("--outdir", default=None, help="Output directory for log files")
    parser.add_argument("--buffer-size", type=int, default=50, dest="buffer_size", help="Log flush buffer size")
    # Safety
    parser.add_argument("--safety-radius", type=float, default=1.5, dest="safety_radius",
                        help="Safety zone radius (m) — distance from nearest robot link")
    parser.add_argument("--warning-radius", type=float, default=2.5, dest="warning_radius",
                        help="Warning zone radius (m) — distance from nearest robot link")
    parser.add_argument("--model-path", default=None, dest="model_path",
                        help="Path to OpenVINO person-detection-retail-0013.xml model")
    parser.add_argument("--no-safety-auto", action="store_false", dest="safety_auto",
                        help="Disable automatic robot pause/resume from safety monitor")
    # Camera pose (in robot base frame, meters) — edit these for your setup
    parser.add_argument("--cam-x", type=float, default=3.8, dest="cam_x",
                        help="Camera X position in robot base frame (meters, +X = forward)")
    parser.add_argument("--cam-y", type=float, default=0.0, dest="cam_y",
                        help="Camera Y position in robot base frame (meters, +Y = left)")
    parser.add_argument("--cam-z", type=float, default=1.5, dest="cam_z",
                        help="Camera Z position in robot base frame (meters, +Z = up)")
    parser.add_argument("--cam-look-x", type=float, default=0.0, dest="cam_look_x",
                        help="Camera look-at X (point the camera is aimed at)")
    parser.add_argument("--cam-look-y", type=float, default=0.0, dest="cam_look_y",
                        help="Camera look-at Y")
    parser.add_argument("--cam-look-z", type=float, default=0.3, dest="cam_look_z",
                        help="Camera look-at Z")
    # Server
    parser.add_argument("--port", type=int, default=8080, help="Dashboard web server port")
    parser.add_argument("--host", default="0.0.0.0", help="Dashboard bind address")
    parser.add_argument("--ws-port", type=int, default=8767, dest="ws_port",
                        help="WebSocket port for React dashboard bridge")

    args = parser.parse_args()

    # ── Rebuild camera-to-robot-base transform from CLI args ──
    global T_CAMERA_TO_BASE, CAMERA_POS_IN_BASE, CAMERA_LOOK_AT_IN_BASE
    CAMERA_POS_IN_BASE = (args.cam_x, args.cam_y, args.cam_z)
    CAMERA_LOOK_AT_IN_BASE = (args.cam_look_x, args.cam_look_y, args.cam_look_z)
    T_CAMERA_TO_BASE = _build_camera_to_base_transform(
        CAMERA_POS_IN_BASE, CAMERA_LOOK_AT_IN_BASE, CAMERA_ROLL_DEG
    )

    log.info("=" * 60)
    log.info("  UR5e Unified Dashboard")
    log.info(f"  Robot: {args.ip} | Rate: {args.rate} Hz")
    log.info(f"  Dashboard: http://{args.host}:{args.port}")
    log.info(f"  React WS:  ws://0.0.0.0:{args.ws_port}")
    log.info(f"  RTDE: {'available' if HAS_RTDE else 'NOT INSTALLED (demo mode)'}")
    log.info(f"  RealSense: {'available' if HAS_REALSENSE else 'NOT INSTALLED (camera disabled)'}")
    log.info(f"  OpenVINO: {'available' if HAS_OPENVINO else 'NOT INSTALLED (person detection disabled)'}")
    log.info(f"  MediaPipe: {'available' if HAS_MEDIAPIPE else 'NOT INSTALLED (hand gestures disabled)'}")
    log.info(f"  Safety: radius={args.safety_radius}m, warning={args.warning_radius}m, auto={'ON' if args.safety_auto else 'OFF'}")
    log.info(f"  Camera pose: pos={CAMERA_POS_IN_BASE} look_at={CAMERA_LOOK_AT_IN_BASE} (robot base frame)")
    log.info("=" * 60)

    state = AppState(args)

    @ui.page("/")
    def index():
        build_dashboard(state)

    # ── MJPEG Streaming Endpoint (runs outside NiceGUI, pure HTTP) ──
    from starlette.responses import StreamingResponse

    def _generate_mjpeg():
        """Yield MJPEG frames as a continuous HTTP stream."""
        while True:
            if state.camera.running:
                jpg = state.camera.get_jpeg("color", quality=80)
                if jpg:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
            time.sleep(0.033)  # ~30 FPS cap

    @app.get("/video_feed")
    async def video_feed():
        return StreamingResponse(
            _generate_mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/depth_feed")
    async def depth_feed():
        def _gen_depth():
            while True:
                if state.camera.running:
                    jpg = state.camera.get_jpeg("depth", quality=80)
                    if jpg:
                        yield (b"--frame\r\n"
                               b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                time.sleep(0.033)
        return StreamingResponse(_gen_depth(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/combined_feed")
    async def combined_feed():
        def _gen_combined():
            while True:
                if state.camera.running:
                    jpg = state.camera.get_jpeg("combined", quality=80)
                    if jpg:
                        yield (b"--frame\r\n"
                               b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n")
                time.sleep(0.033)
        return StreamingResponse(_gen_combined(), media_type="multipart/x-mixed-replace; boundary=frame")

    app.on_startup(state.start)
    app.on_shutdown(state.shutdown)

    ui.run(
        host=args.host,
        port=args.port,
        title="UR5e Dashboard",
        favicon="🤖",
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    main()