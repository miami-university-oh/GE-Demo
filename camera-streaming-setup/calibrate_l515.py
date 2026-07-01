"""
calibrate_l515.py
─────────────────
Interactive calibration tool for a ceiling-mounted Intel RealSense L515.

What it does:
  1. Streams aligned color + depth from the L515.
  2. You click points on the live view → it prints their 3D camera coords.
  3. Click the ROBOT BASE to get robot_base_xy.
  4. Click FLOOR MARKERS to compute camera height and T_cam_floor.
  5. Outputs ready-to-paste values for safety_monitor.py.

Usage:
    pip install pyrealsense2 opencv-python numpy
    python calibrate_l515.py

Controls:
    Left-click   → record a calibration point
    'r'          → mark the LAST clicked point as the robot base
    'h'          → compute camera height from all clicked floor points
    'm'          → compute and print the final T_cam_floor matrix
    'q' / ESC    → quit and print summary

Instructions:
    1. Place 3-4 flat objects (tape squares, paper) on the floor at known
       positions around the robot. These are your floor markers.
    2. Run this script.
    3. Click each floor marker → note the 3D coords printed.
    4. Click the center of the UR5e base plate → press 'r'.
    5. Press 'h' to compute camera height.
    6. Press 'm' to get your T_cam_floor matrix.
    7. Press 'q' → copy the printed values into safety_monitor.py.
"""

import sys

import cv2
import numpy as np
import pyrealsense2 as rs

# ── State ──
clicked_points = []  # list of (u, v, x_cam, y_cam, z_cam, depth_m)
robot_base_point = None  # (x_cam, y_cam, z_cam)
camera_height = None


def mouse_callback(event, x, y, flags, param):
    """OpenCV mouse callback: deproject a clicked pixel to 3D camera coordinates.

    Fires only on ``cv2.EVENT_LBUTTONDOWN``. Reads the depth value at the
    clicked pixel from the current ``depth_frame`` stored in ``param``,
    rejects readings outside the valid range (0.05 m – 6.0 m), then calls
    ``rs.rs2_deproject_pixel_to_point`` to convert the pixel + depth to a
    3D point in camera space. The result is appended to ``clicked_points``
    and printed to stdout.

    Args:
        event (int): OpenCV mouse event code.
        x (int): Horizontal pixel coordinate of the click (image space).
        y (int): Vertical pixel coordinate of the click (image space).
        flags (int): OpenCV event flags (unused).
        param (dict): Shared state dict containing:
            ``depth_frame`` (rs.depth_frame | None),
            ``intrinsics`` (rs.intrinsics),
            ``w`` (int) frame width,
            ``h`` (int) frame height.
    """
    if event != cv2.EVENT_LBUTTONDOWN:
        return

    depth_frame, intrinsics = param["depth_frame"], param["intrinsics"]
    if depth_frame is None:
        return

    # Clamp to frame bounds.
    u = max(0, min(x, param["w"] - 1))
    v = max(0, min(y, param["h"] - 1))

    depth_m = depth_frame.get_distance(u, v)
    if depth_m < 0.05 or depth_m > 6.0:
        print(f"  ⚠  Bad depth at ({u}, {v}): {depth_m:.3f} m — try nearby pixel")
        return

    # Deproject to 3D camera coordinates.
    point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_m)
    x_cam, y_cam, z_cam = point_3d

    idx = len(clicked_points)
    clicked_points.append((u, v, x_cam, y_cam, z_cam, depth_m))

    print(f"\n  Point #{idx}:")
    print(f"    Pixel      : ({u}, {v})")
    print(f"    Depth      : {depth_m:.4f} m")
    print(f"    Camera XYZ : ({x_cam:.4f}, {y_cam:.4f}, {z_cam:.4f}) m")
    print(f"    (press 'r' to mark this as robot base)")


