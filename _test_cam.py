"""Minimal RealSense L515 test — serves MJPEG at http://localhost:5555"""
import pyrealsense2 as rs
import numpy as np
import cv2
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

pipeline = None
align = None
running = True

def start_camera():
    global pipeline, align
    pipeline = rs.pipeline()
    config = rs.config()

    # Try configs in order until one works
    configs = [
        ("1920x1080 color + 1024x768 depth", lambda c: (
            c.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30),
            c.enable_stream(rs.stream.depth, 1024, 768, rs.format.z16, 30),
        )),
        ("1920x1080 color + 640x480 depth", lambda c: (
            c.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30),
            c.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30),
        )),
        ("1280x720 color + 640x480 depth", lambda c: (
            c.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30),
            c.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30),
        )),
        ("1920x1080 color only", lambda c: (
            c.enable_stream(rs.stream.color, 1920, 1080, rs.format.bgr8, 30),
        )),
        ("auto (no constraints)", lambda c: None),
    ]

    for desc, setup_fn in configs:
        try:
            config = rs.config()
            setup_fn(config)
            profile = pipeline.start(config)
            device = profile.get_device()
            print(f"SUCCESS: {desc}")
            print(f"  Device: {device.get_info(rs.camera_info.name)}")
            align = rs.align(rs.stream.color)

            # Print active streams
            for s in profile.get_streams():
                vp = s.as_video_stream_profile()
                print(f"  Active: {s.stream_type()} {vp.width()}x{vp.height()} @{s.fps()} {s.format()}")
            return True
        except RuntimeError as e:
            print(f"FAILED: {desc} -> {e}")
            pipeline = rs.pipeline()  # reset
            continue

    print("ERROR: No configuration worked!")
    return False


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""<!DOCTYPE html>
<html><head><title>RealSense L515 Test</title>
<style>body{background:#111;color:#fff;font-family:sans-serif;text-align:center;padding:20px}
img{max-width:90vw;border:2px solid #333;border-radius:8px}</style></head>
<body><h2>RealSense L515 - Live Feed</h2>
<img src="/feed"><br><br>
<small>If you see video, the camera works.</small>
</body></html>""")
        elif self.path == "/feed":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            while running:
                try:
                    frames = pipeline.wait_for_frames(timeout_ms=2000)
                    if align:
                        frames = align.process(frames)
                    color = frames.get_color_frame()
                    if not color:
                        continue
                    img = np.asanyarray(color.get_data())
                    # Downscale for browser
                    h, w = img.shape[:2]
                    if w > 960:
                        img = cv2.resize(img, (960, int(h * 960 / w)))
                    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
                except Exception as e:
                    print(f"Frame error: {e}")
                    break

    def log_message(self, format, *args):
        pass  # suppress request logs


if __name__ == "__main__":
    if not start_camera():
        exit(1)
    print(f"\nOpen http://localhost:5555 in your browser")
    print("Press Ctrl+C to stop\n")
    server = HTTPServer(("0.0.0.0", 5555), MJPEGHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        running = False
        pipeline.stop()
        print("\nStopped.")
