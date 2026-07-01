#!/usr/bin/env python3
"""
amcrest_yolo_stream.py — Amcrest IP Camera + Custom YOLOv8 (best.pt)
=====================================================================
Detects: Human, Hard-hat  (all other classes filtered out)

  GET /video_feed   — annotated MJPEG stream
  GET /detections   — latest detections as JSON
  GET /status       — status JSON

Install:
    pip install ultralytics flask opencv-python numpy

Run:
    python amcrest_yolo_stream.py

Set CAMERA_URL below to your Amcrest RTSP or HTTP stream.
"""

import threading
import time
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, Response, jsonify
from ultralytics import YOLO

# ── Config ─────────────────────────────────────────────────────────────────────

# Amcrest stream — try RTSP first, fall back to HTTP snapshot URL
# Common Amcrest formats:
#   rtsp://admin:PASSWORD@192.168.1.X/cam/realmonitor?channel=1&subtype=0
#   http://192.168.1.X/cgi-bin/mjpg/video.cgi
CAMERA_URL = "rtsp://admin:admin@192.168.1.X/cam/realmonitor?channel=1&subtype=0"

MODEL_PATH = "best.pt"  # relative to this script's directory
PORT = 5002
HOST = "0.0.0.0"
JPEG_QUALITY = 82
CONF_THRESH = 0.45
INFER_EVERY = 2  # run inference every N frames (reduces CPU load)

# ── Classes to show ────────────────────────────────────────────────────────────
# These are matched by name (case-insensitive) against the model's class list.
# Anything not in this set is ignored.
ALLOWED_CLASSES = {"human", "hard-hat", "hardhat", "hard_hat"}

# ── Colors (BGR) ───────────────────────────────────────────────────────────────
COLOR_HUMAN = (34, 197, 94)  # green
COLOR_HARDHAT = (250, 204, 21)  # yellow
COLOR_DEFAULT = (96, 165, 250)  # blue fallback

# ── Model ──────────────────────────────────────────────────────────────────────

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, MODEL_PATH)

print(f"Loading model: {model_path}")
model = YOLO(model_path)
print("Model ready ✓")
print(f"Model classes: {model.names}")

# Build index → color map for allowed classes only
CLASS_COLOR: dict[int, tuple] = {}
CLASS_LABEL: dict[int, str] = {}
for idx, name in model.names.items():
    if (
        name.lower().replace(" ", "-") in ALLOWED_CLASSES
        or name.lower() in ALLOWED_CLASSES
    ):
        lname = name.lower()
        if "hardhat" in lname or "hard" in lname:
            CLASS_COLOR[idx] = COLOR_HARDHAT
            CLASS_LABEL[idx] = "Hard Hat ✓"
        else:
            CLASS_COLOR[idx] = COLOR_HUMAN
            CLASS_LABEL[idx] = "Human"

ALLOWED_IDS = set(CLASS_COLOR.keys())
print(f"Tracking class IDs: { {model.names[i]: i for i in ALLOWED_IDS} }")

# ── Shared state ────────────────────────────────────────────────────────────────

latest_frame = None
latest_detections = []
frame_lock = threading.Lock()
det_lock = threading.Lock()
running = True
frame_count = 0
actual_fps = 0.0
start_time = time.time()

# ── Capture + inference thread ────────────────────────────────────────────────


