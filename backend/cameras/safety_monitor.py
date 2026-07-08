import logging
import threading

logger = logging.getLogger(__name__)

HAS_REALSENSE = False

try:
    import pyrealsense2 as rs
    HAS_REALSENSE = True
except ImportError:
    pass

def _safety_monitor_loop():
    logger.warning("Hardware not available, safety monitor thread exiting.")
    return

def start_safety_monitor():
    if not HAS_REALSENSE:
        logger.warning("pyrealsense2 not available. Skipping safety monitor start.")
        return

    thread = threading.Thread(target=_safety_monitor_loop, daemon=True)
    thread.start()
    logger.info("Safety monitor thread started.")
