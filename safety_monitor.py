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

import json
import logging
import math
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

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
    danger_radius: float = 0.85
    warning_radius: float = 1.65
    clear_radius: float = 1.95

    # ── Speed scaling ──
    max_speed_scale: float = 1.0
    min_speed_scale: float = 0.10

    # ── Timing ──
    control_hz: float = 30.0
    rescan_pause_ms: float = 500.0
    stale_timeout_ms: float = 200.0

    # ── Robot base position in floor frame (CALIBRATED) ──
    robot_base_xy: Tuple[float, float] = (0.00, -0.18)

    # ── Network ──
    robot_ip: str = "192.168.1.15"
    sim_host: str = "127.0.0.1"
    sim_port: int = 9876

    # ── YOLO model (custom trained) ──
    # Place weights.pt in the same folder as this script.
    yolo_weights: str = "weights__10_.pt"
    yolo_conf: float = 0.5
    human_class_id: int = 2  # class 2 = Human in your model

    # ── Camera ──
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30


class SafetyState(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    RESCAN = "RESCAN"


@dataclass
class Detection:
    human_present: bool
    human_xy: Optional[Tuple[float, float]]
    confidence: float
    timestamp: float = field(default_factory=time.monotonic)

    def age_ms(self) -> float:
        """Return milliseconds elapsed since this detection was created.

        Uses ``time.monotonic`` to avoid wall-clock skew.  The safety
        controller compares this against ``stale_timeout_ms`` to decide
        whether the reading is still trustworthy.

        Returns:
            float: Detection age in milliseconds.
        """
        return (time.monotonic() - self.timestamp) * 1000.0


# ═══════════════════════════════════════════════════════════════════════════ #
#  PERCEPTION
# ═══════════════════════════════════════════════════════════════════════════ #
class PerceptionThread(threading.Thread):
    def __init__(self, cfg: SafetyConfig):
        """Initialise the perception thread.

        Sets up the camera-to-floor extrinsic transform (``T_cam_floor``) for a
        ceiling-mounted camera 3.52 m above the floor, and primes the internal
        ``Detection`` cache to a safe-default (human present, unknown position).

        Args:
            cfg (SafetyConfig): Frozen configuration dataclass with camera,
                YOLO, zone, and network parameters.
        """
        super().__init__(daemon=True, name="perception")
        self.cfg = cfg
        self._lock = threading.Lock()
        self._latest = Detection(True, None, 1.0)
        self._running = threading.Event()
        self._running.set()

        # ── CALIBRATED camera-to-floor extrinsic ──
        self.T_cam_floor = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 3.52],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

    def latest(self) -> Detection:
        """Thread-safe read of the most recent detection snapshot.

        Returns:
            Detection: Latest detection result (may be stale; check ``age_ms``).
        """
        with self._lock:
            return self._latest

    def stop(self):
        """Signal the perception thread to exit after the current frame completes."""
        self._running.clear()

    def run(self):
        """Main perception loop.

        Starts the RealSense L515 pipeline (colour + depth streams aligned to
        colour), loads the YOLO model, then calls :meth:`_infer` every frame.
        On any frame-level exception the thread defaults to the safe ``human
        present / unknown position`` state.  Stops the pipeline on exit.
        """
        cfg = self.cfg

        pipeline = rs.pipeline()
        rs_cfg = rs.config()
        rs_cfg.enable_stream(
            rs.stream.color,
            cfg.camera_width,
            cfg.camera_height,
            rs.format.bgr8,
            cfg.camera_fps,
        )
        rs_cfg.enable_stream(
            rs.stream.depth,
            cfg.camera_width,
            cfg.camera_height,
            rs.format.z16,
            cfg.camera_fps,
        )
        profile = pipeline.start(rs_cfg)
        align = rs.align(rs.stream.color)

        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        self.intrinsics = depth_profile.get_intrinsics()

        model = YOLO(cfg.yolo_weights)
        log.info(
            "Perception started  (model=%s, class=%d='Human', conf=%.2f)",
            cfg.yolo_weights,
            cfg.human_class_id,
            cfg.yolo_conf,
        )

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
        """Run one inference cycle and return the result.

        Grabs an aligned colour+depth frame pair, runs YOLOv8 with
        ``human_class_id`` filter, deprojects each detection's centre pixel
        to 3-D camera coordinates, applies ``T_cam_floor`` to get floor-frame
        XY, and returns the nearest human to the robot base.  Returns an empty
        (no-human) ``Detection`` when no valid detections are found.

        Args:
            pipeline: Active ``rs.pipeline`` instance.
            align:    ``rs.align`` object aligned to the colour stream.
            model:    Loaded ``YOLO`` model.

        Returns:
            Detection: ``human_present=True`` with floor-frame XY if a human
            is detected; ``human_present=False`` otherwise.
        """
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
        """Initialise the robot interface.

        Creates a UDP socket targeting the Isaac Sim visualiser.  The RTDE
        control handle (``self.rtde``) is left as ``None`` so the script can
        run in simulation-only mode; uncomment the import and instantiation
        lines to command a real UR5e.

        Args:
            cfg (SafetyConfig): Configuration with robot IP, sim host/port, and
                speed-scaling limits.
        """
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

        log.info(
            "RobotInterface ready  (robot=%s, sim=%s:%d)",
            cfg.robot_ip,
            cfg.sim_host,
            cfg.sim_port,
        )

    def set_speed_scale(self, scale: float):
        """Apply a speed-slider fraction to the robot (0.0 = stop, 1.0 = full speed).

        No-ops if the new value is within 0.001 of the current setting to
        avoid flooding the RTDE interface.  Value is clamped to [0.0, 1.0].

        Args:
            scale (float): Desired speed fraction in [0.0, 1.0].
        """
        scale = float(np.clip(scale, 0.0, 1.0))
        with self._lock:
            if abs(scale - self._scale) < 1e-3:
                return
            self._scale = scale
        if self.rtde:
            self.rtde.setSpeedSlider(scale)
        log.debug("speed → %.2f", scale)

    def pause(self):
        """Command an immediate protective stop.  Idempotent — ignored if already paused."""
        with self._lock:
            if self._paused:
                return
            self._paused = True
        if self.rtde:
            self.rtde.stopL(2.0)
        log.warning("ROBOT PAUSED")

    def resume(self):
        """Clear the paused flag and log the resumption.  Idempotent — ignored if not paused."""
        with self._lock:
            if not self._paused:
                return
            self._paused = False
        log.info("Robot RESUMED")

    def send_state_to_sim(self, state: str, distance: float):
        """Send a safety zone state update to the Isaac Sim visualiser via UDP.

        Fires-and-forgets; any socket error is silently swallowed so a
        missing sim host does not affect safety control.

        Args:
            state (str): Safety state string (``"GREEN"``, ``"YELLOW"``,
                ``"RED"``, or ``"RESCAN"``).
            distance (float): Distance (m) from robot base to nearest human.
        """
        try:
            msg = json.dumps({"state": state, "distance": round(distance, 3)})
            self._sim_sock.sendto(msg.encode(), self._sim_addr)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════ #
