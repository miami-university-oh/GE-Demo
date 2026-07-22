import hmac
import threading
import time
import logging
import cv2
import numpy as np
from datetime import datetime
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import Response, StreamingResponse

from backend.config import settings

logger = logging.getLogger(__name__)

camera_router = APIRouter()

HAS_YOLO = False

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    pass

WIDTH = 640
HEIGHT = 480
JPEG_QUALITY = 85

# Docker Desktop on Windows cannot pass USB devices into the container, so the
# camera is captured by publisher/cam01_publisher.py on the host and pushed here
# as JPEG frames over HTTP. The publisher can run on any machine on the network.
INGEST_STALE_SECS = 5.0

# Ingest state (written by the POST handler, read by the processing thread)
latest_ingest_jpeg = None
last_ingest_time = 0.0
ingest_lock = threading.Lock()
new_frame_event = threading.Event()

# Output state (written by the processing thread, read by the MJPEG generators)
latest_raw_frame = None
latest_yolo_frame = None
frame_seq = 0
frame_lock = threading.Lock()

# YOLO config
CONF_THRESH = 0.5
INFER_EVERY = 3
ALERT_ZONE_PX = 160  # scaled down for 640x480

COLOR_PERSON = (94, 197, 34)
COLOR_SAFE = (94, 197, 34)
COLOR_ALERT = (68, 68, 239)
COLOR_ZONE = (21, 204, 250)

KP_NAMES = {
    5: "L_SHOULDER", 6: "R_SHOULDER",
    7: "L_ELBOW",    8: "R_ELBOW",
    9: "L_WRIST",   10: "R_WRIST",
}

SKELETON = [
    (5,6), (5,7), (7,9), (6,8), (8,10), (5,11), (6,12),
    (11,12), (11,13), (12,14), (13,15), (14,16)
]
ALERT_KP_IDS = {7, 8, 9, 10}

