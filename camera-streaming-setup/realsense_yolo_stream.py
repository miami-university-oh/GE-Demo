#!/usr/bin/env python3
"""
realsense_yolo_stream.py — RealSense L515 + YOLOv8n-Pose
=========================================================
Single model detects persons AND body keypoints (shoulders, elbows,
wrists, hips, knees, ankles). Arms are drawn as a skeleton overlay.
Alerts when wrists enter the robot zone ring.

  GET /video_feed   — annotated MJPEG stream
  GET /detections   — latest detections as JSON
  GET /status       — status JSON

Install:
    pip install ultralytics pyrealsense2 flask opencv-python numpy

Run:
    python realsense_yolo_stream.py
"""

import threading
import time
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, Response, jsonify
import pyrealsense2 as rs
from ultralytics import YOLO

# ── Config ─────────────────────────────────────────────────────────────────────

WIDTH        = 1280
HEIGHT       = 720
FPS          = 30
PORT         = 5001
HOST         = "0.0.0.0"
JPEG_QUALITY = 85
CONF_THRESH  = 0.5
INFER_EVERY  = 3

# Radius from frame center (px) that triggers the proximity alert
ALERT_ZONE_PX = 320

# ── Colors (BGR) ───────────────────────────────────────────────────────────────

COLOR_PERSON = (94,  197,  34)   # green  — person box
COLOR_SAFE   = (94,  197,  34)   # green  — skeleton / joints safe
COLOR_ALERT  = (68,   68, 239)   # red    — wrist/elbow in zone
COLOR_ZONE   = (21,  204, 250)   # yellow — robot zone ring

# ── YOLOv8n-pose keypoint indices (COCO 17-point) ─────────────────────────────
#   0=nose  1=l_eye  2=r_eye  3=l_ear  4=r_ear
#   5=l_shoulder  6=r_shoulder  7=l_elbow  8=r_elbow
#   9=l_wrist    10=r_wrist    11=l_hip  12=r_hip
#  13=l_knee     14=r_knee     15=l_ankle 16=r_ankle

KP_NAMES = {
    5: "L_SHOULDER", 6: "R_SHOULDER",
    7: "L_ELBOW",    8: "R_ELBOW",
    9: "L_WRIST",   10: "R_WRIST",
}

# Skeleton connections to draw (index pairs)
SKELETON = [
    (5,  6),   # shoulder — shoulder
    (5,  7),   # l_shoulder — l_elbow
    (7,  9),   # l_elbow — l_wrist
    (6,  8),   # r_shoulder — r_elbow
    (8, 10),   # r_elbow — r_wrist
    (5, 11),   # l_shoulder — l_hip
    (6, 12),   # r_shoulder — r_hip
    (11,12),   # hip — hip
    (11,13),   # l_hip — l_knee
    (12,14),   # r_hip — r_knee
    (13,15),   # l_knee — l_ankle
    (14,16),   # r_knee — r_ankle
]

ALERT_KP_IDS = {7, 8, 9, 10}   # elbows + wrists trigger alert

# ── Find RealSense device ─────────────────────────────────────────────────────

def _find_realsense_device():
    ctx = rs.context()
    devices = ctx.query_devices()
    if len(devices) == 0:
        print("No Intel RealSense device connected.")
        print("  -> Connect the L515, close RealSense Viewer, and try again.")
        return None
    dev = devices[0]
    name = dev.get_info(rs.camera_info.name)
    serial = dev.get_info(rs.camera_info.serial_number)
    print(f"Found RealSense device: {name} (S/N {serial})")
    return dev


# ── Model (auto-downloads ~6 MB on first run) ──────────────────────────────────

print("Loading YOLOv8n-pose (auto-downloads if not cached)...")
model = YOLO("yolov8n-pose.pt")
print("Model ready ✓")

# ── RealSense pipeline ──────────────────────────────────────────────────────────

device = _find_realsense_device()
if device is None:
    raise SystemExit(1)

pipeline  = rs.pipeline()
rs_config = rs.config()
rs_config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.bgr8, FPS)
try:
    pipeline.start(rs_config)
    print(f"RealSense started: {WIDTH}x{HEIGHT} @ {FPS} FPS ✓\n")
