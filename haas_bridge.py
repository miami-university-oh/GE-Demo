#!/usr/bin/env python3
"""
haas_bridge.py — HAAS TL-1 Direct WebSocket Bridge
=====================================================
Single-script replacement for the collector + server two-step pipeline.

Old architecture:
  HAAS:5051 → [collector] → haas_data_shared.json → [server reads @ 2 Hz] → ws://:8000/ws

New architecture:
  HAAS:5051 → [haas_bridge] → ws://:8766  (data in memory, no file I/O)

All tier collection intervals are preserved:
  Tier 1  — 1 s   : spindle RPM/load, position, overrides, program, active tool
  Tier 2  — 10 s  : mode, cycle timers, tool wear / life, operator coords
  Tier 3  — 30 s  : machine info, all 12 tool offsets + geometry
  Tier 4  — 120 s : full alarm sweep (Q500 + MTConnect /current)

WebSocket protocol (JSON):
  Server → client:
    {"type": "tier1"|"tier2"|"tier3"|"tier4", "data": {...}}
    {"type": "full_state", "data": {...}}          ← on initial connect
    {"type": "connection", "connected": true|false}

  Client → server (control commands):
    {"cmd": "cycle_start"}
    {"cmd": "feed_hold"}
    {"cmd": "reset"}
    {"cmd": "coolant_flood_on"|"coolant_mist_on"|"coolant_off"}
    {"cmd": "spindle_override", "percent": 80}
    {"cmd": "feed_override",    "percent": 100}
    {"cmd": "rapid_override",   "percent": 50}
    {"cmd": "macro_write",      "variable": 500, "value": 1.5}

  Server replies to commands with:
    {"type": "cmd_result", "data": {"success": bool, "command": "...", ...}}

Requirements:
    pip install websockets

Optionally place haas_alarm_db.py in the same directory for full alarm lookup.
If not present, a minimal fallback is used automatically.

Usage:
    python haas_bridge.py
"""

import asyncio
import csv
import json
import logging
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ── Dependency check ──────────────────────────────────────────────────────────

try:
    import websockets
except ImportError:
    raise SystemExit(
        "\n[ERROR] 'websockets' library not found.\n"
        "Install it with:  pip install websockets\n"
    )

# ── Optional alarm database ───────────────────────────────────────────────────

try:
    from haas_alarm_db import get_alarm_info, parse_alarm_text
    _ALARM_DB_AVAILABLE = True
except ImportError:
    _ALARM_DB_AVAILABLE = False

    def get_alarm_info(code: int) -> Dict[str, Any]:
        """Minimal fallback when haas_alarm_db.py is not present."""
        severity = "critical" if 100 <= code < 200 or 700 <= code < 800 else "warning"
        return {
            "code": code,
            "title": f"ALARM {code}",
            "severity": severity,
            "category": "System",
            "machine": "both",
            "causes": [f"Alarm {code} — refer to HAAS service manual"],
            "checks": ["Check HAAS control screen for details"],
            "recovery": ["Press RESET", "Power cycle if RESET doesn't clear"],
        }

    def parse_alarm_text(text: str) -> List[Dict[str, Any]]:
        """Minimal fallback alarm text parser."""
        if not text or text.strip() == "":
            return []
        upper = text.strip().upper()
        if upper in ("ALARM ON", "ALARM"):
            return [{
                "code": 0, "title": "ALARM ACTIVE (code unknown)",
                "severity": "warning", "category": "System", "machine": "both",
                "causes": ["Alarm active — check HAAS screen for specific code"],
                "checks": ["View alarm screen on HAAS control"],
                "recovery": ["Press RESET on the HAAS control"],
            }]
        nums = re.findall(r'\b(\d{3,4})\b', upper)
        results = [get_alarm_info(int(n)) for n in nums if 100 <= int(n) <= 9999]
        if not results and "ALARM" in upper:
            return [{
                "code": 0, "title": text.strip(),
                "severity": "warning", "category": "System", "machine": "both",
                "causes": [text.strip()], "checks": [], "recovery": ["Press RESET"],
            }]
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

HAAS_IP           = "192.168.1.50"
HAAS_PORT         = 5051
MTCONNECT_PORT    = 8082          # Used for alarm detail in Tier 4

WS_HOST           = "0.0.0.0"    # Bind all interfaces → reach at 192.168.1.16:8765
WS_PORT           = 8765