def capture_and_infer():
    """Background thread: capture frames from the Amcrest camera and run YOLO inference.

    Opens ``CAMERA_URL`` with OpenCV, reading frames in a loop. Every
    ``INFER_EVERY`` frames, YOLOv8 inference is run and filtered to
    ``ALLOWED_IDS`` (human / hard-hat) only. Bounding boxes, a PPE
    compliance banner, and a timestamp overlay are drawn on each frame
    before it is JPEG-encoded and stored in ``latest_frame`` for streaming.
    Latest detection metadata is stored in ``latest_detections``.

    On read failure or an unopened capture, the camera is released and
    reconnection is retried automatically after a short sleep.
    Stops when the global ``running`` flag is cleared.
    """
    global latest_frame, latest_detections, running, frame_count, actual_fps

    fps_counter = 0
    fps_timer = time.time()
    last_dets = []

    cap = None
    while running:
        # Open / reopen camera
        if cap is None or not cap.isOpened():
            print(f"Connecting to camera: {CAMERA_URL}")
            cap = cv2.VideoCapture(CAMERA_URL)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.isOpened():
                print("  Camera not reachable — retrying in 5s")
                time.sleep(5)
                cap = None
                continue
            print("Camera connected ✓")

        ret, frame = cap.read()
        if not ret:
            print("Frame read failed — reconnecting")
            cap.release()
            cap = None
            time.sleep(2)
            continue

        frame_count += 1
        img = frame.copy()

        # ── Inference ──
        if frame_count % INFER_EVERY == 0:
            results = model.predict(img, conf=CONF_THRESH, verbose=False, imgsz=640)
            dets = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    if cls_id not in ALLOWED_IDS:
                        continue
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    color = CLASS_COLOR[cls_id]
                    label = CLASS_LABEL[cls_id]
                    dets.append(
                        {
                            "cls": cls_id,
                            "name": model.names[cls_id],
                            "label": label,
                            "conf": round(conf, 3),
                            "box": [x1, y1, x2, y2],
                        }
                    )
            last_dets = dets
            with det_lock:
                latest_detections = dets

        # ── Draw ──
        h, w = img.shape[:2]
        human_count = 0
        hardhat_count = 0

        for d in last_dets:
            x1, y1, x2, y2 = d["box"]
            color = CLASS_COLOR[d["cls"]]
            label = f"{d['label']} {d['conf']:.0%}"

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            ty = max(y1 - 4, th + 4)
            cv2.rectangle(img, (x1, ty - th - bl - 2), (x1 + tw + 6, ty + 2), color, -1)
            cv2.putText(
                img,
                label,
                (x1 + 3, ty - bl),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (10, 10, 10),
                1,
                cv2.LINE_AA,
            )

            n = d["name"].lower()
            if "human" in n:
                human_count += 1
            else:
                hardhat_count += 1

        # ── Banner ──
        ppe_ok = human_count > 0 and hardhat_count >= human_count
        ppe_color = COLOR_HUMAN if ppe_ok else (0, 0, 220)
        if human_count == 0:
            banner = "NO PERSON DETECTED"
            banner_color = (100, 100, 100)
        elif ppe_ok:
            banner = f"PPE OK — {human_count} person(s) · {hardhat_count} hard hat(s)"
            banner_color = COLOR_HUMAN
        else:
            missing = human_count - hardhat_count
            banner = f"⚠ PPE VIOLATION — {missing} person(s) missing hard hat"
            banner_color = (0, 0, 220)

        cv2.rectangle(img, (0, 0), (w, 28), (0, 0, 0), -1)
        cv2.putText(
            img,
            banner,
            (10, 19),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            banner_color,
            1,
            cv2.LINE_AA,
        )

        # ── Timestamp ──
        ts = datetime.now().strftime("%H:%M:%S")
        cv2.putText(
            img,
            f"CAM-02 · Amcrest · YOLOv8 best.pt · {ts}",
            (12, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.36,
            (0, 220, 180),
            1,
            cv2.LINE_AA,
        )

        # ── Encode ──
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        with frame_lock:
            latest_frame = buf.tobytes()

        fps_counter += 1
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            actual_fps = fps_counter / elapsed
            fps_counter = 0
            fps_timer = time.time()

    if cap:
        cap.release()


# ── MJPEG ──────────────────────────────────────────────────────────────────────


def _mjpeg():
    """Generator that yields MJPEG boundary-delimited JPEG frames for Flask streaming.

    Reads ``latest_frame`` under ``frame_lock`` on every iteration.
    If no frame is available yet, sleeps briefly and retries. Each
    yielded chunk is a complete MJPEG part including the boundary
    header and ``Content-Type`` field, ready for a
    ``multipart/x-mixed-replace`` response.

    Yields:
        bytes: A single MJPEG part: boundary + headers + JPEG payload.
    """
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.02)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"


