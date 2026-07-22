"""CAM01 host publisher.

Docker Desktop on Windows cannot pass USB devices into Linux containers, so the
RealSense L515 RGB stream is captured here on the host and pushed to the
dashboard backend as JPEG frames over HTTP. Run this on whichever machine the
camera is plugged into; point CAM01_INGEST_URL at the dashboard server to
stream over the network (e.g. WiFi).

Usage:
    python publisher/cam01_publisher.py
"""

import logging
import os
import time
from pathlib import Path

import cv2
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

INGEST_URL = os.getenv("CAM01_INGEST_URL", "http://localhost:8000").rstrip("/") + "/api/cam01/ingest"
INGEST_TOKEN = os.getenv("CAM01_INGEST_TOKEN", "makino-cam01")
DEVICE_NAME = os.getenv("CAM01_DEVICE_NAME", "RealSense")
DEVICE_INDEX = os.getenv("CAM01_DEVICE_INDEX", "")
WIDTH = int(os.getenv("CAM01_WIDTH", "640"))
HEIGHT = int(os.getenv("CAM01_HEIGHT", "480"))
FPS = int(os.getenv("CAM01_FPS", "30"))
JPEG_QUALITY = int(os.getenv("CAM01_JPEG_QUALITY", "85"))

STATS_EVERY_SECS = 10.0
REOPEN_WAIT_SECS = 3.0
SERVER_RETRY_WAIT_SECS = 1.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cam01_publisher")


def find_device_index() -> int | None:
    if DEVICE_INDEX != "":
        return int(DEVICE_INDEX)
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        logger.warning("pygrabber not available, falling back to device index 0")
        return 0
    devices = FilterGraph().get_input_devices()
    for i, name in enumerate(devices):
        # The L515 exposes both an RGB and a Depth UVC device; we want RGB.
        if DEVICE_NAME.lower() in name.lower() and "depth" not in name.lower():
            logger.info(f"Found camera [{i}] {name}")
            return i
    logger.error(f"No camera matching '{DEVICE_NAME}' found. Devices: {devices}")
    return None


def open_camera() -> cv2.VideoCapture | None:
    index = find_device_index()
    if index is None:
        return None
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    if not cap.isOpened():
        cap.release()
        logger.error(f"Failed to open camera index {index}")
        return None
    return cap


def encode_jpeg(frame) -> bytes | None:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return buf.tobytes() if ok else None


def post_frame(session: requests.Session, jpeg: bytes) -> bool:
    resp = session.post(
        INGEST_URL,
        data=jpeg,
        headers={"X-Ingest-Token": INGEST_TOKEN, "Content-Type": "image/jpeg"},
        timeout=2,
    )
    if resp.status_code == 401:
        raise SystemExit("Ingest token rejected by server. Check CAM01_INGEST_TOKEN in .env.")
    return resp.status_code < 400


def publish_loop(cap: cv2.VideoCapture, session: requests.Session):
    sent = 0
    server_ok = True
    stats_start = time.time()
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            logger.warning("Camera read failed, reopening camera")
            return
        jpeg = encode_jpeg(frame)
        if jpeg is None:
            continue
        try:
            post_frame(session, jpeg)
            if not server_ok:
                logger.info("Server reachable again, streaming resumed")
                server_ok = True
            sent += 1
        except requests.RequestException:
            if server_ok:
                logger.warning(f"Cannot reach {INGEST_URL}, retrying quietly...")
                server_ok = False
            # Do not hammer a server that is down or still starting up.
            time.sleep(SERVER_RETRY_WAIT_SECS)
        if time.time() - stats_start >= STATS_EVERY_SECS:
            fps = sent / (time.time() - stats_start)
            logger.info(f"Publishing at {fps:.1f} fps to {INGEST_URL}")
            sent = 0
            stats_start = time.time()


def main():
    logger.info(f"CAM01 publisher starting, target: {INGEST_URL}")
    session = requests.Session()
    while True:
        cap = open_camera()
        if cap is None:
            logger.error(f"No camera. Retrying in {REOPEN_WAIT_SECS}s (is it plugged in? is another app using it?)")
            time.sleep(REOPEN_WAIT_SECS)
            continue
        logger.info(f"Camera open at {WIDTH}x{HEIGHT}, publishing...")
        try:
            publish_loop(cap, session)
        finally:
            cap.release()
        time.sleep(REOPEN_WAIT_SECS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("CAM01 publisher stopped")