def generate_placeholder_frame(message: str):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(message, font, 1, 2)[0]
    text_x = (frame.shape[1] - text_size[0]) // 2
    text_y = (frame.shape[0] + text_size[1]) // 2
    cv2.putText(frame, message, (text_x, text_y), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
    ret, jpeg = cv2.imencode('.jpg', frame)
    return jpeg.tobytes()

def _in_zone(px, py):
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

def _draw_keypoints(img, kps, alert_kps):
    for a, b in SKELETON:
        if a >= len(kps) or b >= len(kps): continue
        ax, ay, ac = kps[a]
        bx, by, bc = kps[b]
        if ac < 0.3 or bc < 0.3: continue
        in_alert = a in alert_kps or b in alert_kps
        cv2.line(img, (ax, ay), (bx, by), COLOR_ALERT if in_alert else COLOR_SAFE, 2, cv2.LINE_AA)
    for idx, (px, py, pc) in enumerate(kps):
        if pc < 0.3: continue
        in_alert = idx in alert_kps
        color = COLOR_ALERT if in_alert else COLOR_SAFE
        cv2.circle(img, (px, py), 4, color, -1, cv2.LINE_AA)
        cv2.circle(img, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)

def _draw_banner(img, num_people, alert_names):
    if alert_names:
        color = COLOR_ALERT
        msg = f"!! ARM IN ROBOT ZONE - {', '.join(alert_names)}"
    elif num_people:
        color = COLOR_SAFE
        msg = f"PERSON DETECTED ({num_people}) - arms tracked"
    else:
        color = (120, 120, 120)
        msg = "NO PERSON IN FRAME"
    cv2.rectangle(img, (0, 0), (WIDTH, 26), (0, 0, 0), -1)
    cv2.putText(img, msg, (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1, cv2.LINE_AA)

def _draw_timestamp(img, extra=""):
    ts = datetime.now().strftime("%H:%M:%S")
    cv2.putText(img, f"CAM-01 {extra} - {ts}", (12, HEIGHT - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 180), 1, cv2.LINE_AA)

def ingest_is_live():
    return last_ingest_time > 0 and (time.time() - last_ingest_time) < INGEST_STALE_SECS

def _decode_latest_ingest():
    with ingest_lock:
        jpeg = latest_ingest_jpeg
    if jpeg is None:
        return None
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    # Publishers may send a different resolution; the overlay math assumes 640x480.
    if img.shape[1] != WIDTH or img.shape[0] != HEIGHT:
        img = cv2.resize(img, (WIDTH, HEIGHT))
    return img

def _publish_frames(buf_raw, buf_yolo):
    global latest_raw_frame, latest_yolo_frame, frame_seq
    with frame_lock:
        latest_raw_frame = buf_raw
        latest_yolo_frame = buf_yolo
        frame_seq += 1

def process_thread():
    model = None
    if HAS_YOLO:
        model = YOLO("yolov8n-pose.pt")
        logger.info("YOLO pose model loaded for cam01")
    else:
        logger.warning("ultralytics not available, cam01 yolo feed will mirror the raw feed")

    frame_count = 0
    last_dets = []

    while True:
        # Wake when the publisher POSTs a frame; the timeout keeps the loop
        # responsive so a stopped publisher does not leave us blocked forever.
        if not new_frame_event.wait(timeout=1.0):
            continue
        new_frame_event.clear()

        try:
            img = _decode_latest_ingest()
            if img is None:
                continue

            raw_img = img.copy()
            _draw_timestamp(raw_img, "RAW")
            _, buf_raw = cv2.imencode(".jpg", raw_img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

            yolo_img = img.copy()
            if HAS_YOLO:
                frame_count += 1
                if frame_count % INFER_EVERY == 0:
                    results = model.predict(img, conf=CONF_THRESH, verbose=False, imgsz=WIDTH)
                    dets = []
                    for r in results:
                        if r.boxes is None: continue
                        for i, box in enumerate(r.boxes):
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            conf = float(box.conf[0])
                            kps, alert_kps, alert_names = [], set(), []
                            if r.keypoints is not None and i < len(r.keypoints.data):
                                kp_data = r.keypoints.data[i].cpu().numpy()
                                for kid, (kx, ky, kc) in enumerate(kp_data):
                                    px, py = int(kx), int(ky)
                                    kps.append((px, py, float(kc)))
                                    if float(kc) > 0.3 and kid in ALERT_KP_IDS and _in_zone(px, py):
                                        alert_kps.add(kid)
                                        alert_names.append(KP_NAMES.get(kid, str(kid)))
                            dets.append({
                                "box": [x1, y1, x2, y2], "conf": conf,
                                "keypoints": kps, "alert_kps": list(alert_kps), "alert_names": alert_names
                            })
                    last_dets = dets

                all_alert_names = []
                for p in last_dets:
                    alert = bool(p["alert_kps"])
                    x1, y1, x2, y2 = p["box"]
                    _draw_person(yolo_img, x1, y1, x2, y2, p["conf"], alert)
                    _draw_keypoints(yolo_img, p["keypoints"], set(p["alert_kps"]))
                    all_alert_names.extend(p["alert_names"])

                _draw_zone(yolo_img)
                _draw_banner(yolo_img, len(last_dets), all_alert_names)
                _draw_timestamp(yolo_img, "YOLO")

                _, buf_yolo = cv2.imencode(".jpg", yolo_img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            else:
                buf_yolo = buf_raw

            _publish_frames(buf_raw.tobytes(), buf_yolo.tobytes())

        except Exception as e:
            logger.error(f"cam01 processing error: {e}")
            time.sleep(0.1)

threading.Thread(target=process_thread, daemon=True).start()

def _mjpeg_part(jpeg_bytes):
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"

def stream_mjpeg(feed_type):
    placeholder = generate_placeholder_frame("WAITING FOR CAM01 PUBLISHER")
    last_seq = -1
    while True:
        if not ingest_is_live():
            yield _mjpeg_part(placeholder)
            last_seq = -1
            time.sleep(1.0)
            continue
        with frame_lock:
            seq = frame_seq
            frame = latest_yolo_frame if feed_type == "yolo" else latest_raw_frame
        # Only forward frames we have not sent yet, at the rate they arrive.
        if frame is None or seq == last_seq:
            time.sleep(0.01)
            continue
        last_seq = seq
        yield _mjpeg_part(frame)

@camera_router.post("/api/cam01/ingest")
async def cam01_ingest(request: Request, x_ingest_token: str = Header(default="")):
    global latest_ingest_jpeg, last_ingest_time
    if not hmac.compare_digest(x_ingest_token, settings.cam01_ingest_token):
        raise HTTPException(status_code=401, detail="invalid ingest token")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty frame")
    with ingest_lock:
        latest_ingest_jpeg = body
        last_ingest_time = time.time()
    new_frame_event.set()
    return Response(status_code=204)

@camera_router.get("/api/cam01/feed")
async def cam01_feed():
    return StreamingResponse(
        stream_mjpeg("raw"),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@camera_router.get("/api/cam01/yolo_feed")
async def cam01_yolo_feed():
    return StreamingResponse(
        stream_mjpeg("yolo"),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
