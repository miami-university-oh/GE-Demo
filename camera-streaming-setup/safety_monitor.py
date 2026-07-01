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
#  CONFIGURATION — EDIT THESE TO MATCH YOUR SETUP
# ═══════════════════════════════════════════════════════════════════════════ #
@dataclass(frozen=True)
class SafetyConfig:
    # ── Zone radii (meters, floor plane) ──
    danger_radius: float = 0.8  # inside  → hard pause  (RED)
    warning_radius: float = 1.8  # inside  → slow down   (YELLOW)
    clear_radius: float = 2.2  # outside → full speed   (GREEN)
    #   gap between warning & clear = hysteresis band

    # ── Speed scaling ──
    max_speed_scale: float = 1.0
    min_speed_scale: float = 0.10  # slowest crawl in YELLOW band

    # ── Timing ──
    control_hz: float = 30.0  # safety-loop rate
    rescan_pause_ms: float = 500.0  # clear-confirmation window
    stale_timeout_ms: float = 200.0  # detection older than this → unsafe

    # ── Robot base position in the floor frame (meters) ──
    #    Measure where the UR5e base sits relative to your
    #    camera-floor calibration origin.
    robot_base_xy: Tuple[float, float] = (0.0, 0.0)

    # ── Network ──
    robot_ip: str = "192.168.1.15"  # ← your UR5e IP
    sim_host: str = "127.0.0.1"  # Isaac Sim machine
    sim_port: int = 9876

    # ── YOLO model ──
    # Point this to YOUR trained weights.
    #   • "yolov8n.pt" = pretrained nano (person = class 0, good for testing)
    #   • "best.pt"    = your custom-trained weights
    yolo_weights: str = "yolov8n.pt"
    yolo_conf: float = 0.5  # confidence threshold
    human_class_id: int = 0  # COCO person=0; change if custom model differs

    # ── Camera ──
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30


