import threading
import time
import logging
import cv2
import numpy as np
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

camera_router = APIRouter()

HAS_REALSENSE = False
HAS_YOLO = False

try:
    import pyrealsense2 as rs
    HAS_REALSENSE = True
except ImportError:
    pass

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    pass

WIDTH = 640
HEIGHT = 480
FPS = 30
JPEG_QUALITY = 85

# State
latest_raw_frame = None
latest_yolo_frame = None
frame_lock = threading.Lock()
running = False

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

def generate_frames_fallback(message: str):
    jpeg_bytes = generate_placeholder_frame(message)
    while True:
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")
        time.sleep(1)

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

def capture_thread():
    global latest_raw_frame, latest_yolo_frame, running
    
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.bgr8, FPS)
    
    try:
        pipeline.start(config)
        logger.info(f"RealSense pipeline started: {WIDTH}x{HEIGHT} @ {FPS} FPS")
    except Exception as e:
        logger.error(f"Failed to start RealSense: {e}")
        running = False
        return
        
    model = None
    if HAS_YOLO:
        model = YOLO("yolov8n-pose.pt")
        
    frame_count = 0
    last_dets = []
    
    while running:
        try:
            frames = pipeline.wait_for_frames(timeout_ms=5000)
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue
                
            img = np.asanyarray(color_frame.get_data())
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
                
            with frame_lock:
                latest_raw_frame = buf_raw.tobytes()
                latest_yolo_frame = buf_yolo.tobytes()
                
        except Exception as e:
            logger.error(f"Capture error: {e}")
            time.sleep(0.1)
            
    pipeline.stop()

if HAS_REALSENSE:
    running = True
    threading.Thread(target=capture_thread, daemon=True).start()

def stream_mjpeg(feed_type):
    if not HAS_REALSENSE:
        yield from generate_frames_fallback(f"{feed_type.upper()} STREAM (SIMULATED)")
        return
        
    while True:
        with frame_lock:
            frame = latest_yolo_frame if feed_type == "yolo" else latest_raw_frame
        if frame is None:
            if not running:
                yield from generate_frames_fallback(f"{feed_type.upper()} STREAM (FAILED)")
                return
            time.sleep(0.1)
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

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
