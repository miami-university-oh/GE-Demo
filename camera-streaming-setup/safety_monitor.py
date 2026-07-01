"""
safety_monitor.py
─────────────────
Top-down Intel RealSense L515 + YOLOv8 + UR5e safety supervisor.

Runs on the HOST PC (not inside Isaac Sim).
Isaac Sim receives zone-state updates over UDP for visualization.

Requirements:
    pip install ultralytics pyrealsense2 ur-rtde numpy

Usage:
    python safety_monitor.py

    Then in Isaac Sim Script Editor, run the mirror script that listens
    on UDP port 9876.
"""

import time
import math
import threading
import logging
import socket
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("safety")


# ═══════════════════════════════════════════════════════════════════════════ #
#  CONFIGURATION — EDIT THESE TO MATCH YOUR SETUP
# ═══════════════════════════════════════════════════════════════════════════ #
@dataclass(frozen=True)
class SafetyConfig:
    # ── Zone radii (meters, floor plane) ──
    danger_radius: float  = 0.8     # inside  → hard pause  (RED)
    warning_radius: float = 1.8     # inside  → slow down   (YELLOW)
    clear_radius: float   = 2.2     # outside → full speed   (GREEN)
    #   gap between warning & clear = hysteresis band

    # ── Speed scaling ──
    max_speed_scale: float = 1.0
    min_speed_scale: float = 0.10   # slowest crawl in YELLOW band

    # ── Timing ──
    control_hz: float      = 30.0   # safety-loop rate
    rescan_pause_ms: float = 500.0  # clear-confirmation window
    stale_timeout_ms: float = 200.0 # detection older than this → unsafe

    # ── Robot base position in the floor frame (meters) ──
    #    Measure where the UR5e base sits relative to your
    #    camera-floor calibration origin.
    robot_base_xy: Tuple[float, float] = (0.0, 0.0)

    # ── Network ──
    robot_ip: str   = "192.168.1.15"   # ← your UR5e IP
    sim_host: str   = "127.0.0.1"      # Isaac Sim machine
    sim_port: int   = 9876

    # ── YOLO model ──
    # Point this to YOUR trained weights.
    #   • "yolov8n.pt" = pretrained nano (person = class 0, good for testing)
    #   • "best.pt"    = your custom-trained weights
    yolo_weights: str    = "yolov8n.pt"
    yolo_conf: float     = 0.5          # confidence threshold
    human_class_id: int  = 0            # COCO person=0; change if custom model differs

    # ── Camera ──
    camera_width: int  = 640
    camera_height: int = 480
    camera_fps: int    = 30


# ═══════════════════════════════════════════════════════════════════════════ #
#  DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════ #
class SafetyState(Enum):
    GREEN  = "GREEN"
    YELLOW = "YELLOW"
    RED    = "RED"
    RESCAN = "RESCAN"


@dataclass
class Detection:
    human_present: bool
    human_xy: Optional[Tuple[float, float]]   # floor-frame meters
    confidence: float
    timestamp: float = field(default_factory=time.monotonic)

    def age_ms(self) -> float:
        return (time.monotonic() - self.timestamp) * 1000.0