def compute_camera_height():
    """Estimate camera mounting height by averaging depth across clicked floor points.

    Computes the mean and standard deviation of the raw depth values
    (``clicked_points[:][5]``) collected so far and stores the mean in
    the global ``camera_height``. Prints both statistics and warns when
    the standard deviation exceeds 0.02 m, which may indicate floor
    tilt or accidental clicks on non-floor objects.

    Requires at least one point in ``clicked_points``; prints a warning
    and returns early if the list is empty.
    """
    global camera_height
    if len(clicked_points) < 1:
        print("  ⚠  Click at least 1 floor point first.")
        return

    depths = [p[5] for p in clicked_points]
    camera_height = float(np.mean(depths))
    std = float(np.std(depths)) if len(depths) > 1 else 0.0

    print(f"\n  ═══ Camera Height ═══")
    print(f"    Points used : {len(depths)}")
    print(f"    Mean depth  : {camera_height:.4f} m")
    print(f"    Std dev     : {std:.4f} m")
    if std > 0.02:
        print(
            f"    ⚠  High variance — floor may not be flat, or points are on objects."
        )
    print(f"    → Camera is ~{camera_height:.3f} m above the floor.\n")


def compute_matrix():
    """Build and print the 4x4 ``T_cam_floor`` extrinsic transform.

    Constructs the rigid-body transform that maps 3D points from camera
    space to floor (world) space, assuming the camera is mounted on the
    ceiling pointing straight down::

        T_cam_floor = [[ 1,  0,  0,   tx ],
                       [ 0,  1,  0,   ty ],
                       [ 0,  0, -1,   H  ],
                       [ 0,  0,  0,   1  ]]

    where ``H`` is the camera height computed by ``compute_camera_height``
    and ``tx``/``ty`` default to 0 (floor origin directly below the camera).

    Prints:
        - Paste-ready ``self.T_cam_floor`` code for ``safety_monitor.py``.
        - Verification table showing floor-frame Z for each clicked point
          (should be ≈ 0 for floor markers).
        - Paste-ready ``robot_base_xy`` value for ``SafetyConfig`` if the
          robot base has been marked with ``'r'``.

    Requires ``camera_height`` to have been set first (press ``'h'``).
    Returns early with a warning if it has not.

    Note:
        For a straight-down ceiling mount::

            p_floor = T_cam_floor @ p_cam

        Camera Z axis points toward the floor (positive Z = downward).
    """
    global camera_height
    if camera_height is None:  # noqa: F821  (module-level global)
        print("  ⚠  Press 'h' first to compute camera height.")
        return

    # If floor origin = directly below camera, no lateral offset.
    # If you want a different origin, measure tx/ty.
    tx, ty = 0.0, 0.0

    T = np.array(
        [
            [1.0, 0.0, 0.0, tx],
            [0.0, 1.0, 0.0, ty],
            [0.0, 0.0, -1.0, camera_height],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )

    print(f"\n  ═══════════════════════════════════════════════════")
    print(f"  PASTE THIS INTO safety_monitor.py → PerceptionThread.__init__")
    print(f"  ═══════════════════════════════════════════════════")
    print(f"  self.T_cam_floor = np.array([")
    for row in T:
        print(f"      [{row[0]:7.4f}, {row[1]:7.4f}, {row[2]:7.4f}, {row[3]:7.4f}],")
    print(f"  ])")
    print()

    # Verify: transform each clicked point to floor coords.
    print(f"  ── Verification (each floor point should have Z ≈ 0) ──")
    for i, (u, v, xc, yc, zc, d) in enumerate(clicked_points):
        p = T @ np.array([xc, yc, zc, 1.0])
        label = (
            " ← ROBOT BASE"
            if robot_base_point
            and np.allclose([xc, yc, zc], robot_base_point, atol=0.001)
            else ""
        )
        print(f"    Point #{i}: floor=({p[0]:+.4f}, {p[1]:+.4f}, {p[2]:+.4f}){label}")
    print()

    # Robot base in floor frame.
    if robot_base_point is not None:
        rb = T @ np.array([*robot_base_point, 1.0])
        print(f"  ═══════════════════════════════════════════════════")
        print(f"  PASTE THIS INTO safety_monitor.py → SafetyConfig")
        print(f"  ═══════════════════════════════════════════════════")
        print(f"  robot_base_xy: Tuple[float, float] = ({rb[0]:.4f}, {rb[1]:.4f})")
        print()
    else:
        print(
            f"  ⚠  Robot base not marked. Click the UR5e base, press 'r', then 'm' again."
        )


def main():
    """Run the interactive L515 calibration loop.

    Starts the RealSense pipeline, displays a live aligned color + depth
    view, and registers a mouse callback so the operator can click floor
    markers and the robot base directly in the image. The overlay renders
    each recorded point with its index and depth reading.

    Keyboard shortcuts during the loop:
        ``left-click`` — record a floor/robot calibration point.
        ``r``          — mark the last clicked point as the robot base.
        ``h``          — compute camera height from all clicked points.
        ``m``          — compute and print the ``T_cam_floor`` matrix.
        ``q`` / ESC    — quit and print a calibration summary.

    Prints a calibration summary (camera height, robot base in camera
    space, total point count) on exit.
    """
    global robot_base_point

    # ── RealSense setup ──
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

    print("\n  Starting L515… ", end="", flush=True)
    try:
        profile = pipeline.start(cfg)
    except RuntimeError as e:
        print(f"\n  ✗ Could not start camera: {e}")
        print("    Is the L515 plugged in? Is another process using it?")
        sys.exit(1)
    print("OK")

    align = rs.align(rs.stream.color)
    depth_stream = profile.get_stream(rs.stream.depth).as_video_stream_profile()
    intrinsics = depth_stream.get_intrinsics()

    print(
        f"  Intrinsics: fx={intrinsics.fx:.1f}  fy={intrinsics.fy:.1f}  "
        f"ppx={intrinsics.ppx:.1f}  ppy={intrinsics.ppy:.1f}"
    )
    print(f"  Resolution: {intrinsics.width}×{intrinsics.height}")

    # Shared state for mouse callback.
    cb_data = {
        "depth_frame": None,
        "intrinsics": intrinsics,
        "w": intrinsics.width,
        "h": intrinsics.height,
    }

    win = "L515 Calibration (click floor points, 'r'=robot, 'h'=height, 'm'=matrix, 'q'=quit)"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(win, mouse_callback, cb_data)

    print("\n  ── Ready ──")
    print("  • Click floor points and the robot base on the live view.")
    print("  • Press 'r' after clicking the robot base.")
    print("  • Press 'h' to compute camera height.")
    print("  • Press 'm' to generate the calibration matrix.")
    print("  • Press 'q' or ESC to quit.\n")

    try:
        while True:
            frames = pipeline.wait_for_frames()
            aligned = align.process(frames)
            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            cb_data["depth_frame"] = depth_frame
            color_img = np.asanyarray(color_frame.get_data())

            # Draw clicked points on the image.
            display = color_img.copy()
            for i, (u, v, xc, yc, zc, d) in enumerate(clicked_points):
                is_robot = robot_base_point is not None and np.allclose(
                    [xc, yc, zc], robot_base_point, atol=0.001
                )
                color = (0, 0, 255) if is_robot else (0, 255, 0)
                cv2.circle(display, (u, v), 8, color, 2)
                label = f"#{i} R" if is_robot else f"#{i}"
                cv2.putText(
                    display,
                    f"{label} d={d:.2f}m",
                    (u + 12, v - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

            # Show depth at cursor (top-left HUD).
            cv2.putText(
                display,
                f"Points: {len(clicked_points)}  |  Height: {camera_height:.3f}m"
                if camera_height
                else f"Points: {len(clicked_points)}  |  Height: (press 'h')",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

            cv2.imshow(win, display)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):  # q or ESC
                break

            elif key == ord("r"):
                if clicked_points:
                    last = clicked_points[-1]
                    robot_base_point = (last[2], last[3], last[4])
                    print(
                        f"\n  ✓ Robot base set to Point #{len(clicked_points) - 1}: "
                        f"cam=({last[2]:.4f}, {last[3]:.4f}, {last[4]:.4f})"
                    )
                else:
                    print("  ⚠  Click a point first, then press 'r'.")

            elif key == ord("h"):
                compute_camera_height()

            elif key == ord("m"):
                compute_matrix()

    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

    # ── Final summary ──
    print("\n  ════════════════════════════════")
    print("  CALIBRATION SUMMARY")
    print("  ════════════════════════════════")
    if camera_height:
        print(f"  Camera height : {camera_height:.4f} m")
    if robot_base_point:
        print(
            f"  Robot base (cam): ({robot_base_point[0]:.4f}, "
            f"{robot_base_point[1]:.4f}, {robot_base_point[2]:.4f})"
        )
    print(f"  Total points  : {len(clicked_points)}")
    if camera_height:
        print(f"\n  Run with 'm' key to get paste-ready values.")
    print()


if __name__ == "__main__":
    main()