# Tier collection intervals (seconds)
T1_INTERVAL       = 1.0           # Spindle, position, overrides
T2_INTERVAL       = 10.0          # Mode, timers, tool wear
T3_INTERVAL       = 30.0          # Static machine info, all tool geometry
T4_INTERVAL       = 120.0         # Diagnostics + full alarm sweep

RECONNECT_DELAY   = 5.0           # Seconds before retry after connection loss

# Set to None to disable CSV logging, or a Path to enable
CSV_LOG_DIR: Optional[Path] = Path("./cnc_logs")

MAX_ALARM_HISTORY = 100

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("haas_bridge")


# ═══════════════════════════════════════════════════════════════════════════════
# MACHINE STATE  (replaces haas_data_shared.json)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MachineState:
    """
    In-memory store for all machine data.
    Replaces the JSON file middleman — data lives here and is pushed
    directly over WebSocket whenever a tier updates.
    """
    tier1: Dict[str, Any]             = field(default_factory=dict)
    tier2: Dict[str, Any]             = field(default_factory=dict)
    tier3: Dict[str, Any]             = field(default_factory=dict)
    tier4: Dict[str, Any]             = field(default_factory=dict)
    active_alarms: List[Dict]         = field(default_factory=list)
    alarm_history: List[Dict]         = field(default_factory=list)
    connected: bool                   = False
    last_update: str                  = ""

    def snapshot(self) -> Dict[str, Any]:
        """Full snapshot for new WebSocket clients on connect."""
        return {
            "tier1":         self.tier1,
            "tier2":         self.tier2,
            "tier3":         self.tier3,
            "tier4":         self.tier4,
            "active_alarms": self.active_alarms,
            "alarm_history": self.alarm_history[:50],
            "connected":     self.connected,
            "timestamp":     self.last_update,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HAAS BRIDGE
# ═══════════════════════════════════════════════════════════════════════════════

class HaasBridge:
    """
    Async bridge between HAAS TL-1 Q-command TCP socket and WebSocket clients.

    Single asyncio event loop runs:
      • collection_loop() — polls HAAS on tier schedules, updates self.state
      • WebSocket server   — broadcasts state updates, handles control commands
    """

    def __init__(self):
        self.state = MachineState()

        # Async TCP connection to HAAS
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._socket_lock = asyncio.Lock()   # Serialize all HAAS socket access

        # WebSocket clients
        self._clients: Set[Any] = set()
        self._clients_lock = asyncio.Lock()

        # Alarm state
        self._alarm_history: deque = deque(maxlen=MAX_ALARM_HISTORY)
        self._current_alarms: List[Dict[str, Any]] = []
        self._last_alarm_codes: set = set()

        # CSV log directory
        if CSV_LOG_DIR:
            CSV_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    # TCP CONNECTION
    # ─────────────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Open async TCP connection to HAAS and prime the socket.

        The HAAS sends a '>' prompt on connect; the first command often gets
        a delayed or empty response. We drain the prompt and send two throwaway
        Q100 queries to stabilise the pipeline before real queries begin.
        """
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(HAAS_IP, HAAS_PORT),
                timeout=5.0,
            )
            log.info("Connected to HAAS TL-1 at %s:%d", HAAS_IP, HAAS_PORT)
            self.state.connected = True

            # Drain initial prompt bytes
            await asyncio.sleep(0.3)
            await self._drain_socket()

            # Two throwaway primes to absorb first-command delay
            await self._prime_command("?Q100")
            await self._prime_command("?Q100")
            log.info("Socket primed — ready for queries")
            return True

        except asyncio.TimeoutError:
            log.error("Connection to %s:%d timed out", HAAS_IP, HAAS_PORT)
        except OSError as e:
            log.error("Connection failed: %s", e)

        self.state.connected = False
        return False

    async def disconnect(self):
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._reader = None
            self._writer = None
        self.state.connected = False
        log.info("Disconnected from HAAS")

    async def _drain_socket(self):
        """Read and discard any pending bytes on the socket."""
        if not self._reader:
            return
        try:
            await asyncio.wait_for(self._reader.read(4096), timeout=0.3)
        except (asyncio.TimeoutError, Exception):
            pass

    async def _prime_command(self, command: str):
        """Send a throwaway command and discard the response."""
        if not self._writer:
            return
        try:
            self._writer.write((command.strip() + "\r\n").encode("ascii", errors="ignore"))
            await self._writer.drain()
            await asyncio.sleep(0.5)
            try:
                data = await asyncio.wait_for(self._reader.read(4096), timeout=1.0)
                clean = data.decode("utf-8", errors="ignore").replace(">", "").strip()
                if clean:
                    log.debug("Prime response: %s", clean[:60])
            except asyncio.TimeoutError:
                pass
        except Exception as e:
            log.debug("Prime error (ignorable): %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Q-COMMAND PROTOCOL
    # ─────────────────────────────────────────────────────────────────────────

    async def send_command(self, command: str, read_timeout: float = 0.8) -> str:
        """
        Send one Q-command to HAAS and return the parsed response line.

        Steps (mirrors the original synchronous logic, now async):
          1. Drain stale bytes from previous responses
          2. Send the command
          3. Brief processing delay (HAAS needs ~150 ms to prepare response)
          4. Read until we see a complete data line (contains a comma)
          5. Return the first non-prompt, non-empty line
        """
        if not self._reader or not self._writer:
            return ""

        async with self._socket_lock:
            # 1. Drain stale bytes
            try:
                await asyncio.wait_for(self._reader.read(4096), timeout=0.05)
            except (asyncio.TimeoutError, Exception):
                pass

            # 2. Send command
            try:
                self._writer.write((command.strip() + "\r\n").encode("ascii", errors="ignore"))
                await self._writer.drain()
            except Exception:
                return ""

            # 3. Processing delay
            await asyncio.sleep(0.15)

            # 4. Read response
            data = b""
            loop = asyncio.get_event_loop()
            deadline = loop.time() + read_timeout

            while loop.time() < deadline:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    chunk = await asyncio.wait_for(
                        self._reader.read(4096),
                        timeout=min(0.15, remaining),
                    )
                    if chunk:
                        data += chunk
                        text = data.decode("utf-8", errors="ignore")
                        # Return first line that contains a comma (HAAS response data)
                        for line in text.splitlines():
                            clean = line.strip().lstrip(">").strip()
                            if "," in clean:
                                return clean
                        if b"\n" in data:
                            break
                except (asyncio.TimeoutError, Exception):
                    break

            # 5. Best-effort parse from whatever we received
            text = data.decode("utf-8", errors="ignore").strip()
            for line in text.splitlines():
                line = line.strip().lstrip(">").strip()
                if line and line != ">":
                    return line
            return ""

    # ─────────────────────────────────────────────────────────────────────────
    # PARSERS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_var(self, var_num: int) -> Optional[float]:
        """
        Q600 macro variable query.
        Handles both 2-field "MACRO, value" and 3-field "MACRO, var, value" responses.
        """
        resp = await self.send_command(f"?Q600 {var_num}")
        if not resp:
            return None
        parts = [p.strip() for p in resp.split(",") if p.strip()]
        if not parts or parts[0].upper() != "MACRO":
            return None
        try:
            return float(parts[2] if len(parts) >= 3 else parts[1])
        except (ValueError, IndexError):
            return None

    def _parse_q500(self, resp: str) -> Dict[str, Any]:
        """
        Parse Q500 response: "PROGRAM, O00002, ALARM ON, PARTS, 143"
        Returns dict with program_name, execution_status, current_alarm_codes, parts_count_total.
        """
        result: Dict[str, Any] = {}
        if not resp:
            return result
        parts = [p.strip() for p in resp.split(",")]
        if len(parts) >= 2:
            result["program_name"] = parts[1]
        if len(parts) >= 3:
            result["execution_status"] = parts[2]
        if len(parts) >= 5:
            try:
                result["parts_count_total"] = int(float(parts[4]))
            except Exception:
                result["parts_count_total"] = 0
        status = result.get("execution_status", "")
        result["current_alarm_codes"] = status if "ALARM" in status.upper() else ""
        return result

    def _parse_simple(self, resp: str) -> str:
        """"LABEL, value" → "value" """
        if not resp:
            return ""
        parts = resp.split(",")
        return parts[1].strip() if len(parts) >= 2 else resp.strip()

    def _parse_int(self, resp: str) -> int:
        try:
            return int(float(self._parse_simple(resp)))
        except Exception:
            return 0

    # ─────────────────────────────────────────────────────────────────────────
    # TIER COLLECTION
    # ─────────────────────────────────────────────────────────────────────────

    async def collect_tier1(self) -> Dict[str, Any]:
        """
        Tier 1 — 1 s interval
        Confirmed working variables on the TL-1:
          3027  = spindle speed RPM
          1098  = spindle load %
          62540 = spindle override %       (changes with knob)
          62590 = feed override %          (changes with knob)
          5041  = X work coordinate
          5042  = Z work coordinate
          1064  = X axis load %
          1066  = Z axis load %
          3026  = current tool number
          2001+ = X geometry offsets (tool 1-12)
          2101+ = Z geometry offsets (tool 1-12)
        """
        data: Dict[str, Any] = {}

        # Program + status + parts count
        q500_raw = await self.send_command("?Q500")
        q500 = self._parse_q500(q500_raw)
        data["program_name"]        = q500.get("program_name", "")
        data["execution_status"]    = q500.get("execution_status", "")
        data["current_alarm_codes"] = q500.get("current_alarm_codes", "")
        data["parts_count_total"]   = q500.get("parts_count_total", 0)

        # Spindle
        data["spindle_speed_rpm"]        = await self.get_var(3027)
        data["spindle_load_percent"]     = await self.get_var(1098)
        data["spindle_override_percent"] = await self.get_var(62540)

        # Feed
        data["feed_override_percent"]    = await self.get_var(62590)

        # Work coordinates
        data["x_work_coord"]             = await self.get_var(5041)
        data["z_work_coord"]             = await self.get_var(5042)

        # Axis loads
        data["x_axis_load_percent"]      = await self.get_var(1064)
        data["z_axis_load_percent"]      = await self.get_var(1066)

        # Active tool + geometry offsets
        data["current_tool_number"]      = await self.get_var(3026)
        tool = int(data["current_tool_number"] or 1)
        data["active_tool_x_geometry"]   = await self.get_var(2001 + (tool - 1))
        data["active_tool_z_geometry"]   = await self.get_var(2101 + (tool - 1))

        return data

    async def collect_tier2(self) -> Dict[str, Any]:
        """
        Tier 2 — 10 s interval
        Mode, cycle timers, tool wear, operator coords, control mode flags.
        """
        data: Dict[str, Any] = {}

        # Machine mode (MEM / MDI / JOG, etc.)
        q104 = await self.send_command("?Q104")
        data["machine_mode"] = self._parse_simple(q104)

        # Timers
        data["present_part_time_seconds"]  = await self.get_var(3023)
        data["total_feed_time_seconds"]    = await self.get_var(3021)
        data["total_spindle_time_seconds"] = await self.get_var(3022)

        # Active tool wear + life
        tool = int(await self.get_var(3026) or 1)
        data["active_tool_x_wear"]         = await self.get_var(2201 + (tool - 1))
        data["active_tool_life_remaining"] = await self.get_var(5701 + (tool - 1))

        # Operator coordinates (negative of work coords on TL-1)
        data["x_operator_coord"]           = await self.get_var(5081)
        data["z_operator_coord"]           = await self.get_var(5082)

        # Control mode flags
        data["single_block_mode"]          = await self.get_var(3030)
        data["block_delete_mode"]          = await self.get_var(3032)
        data["optional_stop_mode"]         = await self.get_var(3033)
        data["rapid_override_percent"]     = await self.get_var(62591)

        return data

    async def collect_tier3(self) -> Dict[str, Any]:
        """
        Tier 3 — 30 s interval
        Static machine identity, power/motion timers, all 12 tool offsets.
        """
        data: Dict[str, Any] = {}

        # Machine identity
        q100 = await self.send_command("?Q100")
        data["serial_number"]        = self._parse_simple(q100)
        q102 = await self.send_command("?Q102")
        data["model_name"]           = self._parse_simple(q102)

        # Cumulative timers
        q300 = await self.send_command("?Q300")
        data["power_on_time"]        = self._parse_simple(q300)
        q301 = await self.send_command("?Q301")
        data["motion_time"]          = self._parse_simple(q301)

        # Counters
        q200 = await self.send_command("?Q200")
        data["total_tool_changes"]   = self._parse_int(q200)
        q402 = await self.send_command("?Q402")
        data["m30_counter_1"]        = self._parse_int(q402)
        q403 = await self.send_command("?Q403")
        data["m30_counter_2"]        = self._parse_int(q403)

        # Cycle times
        data["last_part_time_seconds"] = await self.get_var(3024)

        # Surface speed + chip load (only valid when cutting)
        data["surface_speed_fpm"]    = await self.get_var(62530)
        data["chip_load_ipt"]        = await self.get_var(62531)

        # All 12 tool offsets (skip active tool — already in Tier 1)
        active_tool = int(await self.get_var(3026) or 1)
        for n in range(1, 13):
            if n == active_tool:
                continue
            p = f"tool_{n}"
            data[f"{p}_x_geometry"]     = await self.get_var(2001 + n - 1)
            data[f"{p}_z_geometry"]     = await self.get_var(2101 + n - 1)
            data[f"{p}_x_wear"]         = await self.get_var(2201 + n - 1)
            data[f"{p}_life_remaining"] = await self.get_var(5701 + n - 1)

        return data

    async def collect_tier4(self) -> Dict[str, Any]:
        """
        Tier 4 — 120 s interval
        Full alarm sweep: Q500 text + MTConnect /current XML.
        MTConnect HTTP fetch runs in a thread (blocking I/O, off the event loop).
        """
        data: Dict[str, Any] = {}

        # Alarm status from Q500
        q500_raw = await self.send_command("?Q500")
        q500 = self._parse_q500(q500_raw)
        alarm_text = q500.get("current_alarm_codes", "")
        data["alarm_status"] = alarm_text

        # MTConnect for detailed alarm info (blocking HTTP → thread pool)
        mtc_alarms = await asyncio.get_event_loop().run_in_executor(
            None, self._fetch_mtconnect_alarms
        )

        # Merge + update alarm state
        self._update_alarm_state(alarm_text, mtc_alarms)
        data["active_alarms"] = self._current_alarms
        data["alarm_count"]   = len(self._current_alarms)

        # Power-on time refresh
        q300 = await self.send_command("?Q300")
        data["power_on_time"] = self._parse_simple(q300)

        return data

    # ─────────────────────────────────────────────────────────────────────────
    # ALARM MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_mtconnect_alarms(self) -> List[Dict[str, Any]]:
        """
        Blocking MTConnect HTTP fetch — call via run_in_executor only.
        Returns list of parsed alarm dicts, or [] if MTConnect is unavailable.
        """
        try:
            url = f"http://{HAAS_IP}:{MTCONNECT_PORT}/current"
            req = urllib.request.Request(url, headers={"Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=3) as r:
                xml_data = r.read().decode("utf-8", errors="ignore")
            return self._parse_mtconnect_xml(xml_data)
        except urllib.error.URLError:
            # MTConnect not available — normal fallback to Q500
            return []
        except Exception as e:
            log.debug("MTConnect fetch error: %s", e)
            return []

    def _parse_mtconnect_xml(self, xml_data: str) -> List[Dict[str, Any]]:
        alarms: List[Dict[str, Any]] = []
        try:
            # Strip namespace declarations for simpler parsing
            xml_clean = re.sub(r'\sxmlns[^"]*"[^"]*"', "", xml_data)
            root = ET.fromstring(xml_clean)
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag in ("Fault", "Warning", "Alarm"):
                    info = self._extract_mtconnect_alarm(elem, tag)
                    if info:
                        alarms.append(info)
        except ET.ParseError as e:
            log.debug("MTConnect XML parse error: %s", e)
        return alarms

    def _extract_mtconnect_alarm(self, elem: Any, tag_type: str) -> Optional[Dict[str, Any]]:
        text        = (elem.text or "").strip()
        native_code = elem.get("nativeCode", "")

        # Extract numeric alarm code
        alarm_code = 0
        if native_code:
            try:
                alarm_code = int(native_code)
            except ValueError:
                nums = re.findall(r"\d+", native_code)
                if nums:
                    alarm_code = int(nums[0])
        if alarm_code == 0 and text:
            nums = re.findall(r"\b(\d{3,4})\b", text)
            if nums:
                alarm_code = int(nums[0])

        db = get_alarm_info(alarm_code) if alarm_code > 0 else {
            "code": 0, "title": text or "Unknown Alarm",
            "severity": "warning" if tag_type == "Warning" else "critical",
            "category": "System", "machine": "both",
            "causes": [text or "Unknown"], "checks": [], "recovery": ["Press RESET"],
        }
        return {
            **db,
            "text": text,
            "native_code": native_code,
            "source": "mtconnect",
            "timestamp": datetime.now().isoformat(),
        }

    def _update_alarm_state(
        self,
        q500_text: str,
        mtc_alarms: List[Dict[str, Any]],
    ):
        """
        Merge Q500 and MTConnect alarm sources, track history of
        appeared / cleared alarms, and update self.state.
        """
        new_alarms: List[Dict[str, Any]] = []
        new_codes: set = set()

        # MTConnect is preferred (has specific alarm codes)
        if mtc_alarms:
            for a in mtc_alarms:
                new_codes.add(a.get("code", 0))
                new_alarms.append(a)
        elif q500_text:
            # Fall back to Q500 text parsing
            for a in parse_alarm_text(q500_text):
                code = a.get("code", 0)
                if code not in new_codes:
                    new_codes.add(code)
                    a.update({
                        "source": "q500",
                        "timestamp": datetime.now().isoformat(),
                        "text": q500_text,
                    })
                    new_alarms.append(a)

        now = datetime.now().isoformat()
        appeared = new_codes - self._last_alarm_codes
        cleared  = self._last_alarm_codes - new_codes

        # Log newly appeared alarms
        for a in new_alarms:
            if a.get("code", 0) in appeared or not self._last_alarm_codes:
                self._alarm_history.appendleft({**a, "event": "triggered", "event_time": now})

        # Log cleared alarms
        for code in cleared:
            if code > 0:
                info = get_alarm_info(code)
                self._alarm_history.appendleft({
                    "code": code,
                    "title": info.get("title", f"ALARM {code}"),
                    "severity": info.get("severity", "warning"),
                    "category": info.get("category", "System"),
                    "event": "cleared",
                    "event_time": now,
                    "source": "state_change",
                })

        self._last_alarm_codes = new_codes
        self._current_alarms   = new_alarms
        self.state.active_alarms = new_alarms
        self.state.alarm_history = list(self._alarm_history)

    # ─────────────────────────────────────────────────────────────────────────
    # CONTROL COMMANDS  (bidirectional: WebSocket client → HAAS)
    # ─────────────────────────────────────────────────────────────────────────

    async def _raw_cmd(self, haas_cmd: str) -> Dict[str, Any]:
        """Send a raw MDC E-code or Q600 SET command and return result dict."""
        start = time.monotonic()
        resp  = await self.send_command(haas_cmd, read_timeout=2.0)
        ms    = int((time.monotonic() - start) * 1000)
        ok    = bool(resp)
        log.info("[CMD] %s → %s (%d ms)", haas_cmd, "OK" if ok else "NO RESPONSE", ms)
        return {
            "success":   ok,
            "command":   haas_cmd,
            "response":  resp,
            "elapsed_ms": ms,
            "timestamp": datetime.now().isoformat(),
        }

    async def handle_client_command(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch a JSON control command from a WebSocket client.

        HAAS MDC protocol:
          E0 = Feed Hold   (same as pressing FEED HOLD button)
          E1 = Cycle Start (same as pressing CYCLE START button)
          E2 = Reset       (same as pressing RESET button)
          E6 = Coolant Flood ON
          E7 = Coolant OFF
          E13 = Coolant Mist ON
          Q600 SET {var} {val} = Write macro variable
        """
        cmd = msg.get("cmd", "")

        if cmd == "cycle_start":
            return await self._raw_cmd("E1")

        elif cmd == "feed_hold":
            return await self._raw_cmd("E0")

        elif cmd == "reset":
            return await self._raw_cmd("E2")

        elif cmd == "coolant_flood_on":
            return await self._raw_cmd("E6")

        elif cmd == "coolant_mist_on":
            return await self._raw_cmd("E13")

        elif cmd == "coolant_off":
            return await self._raw_cmd("E7")

        elif cmd == "spindle_override":
            pct = max(0, min(200, int(msg.get("percent", 100))))
            return await self._raw_cmd(f"Q600 SET 62540 {pct}")

        elif cmd == "feed_override":
            pct = max(0, min(200, int(msg.get("percent", 100))))
            return await self._raw_cmd(f"Q600 SET 62590 {pct}")

        elif cmd == "rapid_override":
            pct = max(5, min(100, int(msg.get("percent", 100))))
            return await self._raw_cmd(f"Q600 SET 62591 {pct}")

        elif cmd == "macro_write":
            var = int(msg.get("variable", 0))
            val = float(msg.get("value", 0))
            # Block read-only / protected HAAS variable ranges
            for lo, hi in [(1, 99), (3000, 3099), (5000, 5099)]:
                if lo <= var <= hi:
                    return {
                        "success": False,
                        "command": cmd,
                        "error": f"Variable #{var} is read-only/protected (range {lo}–{hi})",
                        "timestamp": datetime.now().isoformat(),
                    }
            return await self._raw_cmd(f"Q600 SET {var} {val}")

        else:
            return {
                "success": False,
                "command": cmd,
                "error": f"Unknown command: '{cmd}'",
                "timestamp": datetime.now().isoformat(),
            }

    # ─────────────────────────────────────────────────────────────────────────
    # CSV LOGGING  (optional)
    # ─────────────────────────────────────────────────────────────────────────

    def _save_csv(self, tier: int, data: Dict[str, Any]):
        if not CSV_LOG_DIR or not data:
            return
        # Only log scalar values to CSV
        csv_data = {
            k: v for k, v in data.items()
            if isinstance(v, (str, int, float, bool)) or v is None
        }
        date_str = datetime.now().strftime("%Y%m%d")
        path = CSV_LOG_DIR / f"haas_tier{tier}_{date_str}.csv"
        row  = {"timestamp": datetime.now().isoformat(), **csv_data}
        fieldnames = ["timestamp"] + sorted(csv_data)
        try:
            file_exists = path.exists()
            with open(path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    w.writeheader()
                w.writerow(row)
        except Exception as e:
            log.warning("CSV write error (tier %d): %s", tier, e)

    # ─────────────────────────────────────────────────────────────────────────
    # WEBSOCKET
    # ─────────────────────────────────────────────────────────────────────────

    async def _broadcast(self, msg: Dict[str, Any]):
        """Push a JSON message to all connected WebSocket clients."""
        if not self._clients:
            return
        payload = json.dumps(msg, default=str)
        async with self._clients_lock:
            dead: Set[Any] = set()
            for ws in self._clients:
                try:
                    await ws.send(payload)
                except Exception:
                    dead.add(ws)
            self._clients -= dead

    async def ws_handler(self, websocket: Any, path: str = "/"):
        """
        Per-client WebSocket handler.
        Immediately sends the full machine state snapshot on connect,
        then listens for inbound control commands.
        """
        async with self._clients_lock:
            self._clients.add(websocket)
        log.info("WS client connected  (total: %d)", len(self._clients))

        # Send current state immediately so the dashboard doesn't wait
        try:
            await websocket.send(json.dumps({
                "type": "full_state",
                "data": self.state.snapshot(),
            }, default=str))
        except Exception:
            pass

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    result = await self.handle_client_command(msg)
                    await websocket.send(json.dumps(
                        {"type": "cmd_result", "data": result}, default=str
                    ))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps(
                        {"type": "error", "message": "Invalid JSON from client"}
                    ))
                except Exception as e:
                    await websocket.send(json.dumps(
                        {"type": "error", "message": str(e)}
                    ))
        except Exception:
            pass  # Client disconnected
        finally:
            async with self._clients_lock:
                self._clients.discard(websocket)
            log.info("WS client disconnected (total: %d)", len(self._clients))

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN COLLECTION LOOP
    # ─────────────────────────────────────────────────────────────────────────

    async def collection_loop(self):
        """
        Core loop: connect to HAAS, run tier tasks on schedule,
        broadcast results, reconnect automatically on connection loss.

        The loop ticks at 50 Hz (0.02 s sleep) so tier intervals are
        respected to within one tick.
        """
        last_t1 = last_t2 = last_t3 = last_t4 = 0.0

        while True:
            # ── Ensure connection ────────────────────────────────────────────
            if not self.state.connected:
                log.info("Attempting HAAS connection...")
                ok = await self.connect()
                if not ok:
                    log.warning(
                        "HAAS unreachable — retrying in %.0f s", RECONNECT_DELAY
                    )
                    await self._broadcast({"type": "connection", "connected": False})
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue
                await self._broadcast({"type": "connection", "connected": True})

            # ── Tier dispatch ────────────────────────────────────────────────
            try:
                now = time.monotonic()

                if now - last_t1 >= T1_INTERVAL:
                    t1 = await self.collect_tier1()
                    self.state.tier1       = t1
                    self.state.last_update = datetime.now().isoformat()
                    last_t1 = now
                    await self._broadcast({"type": "tier1", "data": t1})
                    self._save_csv(1, t1)

                if now - last_t2 >= T2_INTERVAL:
                    t2 = await self.collect_tier2()
                    self.state.tier2 = t2
                    last_t2 = now
                    await self._broadcast({"type": "tier2", "data": t2})
                    self._save_csv(2, t2)

                if now - last_t3 >= T3_INTERVAL:
                    t3 = await self.collect_tier3()
                    self.state.tier3 = t3
                    last_t3 = now
                    await self._broadcast({"type": "tier3", "data": t3})
                    self._save_csv(3, t3)

                if now - last_t4 >= T4_INTERVAL:
                    t4 = await self.collect_tier4()
                    self.state.tier4 = t4
                    last_t4 = now
                    await self._broadcast({"type": "tier4", "data": t4})
                    self._save_csv(4, t4)

                await asyncio.sleep(0.02)   # 50 Hz tick

            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                log.warning("HAAS connection lost: %s — reconnecting...", e)
                await self.disconnect()
                await asyncio.sleep(RECONNECT_DELAY)

            except Exception as e:
                log.exception("Unexpected collection error: %s", e)
                await asyncio.sleep(1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────────

    async def run(self):
        """Start the WebSocket server and collection loop concurrently."""
        self._print_banner()

        ws_server = await websockets.serve(self.ws_handler, WS_HOST, WS_PORT)
        log.info("WebSocket server listening on ws://%s:%d", WS_HOST, WS_PORT)

        try:
            await self.collection_loop()
        finally:
            ws_server.close()
            await ws_server.wait_closed()
            await self.disconnect()

    @staticmethod
    def _print_banner():
        lines = [
            "=" * 58,
            "  HAAS TL-1 Direct WebSocket Bridge",
            "  (No intermediate JSON file — direct HAAS → WS)",
            "=" * 58,
            f"  HAAS machine:   {HAAS_IP}:{HAAS_PORT} (Q-commands + MDC)",
            f"  MTConnect:      {HAAS_IP}:{MTCONNECT_PORT} /current (alarm detail)",
            f"  WebSocket:      ws://0.0.0.0:{WS_PORT}  (dashboard: ws://192.168.1.16:{WS_PORT})",
            f"  CSV logging:    {str(CSV_LOG_DIR) if CSV_LOG_DIR else 'disabled'}",
            f"  Alarm database: {'haas_alarm_db.py' if _ALARM_DB_AVAILABLE else 'built-in fallback'}",
            "=" * 58,
            "",
            "  Tier intervals:",
            f"    Tier 1  {T1_INTERVAL:>5.0f} s  — spindle, position, overrides",
            f"    Tier 2  {T2_INTERVAL:>5.0f} s  — mode, timers, tool wear",
            f"    Tier 3  {T3_INTERVAL:>5.0f} s  — machine info, all tool geometry",
            f"    Tier 4  {T4_INTERVAL:>5.0f} s  — alarms (Q500 + MTConnect)",
            "",
            "  WebSocket message types (server → client):",
            '    {"type": "full_state", "data": {...}}   ← on connect',
            '    {"type": "tier1"|"tier2"|..., "data": {...}}',
            '    {"type": "connection", "connected": bool}',
            "",
            "  Control commands (client → server):",
            '    {"cmd": "cycle_start"}',
            '    {"cmd": "feed_hold"}',
            '    {"cmd": "reset"}',
            '    {"cmd": "coolant_flood_on"|"coolant_mist_on"|"coolant_off"}',
            '    {"cmd": "spindle_override", "percent": 80}',
            '    {"cmd": "feed_override",    "percent": 100}',
            '    {"cmd": "rapid_override",   "percent": 50}',
            '    {"cmd": "macro_write",      "variable": 500, "value": 1.5}',
            "",
            "  Press Ctrl+C to stop.",
            "=" * 58,
        ]
        for line in lines:
            log.info(line)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    bridge = HaasBridge()
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        log.info("Shutdown requested — bridge stopped")


if __name__ == "__main__":
    main()
