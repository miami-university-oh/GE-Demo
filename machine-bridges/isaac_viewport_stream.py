"""
Isaac Sim Viewport MJPEG Streamer
=================================
Run this in Isaac Sim's Script Editor (or as an extension script).
It captures the active viewport and serves an MJPEG stream at http://localhost:8211

Usage (in Isaac Sim Script Editor):
    exec(open(r"C:\Users\yousifi\Documents\GE Demo\machine-bridges\isaac_viewport_stream.py").read())
"""

import threading
import time
import io
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import omni.kit.viewport.utility as vp_util
    from omni.kit.widget.viewport.capture import ByteCapture
    import carb
except ImportError:
    raise RuntimeError("This script must run inside Isaac Sim")

STREAM_PORT = 8211
CAPTURE_FPS = 20
JPEG_QUALITY = 75

_latest_jpeg = None
_lock = threading.Lock()
_running = True


def _capture_viewport_loop():
    """Continuously capture the active viewport to JPEG bytes."""
    global _latest_jpeg, _running

    try:
        import omni.renderer_capture
        import omni.kit.viewport.utility as vp_util
    except Exception as e:
        carb.log_error(f"Viewport stream: import error: {e}")
        return

    interval = 1.0 / CAPTURE_FPS

    while _running:
        try:
            viewport_api = vp_util.get_active_viewport()
            if viewport_api is None:
                time.sleep(0.5)
                continue

            import asyncio
            import omni.kit.app

            # Use the capture_viewport_to_buffer approach
            capture_completed = threading.Event()
            jpeg_data = [None]

            def on_capture_completed(buffer, buffer_size, width, height, fmt):
                try:
                    import ctypes
                    # buffer is a ctypes pointer, copy to numpy
                    arr = np.ctypeslib.as_array(
                        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8)),
                        shape=(height, width, 4)
                    )
                    # RGBA -> BGR for cv2
                    import cv2
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                    # Resize for streaming
                    if width > 1280:
                        scale = 1280 / width
                        bgr = cv2.resize(bgr, (1280, int(height * scale)))
                    _, buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    jpeg_data[0] = buf.tobytes()
                except Exception as e:
                    carb.log_warn(f"Viewport capture encode error: {e}")
                finally:
                    capture_completed.set()

            viewport_api.schedule_capture(ByteCapture(on_capture_completed))
            capture_completed.wait(timeout=2.0)

            if jpeg_data[0] is not None:
                with _lock:
                    _latest_jpeg = jpeg_data[0]

        except Exception as e:
            carb.log_warn(f"Viewport capture error: {e}")

        time.sleep(interval)


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        Handle GET requests for the viewport stream server.

        Routes:
            ``/`` or ``/stream`` — Returns a minimal HTML page that embeds
            the MJPEG feed in an ``<img>`` tag.

            ``/feed`` — Streams MJPEG frames at ``CAPTURE_FPS`` using
            ``multipart/x-mixed-replace``.  Stops on ``BrokenPipeError``
            or ``ConnectionResetError`` (client disconnect).

            ``/snapshot`` — Returns the most recent captured JPEG as a
            single ``image/jpeg`` response; responds with 503 if no frame
            is available yet.

            Anything else — 404 Not Found.
        """
        if self.path == "/" or self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>Isaac Sim Viewport</title>
<style>body{margin:0;background:#000;display:flex;align-items:center;justify-content:center;height:100vh}
img{max-width:100%;max-height:100%}</style></head>
<body><img src="/feed"></body></html>""")

        elif self.path == "/feed":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            while _running:
                with _lock:
                    frame = _latest_jpeg
                if frame is None:
                    time.sleep(0.05)
                    continue
                try:
                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                        + frame + b"\r\n"
                    )
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
                time.sleep(1.0 / CAPTURE_FPS)

        elif self.path == "/snapshot":
            with _lock:
                frame = _latest_jpeg
            if frame:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
            else:
                self.send_response(503)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        """Suppress default access-log output to keep the Isaac Sim console clean."""
        pass


def _start_server():
    """Bind an ``HTTPServer`` on all interfaces at ``STREAM_PORT`` and serve forever.

    Intended to run in a daemon thread alongside ``_capture_viewport_loop``.
    """
    server = HTTPServer(("0.0.0.0", STREAM_PORT), MJPEGHandler)
    carb.log_info(f"Viewport MJPEG stream at http://localhost:{STREAM_PORT}")
    server.serve_forever()


# Start capture and server threads
_capture_thread = threading.Thread(target=_capture_viewport_loop, daemon=True)
_capture_thread.start()

_server_thread = threading.Thread(target=_start_server, daemon=True)
_server_thread.start()

print(f"✓ Isaac Sim viewport streaming at http://localhost:{STREAM_PORT}")
print(f"  MJPEG feed: http://localhost:{STREAM_PORT}/feed")
print(f"  Snapshot:   http://localhost:{STREAM_PORT}/snapshot")