# ── Flask ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)


@app.route("/")
def index():
    """Serve the HTML status dashboard at ``/``.

    Displays the live annotated stream embedded in the page alongside
    real-time counts of detected humans and hard hats, current FPS,
    and server uptime. Links to ``/video_feed``, ``/detections``, and
    ``/status`` are included for convenience.

    Returns:
        str: An HTML page as a plain string response.
    """
    uptime = int(time.time() - start_time)
    with det_lock:
        dets = latest_detections
    humans = sum(1 for d in dets if "human" in d["name"].lower())
    hardhats = sum(1 for d in dets if "human" not in d["name"].lower())
    return f"""<html><head><title>Amcrest YOLO</title>
    <style>body{{font-family:monospace;background:#0a0a0a;color:#00e5a0;padding:30px}}
    h2{{color:#00bfff}} a{{color:#00e5a0}} img{{border:1px solid #00e5a0;max-width:100%}}
    </style></head><body>
    <h2>CAM-02 · Amcrest · best.pt</h2>
    <p>Humans: <b>{humans}</b> | Hard hats: <b>{hardhats}</b>
       | FPS: {actual_fps:.1f} | Uptime: {uptime}s</p>
    <p><a href="/video_feed">/video_feed</a> |
       <a href="/detections">/detections</a> |
       <a href="/status">/status</a></p>
    <br/><img src="/video_feed"/>
    </body></html>"""


@app.route("/video_feed")
def video_feed():
    """Stream annotated MJPEG video at ``/video_feed``.

    Wraps the ``_mjpeg()`` generator in a Flask ``Response`` with the
    ``multipart/x-mixed-replace`` MIME type so browsers and dashboard
    clients receive a continuous annotated stream.

    Returns:
        flask.Response: A streaming MJPEG response.
    """
    return Response(_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/detections")
def detections():
    """Return the latest detection list as JSON at ``/detections``.

    Reads ``latest_detections`` under ``det_lock`` and serialises it.
    Each entry contains ``cls``, ``name``, ``label``, ``conf``, and
    ``box`` (``[x1, y1, x2, y2]`` in pixels).

    Returns:
        flask.Response: JSON object with keys ``detections`` (list),
        ``count`` (int), and ``timestamp`` (ISO 8601 string).
    """
    with det_lock:
        dets = list(latest_detections)
    return jsonify(
        {
            "detections": dets,
            "count": len(dets),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/status")
def status():
    """Return server and detection status as JSON at ``/status``.

    Aggregates the current detection snapshot into a concise status
    object suitable for monitoring dashboards or health checks.

    Returns:
        flask.Response: JSON object with keys:
            ``camera`` (str), ``model`` (str), ``fps_actual`` (float),
            ``persons`` (int), ``hardhats`` (int), ``ppe_ok`` (bool),
            ``uptime_sec`` (float), ``stream_url`` (str).
    """
    with det_lock:
        dets = latest_detections
    humans = sum(1 for d in dets if "human" in d["name"].lower())
    hardhats = sum(1 for d in dets if "human" not in d["name"].lower())
    ppe_ok = humans == 0 or hardhats >= humans
    return jsonify(
        {
            "camera": "Amcrest IP",
            "model": "best.pt (custom YOLOv8)",
            "fps_actual": round(actual_fps, 1),
            "persons": humans,
            "hardhats": hardhats,
            "ppe_ok": ppe_ok,
            "uptime_sec": round(time.time() - start_time, 1),
            "stream_url": f"http://0.0.0.0:{PORT}/video_feed",
        }
    )


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--camera", default=CAMERA_URL, help="Camera URL (RTSP or HTTP stream)"
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=CONF_THRESH,
        help="Confidence threshold (default 0.45)",
    )
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    CAMERA_URL = args.camera
    CONF_THRESH = args.conf
    PORT = args.port

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