# ═══════════════════════════════════════════════════════════════════════════ #
#  DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════ #
class SafetyState(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    RESCAN = "RESCAN"


@dataclass
class Detection:
    human_present: bool
    human_xy: Optional[Tuple[float, float]]  # floor-frame meters
    confidence: float
    timestamp: float = field(default_factory=time.monotonic)

    def age_ms(self) -> float:
        """Return how many milliseconds have elapsed since this detection was created.

        Uses ``time.monotonic`` to avoid wall-clock skew. The safety
        controller compares this value against ``stale_timeout_ms`` to
        determine whether the detection is still trustworthy.

        Returns:
            float: Age of the detection in milliseconds.
        """
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
        """Initialise perception thread parameters without starting the pipeline.

        Sets up the lock and fail-safe initial detection (human present,
        no position — conservative until the first real frame arrives),
        the stop event, and the camera-to-floor extrinsic transform
        ``T_cam_floor``. The transform defaults to the 4x4 identity
        matrix; replace it with the calibrated matrix produced by
        ``calibrate_l515.py``.

        Args:
            cfg (SafetyConfig): Frozen configuration object containing
                camera resolution, YOLO model path, confidence threshold,
                human class ID, and the robot base position.
        """
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
        """Return the most recent ``Detection`` snapshot, thread-safely.

        Acquires ``_lock`` before reading ``_latest`` so callers on
        other threads always get a consistent object.

        Returns:
            Detection: The last detection produced by ``_infer``, or the
            fail-safe detection if the thread has not yet produced one.
        """
        with self._lock:
            return self._latest

    def stop(self):
        """Signal the perception thread to exit after the current frame.

        Clears the ``_running`` event; the ``run`` loop checks
        ``_running.is_set()`` on every iteration and will exit cleanly,
        stopping the RealSense pipeline in its ``finally`` block.
        """
        self._running.clear()

    def run(self):
        """Main perception loop: start the pipeline and process frames until stopped.

        Starts the RealSense pipeline with both color and depth streams,
        creates an alignment object so depth pixels map to color pixels,
        loads the YOLO model, then repeatedly calls ``_infer`` to
        produce ``Detection`` objects. Each result is stored in
        ``_latest`` under ``_lock``. On any per-frame exception the
        fail-safe detection (human present, no position) is stored
        instead and the loop continues. The pipeline is stopped in a
        ``finally`` block to release the device regardless of how the
        loop exits.
        """
        cfg = self.cfg

        # ── RealSense pipeline ──
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

        # Align depth to color so pixel coords match.
        align = rs.align(rs.stream.color)

        # Depth intrinsics (for deprojection).
        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        self.intrinsics = depth_profile.get_intrinsics()

        # ── YOLO model ──
        model = YOLO(cfg.yolo_weights)
        log.info(
            "Perception started  (model=%s, class=%d, conf=%.2f)",
            cfg.yolo_weights,
            cfg.human_class_id,
            cfg.yolo_conf,
        )

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
        """Run one inference cycle and return a ``Detection`` for the nearest human.

        Steps:

        1. Block on the RealSense pipeline for an aligned color + depth
           frame pair. Returns a fail-safe detection immediately if
           either frame is missing.
        2. Run YOLO on the color image, filtering to ``human_class_id``
           only.
        3. For each detection, read depth at the bounding-box centre
           pixel (skipping if depth is outside 0.1–5.0 m), then call
           ``rs.rs2_deproject_pixel_to_point`` and transform the result
           with ``T_cam_floor`` to get a floor-frame (x, y) position.
        4. Select the human closest to ``robot_base_xy`` by Euclidean
           distance and return it as a ``Detection``. Returns an empty
           ``Detection`` (``human_present=False``) when no humans pass
           the depth validity check.

        Args:
            pipeline (rs.pipeline): Running RealSense pipeline.
            align (rs.align): Alignment processor (depth → color).
            model (YOLO): Loaded Ultralytics YOLO model.

        Returns:
            Detection: Nearest detected human in floor coords, or an
            empty/fail-safe detection when no valid human is found.
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
        """Initialise the robot interface without connecting to the robot.

        Sets up internal speed-scale and pause-state tracking, a
        threading lock for safe concurrent access, and a UDP socket
        bound to the Isaac Sim address. The RTDE handle is left as
        ``None`` (commented-out import) until the real robot is ready;
        all robot commands are silently no-ops when ``self.rtde`` is
        ``None``.

        Args:
            cfg (SafetyConfig): Frozen configuration containing
                ``robot_ip``, ``sim_host``, and ``sim_port``.
        """
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

        log.info(
            "RobotInterface ready  (robot=%s, sim=%s:%d)",
            cfg.robot_ip,
            cfg.sim_host,
            cfg.sim_port,
        )

    def set_speed_scale(self, scale: float):
        """Clamp ``scale`` to [0, 1] and apply it to the robot's speed slider.

        The update is skipped when the new value is within 0.001 of the
        current scale to avoid flooding the RTDE connection with
        redundant commands. The change is logged at DEBUG level.

        Args:
            scale (float): Desired speed fraction in [0.0, 1.0];
                values outside this range are clipped.
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
        """Send a protective stop to the robot and mark it as paused.

        Idempotent: if the robot is already paused the call returns
        immediately without issuing another stop command. Calls
        ``rtde.stopL(2.0)`` (deceleration 2 m/s²) when RTDE is active.
        Logs a WARNING on each transition to paused.
        """
        with self._lock:
            if self._paused:
                return
            self._paused = True

        if self.rtde:
            self.rtde.stopL(2.0)
        log.warning("ROBOT PAUSED")

    def resume(self):
        """Clear the paused flag and log that the robot has resumed.

        Idempotent: returns immediately if the robot is not currently
        paused. Does not send any RTDE command; the running UR program
        must be unblocked separately (e.g. via a digital output or
        ``reuploadScript``) if hard-stop was used.
        """
        with self._lock:
            if not self._paused:
                return
            self._paused = False

        # If you're using a UR program, you may need to call
        # self.rtde.reuploadScript() or send a digital output
        # to signal "resume" to the running program.
        log.info("Robot RESUMED")

    def send_state_to_sim(self, state: str, distance: float):
        """Send the current safety state and human distance to Isaac Sim over UDP.

        Serialises ``{"state": state, "distance": distance}`` as JSON
        and sends it as a single UDP datagram to ``(sim_host, sim_port)``.
        Errors are silently swallowed — the call is non-critical and
        must never block or raise in the safety loop.

        Args:
            state (str): Safety state name (e.g. ``"GREEN"``, ``"RED"``).
            distance (float): Euclidean distance (m) from the robot base
                to the nearest detected human; ``math.inf`` when no
                human is detected.
        """
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

    def __init__(
        self, cfg: SafetyConfig, perception: PerceptionThread, robot: RobotInterface
    ):
        """Initialise the safety controller state machine.

        Sets the initial state to ``GREEN``, creates the stop event,
        and resets the rescan timer. Does not start the thread; call
        ``start()`` explicitly.

        Args:
            cfg (SafetyConfig): Frozen configuration with zone radii,
                speed limits, timing parameters, and control rate.
            perception (PerceptionThread): Running perception thread
                whose ``latest()`` method is polled each control cycle.
            robot (RobotInterface): Robot interface used to apply speed
                changes and pause/resume commands.
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
        """Signal the safety controller thread to exit after its current cycle.

        Clears the ``_running`` event; the ``run`` loop checks
        ``_running.is_set()`` at the top of every iteration.
        """
        self._running.clear()

    # ── helpers ──
    def _distance(self, det: Detection) -> float:
        """Return the Euclidean distance (m) from the robot base to the nearest detected human.

        Returns ``math.inf`` when ``det.human_present`` is ``False`` or
        ``det.human_xy`` is ``None``, ensuring the state machine treats
        "no detection" as safely far away rather than dangerously close.

        Args:
            det (Detection): Detection snapshot from the perception thread.

        Returns:
            float: Distance in metres, or ``math.inf`` if no human is
            present.
        """
        if not det.human_present or det.human_xy is None:
            return math.inf
        bx, by = self.cfg.robot_base_xy
        hx, hy = det.human_xy
        return math.hypot(hx - bx, hy - by)

    def _speed_for_distance(self, d: float) -> float:
        """Linearly interpolate robot speed between min and max across the warning band.

        Returns ``max_speed_scale`` when ``d`` is at or beyond
        ``warning_radius`` and 0.0 when ``d`` is at or within
        ``danger_radius``. Between those boundaries the speed is
        linearly scaled so the robot slows smoothly as the human
        approaches.

        Args:
            d (float): Distance (m) from robot base to the nearest human.

        Returns:
            float: Speed scale in [0.0, ``max_speed_scale``].
        """
        c = self.cfg
        if d >= c.warning_radius:
            return c.max_speed_scale
        if d <= c.danger_radius:
            return 0.0
        t = (d - c.danger_radius) / (c.warning_radius - c.danger_radius)
        return c.min_speed_scale + t * (c.max_speed_scale - c.min_speed_scale)

    def _set_state(self, new_state: SafetyState, d: float):
        """Transition to ``new_state`` if it differs from the current state.

        Logs the transition (old → new, distance) at INFO level and
        notifies Isaac Sim via ``robot.send_state_to_sim``. If
        ``new_state`` is already the current state the call is a no-op.

        Args:
            new_state (SafetyState): The desired next state.
            d (float): Current human distance (m), included in the log
                message and the UDP notification payload.
        """
        if new_state != self.state:
            log.info("STATE  %s → %s  (d=%.2f m)", self.state.value, new_state.value, d)
            self.state = new_state
            self.robot.send_state_to_sim(new_state.value, d)

    # ── main loop ──
    def run(self):
        """Main safety loop: poll perception at ``control_hz`` and drive the state machine.

        Each iteration reads the latest ``Detection``, marks it as stale
        if its age exceeds ``stale_timeout_ms`` (and treats stale data as
        a human at distance 0 for fail-safe behaviour), then delegates to
        ``_step``. The loop sleeps for the remainder of the control period
        to maintain the target rate. Exits when ``_running`` is cleared.
        """
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
        """Execute one state-machine step given current distance and staleness.

        Transition rules:

        - **RED**: entered immediately when ``stale`` is ``True`` or
          ``d <= danger_radius``; robot is paused.
        - **RESCAN**: entered when the robot was RED and ``d`` has risen
          above ``danger_radius``; the robot remains paused for
          ``rescan_pause_ms`` to confirm the human has truly left. If
          the human re-enters the danger zone during this window, the
          state reverts to RED instantly.
        - **YELLOW**: active when ``d`` is in the warning band
          (``danger_radius < d < warning_radius``); robot runs at a
          linearly interpolated reduced speed.
        - **GREEN**: active when ``d >= clear_radius`` or when not
          currently in YELLOW; robot runs at full speed. A hysteresis
          band between ``warning_radius`` and ``clear_radius`` keeps
          the state in YELLOW until ``d`` exceeds ``clear_radius``.

        Args:
            d (float): Distance (m) from robot base to nearest human;
                0.0 when stale.
            stale (bool): ``True`` if the latest detection is older
                than ``stale_timeout_ms``.
        """
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
                self.robot.pause()  # stay stopped while confirming
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
    """Entry point: wire up components, start threads, and block until interrupted.

    Instantiates ``SafetyConfig``, ``PerceptionThread``, ``RobotInterface``,
    and ``SafetyController``; logs the active configuration; then starts
    the perception and controller threads. The main thread sleeps in a
    loop, keeping the process alive until ``KeyboardInterrupt`` (Ctrl+C).

    On interrupt, calls ``controller.stop()``, ``perception.stop()``, and
    ``robot.pause()`` (safe state) before the process exits.
    """
    cfg = SafetyConfig()

    log.info("═" * 60)
    log.info("  UR5e Safety Monitor")
    log.info("  Robot IP   : %s", cfg.robot_ip)
    log.info(
        "  YOLO model : %s  (class %d, conf ≥ %.2f)",
        cfg.yolo_weights,
        cfg.human_class_id,
        cfg.yolo_conf,
    )
    log.info(
        "  Zones      : danger=%.1fm  warning=%.1fm  clear=%.1fm",
        cfg.danger_radius,
        cfg.warning_radius,
        cfg.clear_radius,
    )
    log.info("  Sim target : %s:%d", cfg.sim_host, cfg.sim_port)
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
        robot.pause()  # safe state on exit
        log.info("Stopped.")


if __name__ == "__main__":
    main()
