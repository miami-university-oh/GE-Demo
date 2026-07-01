#!/usr/bin/env python3
"""
realsense_stream.py — Intel RealSense L515 RGB MJPEG Stream Server
===================================================================
Streams the RealSense L515 RGB color feed as MJPEG over HTTP.
The dashboard connects to http://THIS-PC-IP:5001/video_feed

Usage:
    python realsense_stream.py

Endpoints:
    GET /           — Status page
    GET /video_feed — MJPEG stream (use directly in dashboard)
    GET /status     — JSON status: fps, frame_count, resolution, running

Press Ctrl+C to stop.
"""

import threading
import time

import cv2
import numpy as np
import pyrealsense2 as rs
from flask import Flask, Response, jsonify

# ── Config ──────────────────────────────────────────────────────────────────
WIDTH = 1280
HEIGHT = 720
FPS = 30
PORT = 5001  # Port for this stream (5000 is used by Amcrest proxy)
HOST = "0.0.0.0"
QUALITY = 85  # JPEG quality 1-100 (85 is a good balance)
# ────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

# Shared state
latest_frame = None
frame_lock = threading.Lock()
running = True
frame_count = 0
start_time = time.time()
actual_fps = 0.0

# ── RealSense pipeline ───────────────────────────────────────────────────────

pipeline = rs.pipeline()
config = rs.config()

config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.bgr8, FPS)

try:
    profile = pipeline.start(config)
    print(f"✓ RealSense pipeline started: {WIDTH}x{HEIGHT} @ {FPS} FPS")
except Exception as e:
    print(f"✗ Failed to start RealSense pipeline: {e}")
    print("  → Close Intel RealSense Viewer if it is open (it locks the camera)")
    raise

# ── Frame capture thread ─────────────────────────────────────────────────────


def capture_frames():
    """Background thread: pull color frames from the RealSense pipeline and encode them.

    Waits on the RealSense pipeline for color frames (5 s timeout), overlays
    a ``CAM-01`` timestamp string at the bottom-left of each frame, and
    JPEG-encodes the result into ``latest_frame`` under ``frame_lock``.
    Increments ``frame_count`` on every successful encode and updates
    ``actual_fps`` once per second. Exceptions are caught, logged, and
    retried after a 100 ms sleep so transient frame errors don't crash
    the thread. Stops when ``running`` is cleared.
    """
    global latest_frame, running, frame_count, actual_fps

    fps_counter = 0
    fps_timer = time.time()

    while running:
        try:
            frames = pipeline.wait_for_frames(timeout_ms=5000)
            color_frame = frames.get_color_frame()

            if not color_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())

            # Add a subtle timestamp overlay (bottom-left, small)
            ts = time.strftime("%H:%M:%S")
            cv2.putText(
                color_image,
                f"CAM-01 · RealSense L515 · {ts}",
                (12, HEIGHT - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 220, 180),
                1,
                cv2.LINE_AA,
            )

            encode_params = [cv2.IMWRITE_JPEG_QUALITY, QUALITY]
            success, buffer = cv2.imencode(".jpg", color_image, encode_params)
            if not success:
                continue

            with frame_lock:
                latest_frame = buffer.tobytes()

            frame_count += 1
            fps_counter += 1

            # Update FPS every second
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                actual_fps = fps_counter / elapsed
                fps_counter = 0
                fps_timer = time.time()

        except Exception as e:
            print(f"  Capture error: {e}")
            time.sleep(0.1)


# ── MJPEG generator ──────────────────────────────────────────────────────────


def generate_mjpeg():
    """Generator that yields MJPEG multipart frames from ``latest_frame``.

    Reads ``latest_frame`` under ``frame_lock`` on every iteration.
    If no frame is available yet, sleeps 10 ms and retries. Each
    yielded chunk is a fully-formed MJPEG part (boundary line,
    ``Content-Type`` header, blank line, JPEG bytes) suitable for a
    ``multipart/x-mixed-replace`` HTTP response.

    Yields:
        bytes: A single MJPEG part ready for streaming.
    """
    while True:
        with frame_lock:
            frame = latest_frame

        if frame is None:
            time.sleep(0.01)
            continue

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


# ── Flask routes ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Serve the HTML status page at ``/``.

    Displays stream status (frame count, live FPS, uptime) and embeds
    the live MJPEG stream in the page. Links to ``/video_feed`` and
    ``/status`` are included.

    Returns:
        str: An HTML page as a plain string response.
    """
    uptime = int(time.time() - start_time)
    return f"""
    <html>
    <head><title>RealSense L515 Stream</title>
    <style>
      body {{ font-family: monospace; background: #0a0a0a; color: #00e5a0; padding: 30px; }}
      h2 {{ color: #00bfff; }} a {{ color: #00e5a0; }}
      img {{ border: 1px solid #00e5a0; border-radius: 4px; max-width: 100%; }}
    </style></head>
    <body>
      <h2>RealSense L515 — RGB Stream</h2>
      <p>Status: <b>RUNNING</b> | Frames: {frame_count} | FPS: {actual_fps:.1f} | Uptime: {uptime}s</p>
      <p>Stream URL: <a href="/video_feed">http://{HOST}:{PORT}/video_feed</a></p>
      <p>Status JSON: <a href="/status">/status</a></p>
      <br/>
      <img src="/video_feed" alt="Live RGB Stream" />
    </body>
    </html>
    """


@app.route("/video_feed")
def video_feed():
    """Stream live MJPEG video at ``/video_feed``.

    Wraps the ``generate_mjpeg()`` generator in a Flask ``Response``
    with the ``multipart/x-mixed-replace`` MIME type. Compatible with
    ``<img>`` tags and most dashboard clients.

    Returns:
        flask.Response: A streaming MJPEG response.
    """
    return Response(
        generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/status")
def status():
    """Return camera and stream status as JSON at ``/status``.

    Returns:
        flask.Response: JSON object with keys:
            ``camera`` (str), ``stream`` (str), ``resolution`` (str),
            ``fps_target`` (int), ``fps_actual`` (float),
            ``frame_count`` (int), ``uptime_sec`` (float),
            ``running`` (bool), ``stream_url`` (str).
    """
    return jsonify(
        {
            "camera": "Intel RealSense L515",
            "stream": "RGB Color",
            "resolution": f"{WIDTH}x{HEIGHT}",
            "fps_target": FPS,
            "fps_actual": round(actual_fps, 1),
            "frame_count": frame_count,
            "uptime_sec": round(time.time() - start_time, 1),
            "running": running,
            "stream_url": f"http://0.0.0.0:{PORT}/video_feed",
        }
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    print(f"✓ Capture thread started")
    print(f"✓ Stream available at: http://YOUR-PC-IP:{PORT}/video_feed")
    print(f"✓ Status JSON at:      http://YOUR-PC-IP:{PORT}/status")
    print(f"  Press Ctrl+C to stop\n")

    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        running = False
        time.sleep(0.5)
        pipeline.stop()
        print("Pipeline stopped.")