# ═══════════════════════════════════════════════════════════════════════════ #
#  PERCEPTION — L515 + YOLOv8
# ═══════════════════════════════════════════════════════════════════════════ #
class PerceptionThread(threading.Thread):
    """
    Captures aligned color+depth from the L515, runs YOLO, deprojects
    the nearest detected human centroid into the floor frame.
    """

    def __init__(self, cfg: SafetyConfig):
        super().__init__(daemon=True, name="perception")
        self.cfg = cfg
        self._lock = threading.Lock()
        self._latest = Detection(True, None, 1.0)  # fail-safe: assume human
        self._running = threading.Event()
        self._running.set()

        # ── Camera → floor extrinsic ──
        # This 4×4 matrix transforms a point in CAMERA coords to FLOOR coords.
        #
        # HOW TO CALIBRATE:
        #   1. Place 4+ markers on the floor at known (x, y) positions.
        #   2. Detect them in the depth frame → get 3D camera coords.
        #   3. Solve rigid transform (cv2.solvePnP or direct SVD).
        #   4. Paste the resulting 4×4 here.
        #
        # The identity matrix below is a PLACEHOLDER.
        # For a ceiling-mounted camera pointing straight down with Z = height:
        #   - X_floor ≈ X_cam
        #   - Y_floor ≈ Y_cam
        #   - Z_floor ≈ 0  (floor plane)
        # You'll still need translation for the camera offset.
        self.T_cam_floor = np.eye(4, dtype=np.float64)
        # EXAMPLE for a camera at (0, 0, 2.5m) pointing straight down,
        # with camera-Z toward floor:
        # self.T_cam_floor = np.array([
        #     [ 1,  0,  0,  0.0  ],
        #     [ 0,  1,  0,  0.0  ],
        #     [ 0,  0, -1,  2.5  ],
        #     [ 0,  0,  0,  1.0  ],
        # ])

    def latest(self) -> Detection:
        with self._lock:
            return self._latest

    def stop(self):
        self._running.clear()

    def run(self):
        cfg = self.cfg

        # ── RealSense pipeline ──
        pipeline = rs.pipeline()
        rs_cfg = rs.config()
        rs_cfg.enable_stream(rs.stream.color, cfg.camera_width, cfg.camera_height,
                             rs.format.bgr8, cfg.camera_fps)
        rs_cfg.enable_stream(rs.stream.depth, cfg.camera_width, cfg.camera_height,
                             rs.format.z16, cfg.camera_fps)
        profile = pipeline.start(rs_cfg)

        # Align depth to color so pixel coords match.
        align = rs.align(rs.stream.color)

        # Depth intrinsics (for deprojection).
        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        self.intrinsics = depth_profile.get_intrinsics()

        # ── YOLO model ──
        model = YOLO(cfg.yolo_weights)
        log.info("Perception started  (model=%s, class=%d, conf=%.2f)",
                 cfg.yolo_weights, cfg.human_class_id, cfg.yolo_conf)

        try:
            while self._running.is_set():
                try:
                    det = self._infer(pipeline, align, model)
                except Exception:
                    log.exception("Perception frame error → UNSAFE default")
                    det = Detection(True, None, 1.0)
                with self._lock:
                    self._latest = det
        finally:
            pipeline.stop()
            log.info("RealSense pipeline stopped")

    def _infer(self, pipeline, align, model) -> Detection:
        """
        One perception cycle:
          1. Grab aligned color + depth.
          2. Run YOLO on the color frame.
          3. For each human detection, deproject bbox center → floor coords.
          4. Return the NEAREST human to the robot base.
        """
        cfg = self.cfg

        # 1. Grab frames (blocks at sensor framerate ≈ 30 Hz).
        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame or not depth_frame:
            return Detection(True, None, 1.0)  # missing frame → unsafe

        color_image = np.asanyarray(color_frame.get_data())

        # 2. Run YOLO inference.
        results = model.predict(
            source=color_image,
            conf=cfg.yolo_conf,
            classes=[cfg.human_class_id],
            verbose=False,
        )

        # 3. Deproject each human detection to floor coordinates.
        humans_floor: List[Tuple[float, float, float]] = []  # (x, y, conf)

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id != cfg.human_class_id:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Bbox center pixel.
            cu = int((x1 + x2) / 2)
            cv = int((y1 + y2) / 2)

            # Clamp to frame bounds.
            cu = max(0, min(cu, cfg.camera_width - 1))
            cv = max(0, min(cv, cfg.camera_height - 1))

            # Depth at center (meters).
            depth_m = depth_frame.get_distance(cu, cv)
            if depth_m < 0.1 or depth_m > 5.0:
                # Bad depth → skip this detection (don't guess).
                continue

            # Deproject pixel → 3D camera coords.
            point_cam = rs.rs2_deproject_pixel_to_point(
                self.intrinsics, [cu, cv], depth_m
            )
            # → floor coords.
            p_cam = np.array([point_cam[0], point_cam[1], point_cam[2], 1.0])
            p_floor = self.T_cam_floor @ p_cam
            humans_floor.append((float(p_floor[0]), float(p_floor[1]), conf))

        # 4. Pick the nearest human to the robot base.
        if not humans_floor:
            return Detection(human_present=False, human_xy=None, confidence=0.0)

        bx, by = cfg.robot_base_xy
        nearest = min(humans_floor, key=lambda h: math.hypot(h[0] - bx, h[1] - by))
        return Detection(
            human_present=True,
            human_xy=(nearest[0], nearest[1]),
            confidence=nearest[2],
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  ROBOT INTERFACE — UR5e via RTDE
# ═══════════════════════════════════════════════════════════════════════════ #
class RobotInterface:
    """
    Controls real UR5e speed scaling and pause/resume.
    Sends safety state to Isaac Sim over UDP.
    """

    def __init__(self, cfg: SafetyConfig):
        self.cfg = cfg
        self._scale = 1.0
        self._paused = False
        self._lock = threading.Lock()

        # ── RTDE control ──
        # Uncomment when ready to connect to the real robot:
        # from rtde_control import RTDEControlInterface
        # self.rtde = RTDEControlInterface(cfg.robot_ip)
        self.rtde = None  # ← remove this line when uncommenting above

        # ── UDP socket to Isaac Sim ──
        self._sim_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sim_addr = (cfg.sim_host, cfg.sim_port)

        log.info("RobotInterface ready  (robot=%s, sim=%s:%d)",
                 cfg.robot_ip, cfg.sim_host, cfg.sim_port)

    def set_speed_scale(self, scale: float):
        scale = float(np.clip(scale, 0.0, 1.0))
        with self._lock:
            if abs(scale - self._scale) < 1e-3:
                return
            self._scale = scale

        if self.rtde:
            self.rtde.setSpeedSlider(scale)
        log.debug("speed → %.2f", scale)

    def pause(self):
        with self._lock:
            if self._paused:
                return
            self._paused = True

        if self.rtde:
            self.rtde.stopL(2.0)
        log.warning("ROBOT PAUSED")

    def resume(self):
        with self._lock:
            if not self._paused:
                return
            self._paused = False

        # If you're using a UR program, you may need to call
        # self.rtde.reuploadScript() or send a digital output
        # to signal "resume" to the running program.
        log.info("Robot RESUMED")

    def send_state_to_sim(self, state: str, distance: float):
        """Fire-and-forget UDP to Isaac Sim for zone visualization."""
        try:
            msg = json.dumps({"state": state, "distance": round(distance, 3)})
            self._sim_sock.sendto(msg.encode(), self._sim_addr)
        except Exception:
            pass  # non-critical


# ═══════════════════════════════════════════════════════════════════════════ #
#  SAFETY CONTROLLER — STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════ #
class SafetyController(threading.Thread):
    """
    State machine:
        GREEN  ─(human enters warning zone)──→ YELLOW
        YELLOW ─(human enters danger zone)───→ RED
        RED    ─(human leaves danger zone)───→ RESCAN  (500 ms timer)
        RESCAN ─(500 ms all-clear)───────────→ YELLOW or GREEN
        RESCAN ─(human re-enters danger)─────→ RED     (instant)
    """

    def __init__(self, cfg: SafetyConfig,
                 perception: PerceptionThread,
                 robot: RobotInterface):
        super().__init__(daemon=True, name="safety")
        self.cfg = cfg
        self.perception = perception
        self.robot = robot
        self.state = SafetyState.GREEN
        self._running = threading.Event()
        self._running.set()
        self._rescan_started: Optional[float] = None

    def stop(self):
        self._running.clear()

    # ── helpers ──
    def _distance(self, det: Detection) -> float:
        if not det.human_present or det.human_xy is None:
            return math.inf
        bx, by = self.cfg.robot_base_xy
        hx, hy = det.human_xy
        return math.hypot(hx - bx, hy - by)

    def _speed_for_distance(self, d: float) -> float:
        c = self.cfg
        if d >= c.warning_radius:
            return c.max_speed_scale
        if d <= c.danger_radius:
            return 0.0
        t = (d - c.danger_radius) / (c.warning_radius - c.danger_radius)
        return c.min_speed_scale + t * (c.max_speed_scale - c.min_speed_scale)

    def _set_state(self, new_state: SafetyState, d: float):
        if new_state != self.state:
            log.info("STATE  %s → %s  (d=%.2f m)", self.state.value, new_state.value, d)
            self.state = new_state
            self.robot.send_state_to_sim(new_state.value, d)

    # ── main loop ──
    def run(self):
        period = 1.0 / self.cfg.control_hz
        log.info("Safety controller started  (%.0f Hz)", self.cfg.control_hz)

        while self._running.is_set():
            t0 = time.monotonic()
            det = self.perception.latest()

            # Fail-safe: stale data → treat as human at distance 0.
            stale = det.age_ms() > self.cfg.stale_timeout_ms
            d = 0.0 if stale else self._distance(det)

            self._step(d, stale)

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, period - elapsed))

    def _step(self, d: float, stale: bool):
        c = self.cfg

        # ── RED: danger zone or stale data ──
        if stale or d <= c.danger_radius:
            self.robot.pause()
            self._rescan_started = None
            self._set_state(SafetyState.RED, d)
            return

        # ── RESCAN: was RED, confirming human left ──
        if self.state in (SafetyState.RED, SafetyState.RESCAN):
            if self._rescan_started is None:
                self._rescan_started = time.monotonic()
                self._set_state(SafetyState.RESCAN, d)

            elapsed_ms = (time.monotonic() - self._rescan_started) * 1000.0
            if elapsed_ms < c.rescan_pause_ms:
                self.robot.pause()      # stay stopped while confirming
                return
            # Full 500 ms passed with no re-entry → resume.
            self._rescan_started = None
            self.robot.resume()
            # fall through to YELLOW / GREEN

        # ── YELLOW: warning band ──
        if d < c.warning_radius:
            self.robot.set_speed_scale(self._speed_for_distance(d))
            self.robot.resume()
            self._set_state(SafetyState.YELLOW, d)
            return

        # ── GREEN: clear (with hysteresis) ──
        if d >= c.clear_radius or self.state != SafetyState.YELLOW:
            self.robot.set_speed_scale(c.max_speed_scale)
            self.robot.resume()
            self._set_state(SafetyState.GREEN, d)
        else:
            # Still in hysteresis gap → hold YELLOW speed.
            self.robot.set_speed_scale(self._speed_for_distance(d))


# ═══════════════════════════════════════════════════════════════════════════ #
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════ #
def main():
    cfg = SafetyConfig()

    log.info("═" * 60)
    log.info("  UR5e Safety Monitor")
    log.info("  Robot IP   : %s", cfg.robot_ip)
    log.info("  YOLO model : %s  (class %d, conf ≥ %.2f)",
             cfg.yolo_weights, cfg.human_class_id, cfg.yolo_conf)
    log.info("  Zones      : danger=%.1fm  warning=%.1fm  clear=%.1fm",
             cfg.danger_radius, cfg.warning_radius, cfg.clear_radius)
    log.info("  Sim target : %s:%d", cfg.sim_host, cfg.sim_port)
    log.info("═" * 60)

    perception = PerceptionThread(cfg)
    robot      = RobotInterface(cfg)
    controller = SafetyController(cfg, perception, robot)

    perception.start()
    controller.start()

    log.info("System running — Ctrl+C to stop")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        log.info("Shutting down…")
    finally:
        controller.stop()
        perception.stop()
        robot.pause()  # safe state on exit
        log.info("Stopped.")


if __name__ == "__main__":
    main()