#  SAFETY CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════ #
class SafetyController(threading.Thread):
    def __init__(
        self, cfg: SafetyConfig, perception: PerceptionThread, robot: RobotInterface
    ):
        """Initialise the safety state machine.

        Args:
            cfg (SafetyConfig): Zone radii, speed limits, and timing parameters.
            perception (PerceptionThread): Thread that supplies live detections.
            robot (RobotInterface): Handle for issuing speed/stop commands.
        """
        super().__init__(daemon=True, name="safety")
        self.cfg = cfg
        self.perception = perception
        self.robot = robot
        self.state = SafetyState.GREEN
        self._running = threading.Event()
        self._running.set()
        self._rescan_started: Optional[float] = None

    def stop(self):
        """Signal the safety controller thread to stop after the current step."""
        self._running.clear()

    def _distance(self, det: Detection) -> float:
        """Return Euclidean distance (m) from the robot base to the nearest detected human.

        Returns ``math.inf`` when no human is present or position is unknown.

        Args:
            det (Detection): Most recent detection snapshot.

        Returns:
            float: Distance in metres, or ``math.inf``.
        """
        if not det.human_present or det.human_xy is None:
            return math.inf
        bx, by = self.cfg.robot_base_xy
        hx, hy = det.human_xy
        return math.hypot(hx - bx, hy - by)

    def _speed_for_distance(self, d: float) -> float:
        """Linearly interpolate robot speed between min and max across the warning zone.

        Returns ``max_speed_scale`` when the human is at or beyond the warning
        radius, ``0.0`` at or inside the danger radius, and a linear interpolation
        in between based on ``min_speed_scale``.

        Args:
            d (float): Distance (m) from robot base to nearest human.

        Returns:
            float: Speed fraction in [0.0, max_speed_scale].
        """
        c = self.cfg
        if d >= c.warning_radius:
            return c.max_speed_scale
        if d <= c.danger_radius:
            return 0.0
        t = (d - c.danger_radius) / (c.warning_radius - c.danger_radius)
        return c.min_speed_scale + t * (c.max_speed_scale - c.min_speed_scale)

    def _set_state(self, new_state: SafetyState, d: float):
        """Transition to a new safety state if it differs from the current one.

        Logs the transition and notifies Isaac Sim via UDP on every state change.

        Args:
            new_state (SafetyState): Desired next state.
            d (float): Current human-to-robot distance (m) for logging.
        """
        if new_state != self.state:
            log.info("STATE  %s → %s  (d=%.2f m)", self.state.value, new_state.value, d)
            self.state = new_state
            self.robot.send_state_to_sim(new_state.value, d)

    def run(self):
        """Main safety loop running at ``control_hz`` (default 30 Hz).

        On each tick, reads the latest detection, marks it stale if older than
        ``stale_timeout_ms``, computes human distance, and delegates to
        :meth:`_step` for state-machine logic.  Sleeps for the remaining tick
        budget to maintain the target frequency.
        """
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
        """Advance the safety state machine by one step.

        State transitions:
          - Stale data or d ≤ danger_radius → RED (robot paused).
          - Leaving RED triggers RESCAN: robot stays paused for ``rescan_pause_ms``
            before resuming.
          - d < warning_radius → YELLOW (speed scaled proportionally).
          - d ≥ clear_radius (or not previously YELLOW) → GREEN (full speed).

        Args:
            d (float): Current human-to-robot distance in metres
                (0.0 when stale).
            stale (bool): True if the detection is older than
                ``stale_timeout_ms``.
        """
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
    """Entry point for the UR5e safety monitor.

    Instantiates :class:`SafetyConfig`, :class:`PerceptionThread`,
    :class:`RobotInterface`, and :class:`SafetyController`, starts both
    daemon threads, then blocks until a ``KeyboardInterrupt``.  On shutdown,
    signals both threads to stop and issues a final protective pause.
    """
    cfg = SafetyConfig()

    log.info("═" * 60)
    log.info("  UR5e Safety Monitor — ISO/TS 15066 Compliant")
    log.info("  Robot IP    : %s", cfg.robot_ip)
    log.info(
        "  YOLO model  : %s  (class %d='Human', conf ≥ %.2f)",
        cfg.yolo_weights,
        cfg.human_class_id,
        cfg.yolo_conf,
    )
    log.info(
        "  Zones (ISO) : danger=%.2fm  warning=%.2fm  clear=%.2fm",
        cfg.danger_radius,
        cfg.warning_radius,
        cfg.clear_radius,
    )
    log.info("  Robot base  : (%.2f, %.2f) m   (floor frame)", *cfg.robot_base_xy)
    log.info("  Camera      : 3.52 m above floor")
    log.info("  Sim target  : %s:%d", cfg.sim_host, cfg.sim_port)
    log.info("═" * 60)

    perception = PerceptionThread(cfg)
    robot = RobotInterface(cfg)
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
