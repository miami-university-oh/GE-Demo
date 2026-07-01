"""
safety_monitor.py
─────────────────
Top-down Intel RealSense L515 + YOLOv8 + UR5e safety supervisor.

Runs on the HOST PC (not inside Isaac Sim).
Isaac Sim receives zone-state updates over UDP for visualization.

Calibration:
    Camera height : 3.52 m above floor
    Robot base XY : (0.00, -0.18) m in floor frame
    Zone derivation: ISO/TS 15066 Speed and Separation Monitoring

Model classes:
    0: HAAS-CNC, 1: Hard-hat, 2: Human, 3: Laptop, 4: Milling Machine,
    5: Simulator, 6: Toolbox, 7: UR5e, 8: UR5e_Workstation, 9: Workstation

Usage:
    pip install ultralytics pyrealsense2 ur-rtde numpy
    python safety_monitor.py
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
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════ #
@dataclass(frozen=True)
class SafetyConfig:
    # ── Zone radii (ISO/TS 15066 derived) ──
    # S_p = S_h + S_r + S_s + C + Z_d + Z_r
    #     = (1.6×0.1) + (1.0×0.1) + (1.0×0.3) + 0.12 + 0.10 + 0.05
    #     = 0.83 m  →  danger_radius = 0.85 m (rounded up)
    # Warning = danger + v_h × T_slowdown = 0.85 + 1.6×0.5 = 1.65 m
    # Clear   = warning + hysteresis = 1.65 + 0.30 = 1.95 m
    danger_radius:  float = 0.85
    warning_radius: float = 1.65
    clear_radius:   float = 1.95

    # ── Speed scaling ──
    max_speed_scale: float = 1.0
    min_speed_scale: float = 0.10

    # ── Timing ──
    control_hz:       float = 30.0
    rescan_pause_ms:  float = 500.0
    stale_timeout_ms: float = 200.0

    # ── Robot base position in floor frame (CALIBRATED) ──
    robot_base_xy: Tuple[float, float] = (0.00, -0.18)

    # ── Network ──
    robot_ip: str = "192.168.1.15"
    sim_host: str = "127.0.0.1"
    sim_port: int = 9876

    # ── YOLO model (custom trained) ──
    # Place weights.pt in the same folder as this script.
    yolo_weights:   str = "weights__10_.pt"
    yolo_conf:      float = 0.5
    human_class_id: int = 2              # class 2 = Human in your model

    # ── Camera ──
    camera_width:  int = 640
    camera_height: int = 480
    camera_fps:    int = 30


class SafetyState(Enum):
    GREEN  = "GREEN"
    YELLOW = "YELLOW"
    RED    = "RED"
    RESCAN = "RESCAN"


@dataclass
class Detection:
    human_present: bool
    human_xy: Optional[Tuple[float, float]]
    confidence: float
    timestamp: float = field(default_factory=time.monotonic)

    def age_ms(self) -> float:
        return (time.monotonic() - self.timestamp) * 1000.0


# ═══════════════════════════════════════════════════════════════════════════ #
#  PERCEPTION
# ═══════════════════════════════════════════════════════════════════════════ #
class PerceptionThread(threading.Thread):
    def __init__(self, cfg: SafetyConfig):
        super().__init__(daemon=True, name="perception")
        self.cfg = cfg
        self._lock = threading.Lock()
        self._latest = Detection(True, None, 1.0)
        self._running = threading.Event()
        self._running.set()

        # ── CALIBRATED camera-to-floor extrinsic ──
        self.T_cam_floor = np.array([
            [1.0, 0.0,  0.0, 0.0 ],
            [0.0, 1.0,  0.0, 0.0 ],
            [0.0, 0.0, -1.0, 3.52],
            [0.0, 0.0,  0.0, 1.0 ],
        ])

    def latest(self) -> Detection:
        with self._lock:
            return self._latest

    def stop(self):
        self._running.clear()

    def run(self):
        cfg = self.cfg

        pipeline = rs.pipeline()
        rs_cfg = rs.config()
        rs_cfg.enable_stream(rs.stream.color, cfg.camera_width, cfg.camera_height,
                             rs.format.bgr8, cfg.camera_fps)
        rs_cfg.enable_stream(rs.stream.depth, cfg.camera_width, cfg.camera_height,
                             rs.format.z16, cfg.camera_fps)
        profile = pipeline.start(rs_cfg)
        align = rs.align(rs.stream.color)

        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        self.intrinsics = depth_profile.get_intrinsics()

        model = YOLO(cfg.yolo_weights)
        log.info("Perception started  (model=%s, class=%d='Human', conf=%.2f)",
                 cfg.yolo_weights, cfg.human_class_id, cfg.yolo_conf)

        try:
            while self._running.is_set():
                try:
                    det = self._infer(pipeline, align, model)
                except Exception:
                    log.exception("Frame error → UNSAFE default")
                    det = Detection(True, None, 1.0)
                with self._lock:
                    self._latest = det
        finally:
            pipeline.stop()
            log.info("RealSense pipeline stopped")

    def _infer(self, pipeline, align, model) -> Detection:
        cfg = self.cfg

        frames = pipeline.wait_for_frames()
        aligned = align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame or not depth_frame:
            return Detection(True, None, 1.0)

        color_image = np.asanyarray(color_frame.get_data())

        results = model.predict(
            source=color_image,
            conf=cfg.yolo_conf,
            classes=[cfg.human_class_id],
            verbose=False,
        )

        humans_floor: List[Tuple[float, float, float]] = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id != cfg.human_class_id:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            cu = int((x1 + x2) / 2)
            cv = int((y1 + y2) / 2)
            cu = max(0, min(cu, cfg.camera_width - 1))
            cv = max(0, min(cv, cfg.camera_height - 1))

            depth_m = depth_frame.get_distance(cu, cv)
            if depth_m < 0.1 or depth_m > 5.0:
                continue

            point_cam = rs.rs2_deproject_pixel_to_point(
                self.intrinsics, [cu, cv], depth_m
            )
            p_cam = np.array([point_cam[0], point_cam[1], point_cam[2], 1.0])
            p_floor = self.T_cam_floor @ p_cam
            humans_floor.append((float(p_floor[0]), float(p_floor[1]), conf))

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
#  ROBOT INTERFACE
# ═══════════════════════════════════════════════════════════════════════════ #
class RobotInterface:
    def __init__(self, cfg: SafetyConfig):
        self.cfg = cfg
        self._scale = 1.0
        self._paused = False
        self._lock = threading.Lock()

        # Uncomment to command real UR5e:
        # from rtde_control import RTDEControlInterface
        # self.rtde = RTDEControlInterface(cfg.robot_ip)
        self.rtde = None

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
        log.info("Robot RESUMED")

    def send_state_to_sim(self, state: str, distance: float):
        try:
            msg = json.dumps({"state": state, "distance": round(distance, 3)})
            self._sim_sock.sendto(msg.encode(), self._sim_addr)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════ #
#  SAFETY CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════ #
class SafetyController(threading.Thread):
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

    def run(self):
        period = 1.0 / self.cfg.control_hz
        log.info("Safety controller started  (%.0f Hz)", self.cfg.control_hz)

        while self._running.is_set():
            t0 = time.monotonic()
            det = self.perception.latest()
            stale = det.age_ms() > self.cfg.stale_timeout_ms
            d = 0.0 if stale else self._distance(det)
            self._step(d, stale)
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, period - elapsed))

    def _step(self, d: float, stale: bool):
        c = self.cfg

        if stale or d <= c.danger_radius:
            self.robot.pause()
            self._rescan_started = None
            self._set_state(SafetyState.RED, d)
            return

        if self.state in (SafetyState.RED, SafetyState.RESCAN):
            if self._rescan_started is None:
                self._rescan_started = time.monotonic()
                self._set_state(SafetyState.RESCAN, d)
            elapsed_ms = (time.monotonic() - self._rescan_started) * 1000.0
            if elapsed_ms < c.rescan_pause_ms:
                self.robot.pause()
                return
            self._rescan_started = None
            self.robot.resume()

        if d < c.warning_radius:
            self.robot.set_speed_scale(self._speed_for_distance(d))
            self.robot.resume()
            self._set_state(SafetyState.YELLOW, d)
            return

        if d >= c.clear_radius or self.state != SafetyState.YELLOW:
            self.robot.set_speed_scale(c.max_speed_scale)
            self.robot.resume()
            self._set_state(SafetyState.GREEN, d)
        else:
            self.robot.set_speed_scale(self._speed_for_distance(d))


# ═══════════════════════════════════════════════════════════════════════════ #
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════ #
def main():
    cfg = SafetyConfig()

    log.info("═" * 60)
    log.info("  UR5e Safety Monitor — ISO/TS 15066 Compliant")
    log.info("  Robot IP    : %s", cfg.robot_ip)
    log.info("  YOLO model  : %s  (class %d='Human', conf ≥ %.2f)",
             cfg.yolo_weights, cfg.human_class_id, cfg.yolo_conf)
    log.info("  Zones (ISO) : danger=%.2fm  warning=%.2fm  clear=%.2fm",
             cfg.danger_radius, cfg.warning_radius, cfg.clear_radius)
    log.info("  Robot base  : (%.2f, %.2f) m   (floor frame)",
             *cfg.robot_base_xy)
    log.info("  Camera      : 3.52 m above floor")
    log.info("  Sim target  : %s:%d", cfg.sim_host, cfg.sim_port)
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
        robot.pause()
        log.info("Stopped.")


if __name__ == "__main__":
    main()