except Exception as e:
    print(f"RealSense failed: {e}\n  → Close RealSense Viewer if open")
    raise SystemExit(1)

# ── Shared state ────────────────────────────────────────────────────────────────

latest_frame      = None
latest_detections = []
frame_lock        = threading.Lock()
det_lock          = threading.Lock()
running           = True
frame_count       = 0
actual_fps        = 0.0
start_time        = time.time()


# ── Draw helpers ────────────────────────────────────────────────────────────────

def _in_zone(px: int, py: int) -> bool:
    cx, cy = WIDTH // 2, HEIGHT // 2
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 < ALERT_ZONE_PX


def _draw_zone(img):
    cx, cy = WIDTH // 2, HEIGHT // 2
    cv2.circle(img, (cx, cy), ALERT_ZONE_PX, COLOR_ZONE, 1, cv2.LINE_AA)
    cv2.putText(img, "ROBOT ZONE", (cx - 45, cy - ALERT_ZONE_PX - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_ZONE, 1, cv2.LINE_AA)


def _draw_person(img, x1, y1, x2, y2, conf, alert):
    color = COLOR_ALERT if alert else COLOR_PERSON
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    label = f"{'!! ' if alert else ''}PERSON {conf:.0%}"
    (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    ty = max(y1 - 4, th + 4)
    cv2.rectangle(img, (x1, ty - th - bl - 2), (x1 + tw + 6, ty + 2), color, -1)
    cv2.putText(img, label, (x1 + 3, ty - bl),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)


def _draw_keypoints(img, kps, alert_kps: set):
    """kps: list of (x, y, conf) tuples; alert_kps: set of kp indices in zone."""
    # Draw skeleton connections
    for a, b in SKELETON:
        if a >= len(kps) or b >= len(kps):
            continue
        ax, ay, ac = kps[a]
        bx, by, bc = kps[b]
        if ac < 0.3 or bc < 0.3:
            continue
        in_alert = a in alert_kps or b in alert_kps
        cv2.line(img, (ax, ay), (bx, by),
                 COLOR_ALERT if in_alert else COLOR_SAFE, 2, cv2.LINE_AA)

    # Draw joints
    for idx, (px, py, pc) in enumerate(kps):
        if pc < 0.3:
            continue
        in_alert = idx in alert_kps
        color = COLOR_ALERT if in_alert else COLOR_SAFE
        cv2.circle(img, (px, py), 5, color, -1, cv2.LINE_AA)
        cv2.circle(img, (px, py), 5, (255, 255, 255), 1, cv2.LINE_AA)
        # Label arm joints only
        if idx in KP_NAMES:
            short = KP_NAMES[idx].split("_")[1]
            cv2.putText(img, short, (px + 6, py - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1, cv2.LINE_AA)


def _draw_banner(img, num_people, alert_names):
    if alert_names:
        color = COLOR_ALERT
        msg   = f"!! ARM IN ROBOT ZONE — {', '.join(alert_names)}"
    elif num_people:
        color = COLOR_SAFE
        msg   = f"PERSON DETECTED ({num_people})  — arms tracked"
    else:
        color = (120, 120, 120)
        msg   = "NO PERSON IN FRAME"
    cv2.rectangle(img, (0, 0), (WIDTH, 26), (0, 0, 0), -1)
    cv2.putText(img, msg, (10, 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1, cv2.LINE_AA)


def _draw_timestamp(img):
    ts = datetime.now().strftime("%H:%M:%S")
    cv2.putText(img, f"CAM-01 · RealSense L515 · YOLOv8n-pose · {ts}",
                (12, HEIGHT - 12), cv2.FONT_HERSHEY_SIMPLEX,
                0.38, (0, 220, 180), 1, cv2.LINE_AA)


# ── Capture + inference thread ───────────────────────────────────────────────────

def capture_and_infer():
    global latest_frame, latest_detections, running, frame_count, actual_fps

    fps_counter = 0
    fps_timer   = time.time()
    last_dets   = []

    while running:
        try:
            frames      = pipeline.wait_for_frames(timeout_ms=5000)
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            img = np.asanyarray(color_frame.get_data()).copy()
            frame_count += 1

            if frame_count % INFER_EVERY == 0:
                results = model.predict(
                    img, conf=CONF_THRESH, verbose=False, imgsz=640,
                )

                dets = []
                for r in results:
                    if r.boxes is None:
                        continue
                    for i, box in enumerate(r.boxes):
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])

                        # Keypoints for this person
                        kps = []
                        alert_kps = set()
                        alert_names = []
                        if r.keypoints is not None and i < len(r.keypoints.data):
                            kp_data = r.keypoints.data[i].cpu().numpy()
                            for kid, (kx, ky, kc) in enumerate(kp_data):
                                px, py = int(kx), int(ky)
                                kps.append((px, py, float(kc)))
                                if float(kc) > 0.3 and kid in ALERT_KP_IDS and _in_zone(px, py):
                                    alert_kps.add(kid)
                                    alert_names.append(KP_NAMES.get(kid, str(kid)))

                        dets.append({
                            "box":         [x1, y1, x2, y2],
                            "conf":        round(conf, 3),
                            "keypoints":   kps,
                            "alert_kps":   list(alert_kps),
                            "alert_names": alert_names,
                        })

                last_dets = dets
                with det_lock:
                    latest_detections = dets

            # ── Draw ──
            all_alert_names = []
            for p in last_dets:
                alert = bool(p["alert_kps"])
                x1, y1, x2, y2 = p["box"]
                _draw_person(img, x1, y1, x2, y2, p["conf"], alert)
                _draw_keypoints(img, p["keypoints"], set(p["alert_kps"]))
                all_alert_names.extend(p["alert_names"])

            _draw_zone(img)
            _draw_banner(img, len(last_dets), all_alert_names)
            _draw_timestamp(img)

            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            with frame_lock:
                latest_frame = buf.tobytes()

            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                actual_fps  = fps_counter / elapsed
                fps_counter = 0
                fps_timer   = time.time()

        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(0.1)


# ── MJPEG ──────────────────────────────────────────────────────────────────────

def _mjpeg():
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.01)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


# ── Flask ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def index():
    uptime = int(time.time() - start_time)
    with det_lock:
        dets  = latest_detections
    n     = len(dets)
    names = [n for p in dets for n in p.get("alert_names", [])]
    return f"""<html><head><title>RealSense Pose</title>
    <style>body{{font-family:monospace;background:#0a0a0a;color:#00e5a0;padding:30px}}
    h2{{color:#00bfff}} a{{color:#00e5a0}} img{{border:1px solid #00e5a0;max-width:100%}}
    </style></head><body>
    <h2>RealSense L515 · YOLOv8n-pose</h2>
    <p>Persons: <b>{n}</b> | Arms in zone: <b>{'!! ' + ', '.join(names) if names else 'CLEAR'}</b>
       | FPS: {actual_fps:.1f} | Uptime: {uptime}s</p>
    <p><a href="/video_feed">/video_feed</a> | <a href="/detections">/detections</a>
       | <a href="/status">/status</a></p>
    <br/><img src="/video_feed"/>
    </body></html>"""

@app.route("/video_feed")
def video_feed():
    return Response(_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/detections")
def detections():
    with det_lock:
        dets = list(latest_detections)
    return {"detections": dets, "count": len(dets), "timestamp": datetime.now().isoformat()}

@app.route("/status")
def status():
    with det_lock:
        dets = latest_detections
    alert = any(p.get("alert_kps") for p in dets)
    return {
        "camera":     "Intel RealSense L515",
        "model":      "YOLOv8n-pose",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps_actual": round(actual_fps, 1),
        "persons":    len(dets),
        "zone_alert": alert,
        "uptime_sec": round(time.time() - start_time, 1),
        "stream_url": f"http://0.0.0.0:{PORT}/video_feed",
    }

# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=capture_and_infer, daemon=True).start()
    print(f"Stream:     http://YOUR-PC-IP:{PORT}/video_feed")
    print(f"Detections: http://YOUR-PC-IP:{PORT}/detections")
    print(f"Press Ctrl+C to stop\n")
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        running = False
        time.sleep(0.5)
        pipeline.stop()
        print("Done.")
