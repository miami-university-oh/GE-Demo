/* ============================================================
   equipmentData.ts — Live Equipment Simulation
   Makino Lab (Area M / Grid 14) — Advanced Manufacturing Hub
   Machines:
     1. Haas TL-1     — CNC Lathe (Turning Center)
     2. UR5e Cobot    — Universal Robots Collaborative Arm
     3. Makino a51nx  — Horizontal Machining Center
     4. Makino d200Z  — 5-Axis VMC
     5. Makino PS95   — VMC
   ============================================================ */

// ── Types ──────────────────────────────────────────────────────

export type MachineStatus = 'running' | 'idle' | 'alarm' | 'setup' | 'offline';

export interface AxisPosition {
  x: number; // mm
  y: number; // mm
  z: number; // mm
}

export interface HaasVMCData {
  id: 'haas-vf2';
  name: 'Haas VF-2SS';
  type: 'VMC';
  status: MachineStatus;
  program: string;
  spindleRpm: number;       // RPM (0–12000)
  spindleLoad: number;      // % (0–100)
  feedRate: number;         // mm/min
  rapidOverride: number;    // % (0–100)
  feedOverride: number;     // % (0–100)
  position: AxisPosition;
  coolantTemp: number;      // °C
  coolantLevel: number;     // % (0–100)
  toolNumber: number;       // current tool (1–24)
  toolWear: number;         // % (0–100)
  cycleTime: number;        // seconds elapsed
  cycleTimeTotal: number;   // seconds total
  partsComplete: number;
  partsTarget: number;
  powerKw: number;
  alarms: string[];
  history: { t: number; rpm: number; load: number; power: number }[];
}

export interface HaasLathData {
  id: 'haas-tl1';
  name: 'Haas TL-1';
  type: 'Lathe';
  status: MachineStatus;
  program: string;
  spindleRpm: number;       // RPM (0–6000)
  spindleLoad: number;      // %
  spindleOverride: number;  // % (0–150)
  feedRate: number;         // mm/rev
  xAxisLoad: number;        // % X-axis servo load
  zAxisLoad: number;        // % Z-axis servo load
  cssMode: boolean;         // Constant Surface Speed
  cssTarget: number;        // m/min
  position: { x: number; z: number }; // 2-axis lathe
  chuckPressure: number;    // bar
  coolantTemp: number;      // °C
  toolStation: number;      // turret position (1–12)
  toolWear: number;         // %
  cycleTime: number;
  cycleTimeTotal: number;
  partsComplete: number;
  partsTarget: number;
  powerKw: number;
  alarms: string[];
  history: { t: number; rpm: number; load: number; power: number }[];
}

export interface CobotJoint {
  id: string;
  label: string;
  angle: number;   // degrees
  speed: number;   // deg/s
  torque: number;  // Nm
}

export interface UR5eData {
  id: 'ur5e';
  name: 'UR5e Cobot';
  type: 'Cobot';
  status: MachineStatus;
  program: string;
  mode: 'automatic' | 'manual' | 'freedrive' | 'paused';
  tcpSpeed: number;         // mm/s (Tool Center Point)
  tcpPosition: AxisPosition & { rx: number; ry: number; rz: number };
  payload: number;          // kg (0–5)
  payloadMax: number;       // kg = 5
  joints: CobotJoint[];
  safetyStatus: 'normal' | 'reduced' | 'protective_stop' | 'emergency_stop';
  humanProximity: number;   // cm (distance to nearest human)
  collaborativeMode: boolean;
  cyclesComplete: number;
  cycleTime: number;
  cycleTimeTotal: number;
  powerKw: number;
  temperature: number;      // controller temp °C
  alarms: string[];
  history: { t: number; tcpSpeed: number; payload: number; power: number }[];
}

// ── Makino Machine Types ──────────────────────────────────────

export interface MakinoA51nxData {
  id: 'makino-a51nx';
  name: 'Makino a51nx';
  type: 'HMC'; // Horizontal Machining Center
  status: MachineStatus;
  program: string;
  spindleRpm: number;       // RPM (0–14000)
  spindleLoad: number;      // %
  feedRate: number;         // mm/min
  feedOverride: number;     // %
  rapidOverride: number;    // %
  position: AxisPosition;
  palletId: number;         // active pallet (1 or 2)
  palletStatus: 'machining' | 'loading' | 'waiting';
  coolantTemp: number;      // °C
  coolantLevel: number;     // %
  toolNumber: number;       // current tool (1–60)
  toolWear: number;         // %
  cycleTime: number;
  cycleTimeTotal: number;
  partsComplete: number;
  partsTarget: number;
  powerKw: number;
  alarms: string[];
  history: { t: number; rpm: number; load: number; power: number }[];
}

export interface MakinoD200ZData {
  id: 'makino-d200z';
  name: 'Makino d200Z';
  type: '5-Axis VMC';
  status: MachineStatus;
  program: string;
  spindleRpm: number;       // RPM (0–20000)
  spindleLoad: number;      // %
  feedRate: number;         // mm/min
  feedOverride: number;     // %
  position: AxisPosition & { a: number; c: number }; // 5-axis A and C
  tiltAngle: number;        // A-axis degrees (-120 to +30)
  rotaryAngle: number;      // C-axis degrees (0–360)
  coolantTemp: number;      // °C
  toolNumber: number;       // current tool (1–40)
  toolWear: number;         // %
  cycleTime: number;
  cycleTimeTotal: number;
  partsComplete: number;
  partsTarget: number;
  powerKw: number;
  alarms: string[];
  history: { t: number; rpm: number; load: number; power: number }[];
}

export interface MakinoPS95Data {
  id: 'makino-ps95';
  name: 'Makino PS95';
  type: 'VMC';
  status: MachineStatus;
  program: string;
  spindleRpm: number;       // RPM (0–12000)
  spindleLoad: number;      // %
  feedRate: number;         // mm/min
  feedOverride: number;     // %
  rapidOverride: number;    // %
  position: AxisPosition;
  coolantTemp: number;      // °C
  coolantLevel: number;     // %
  toolNumber: number;       // current tool (1–30)
  toolWear: number;         // %
  cycleTime: number;
  cycleTimeTotal: number;
  partsComplete: number;
  partsTarget: number;
  powerKw: number;
  alarms: string[];
  history: { t: number; rpm: number; load: number; power: number }[];
}

export type Equipment = HaasLathData | UR5eData | MakinoA51nxData | MakinoD200ZData | MakinoPS95Data;

// ── Simulation State ──────────────────────────────────────────

/**
 * Returns a random float in [min, max] rounded to `dec` decimal places.
 *
 * @param min - Lower bound (inclusive).
 * @param max - Upper bound (inclusive).
 * @param dec - Decimal places to round to. Defaults to 1.
 */
function rand(min: number, max: number, dec = 1) {
  return parseFloat((Math.random() * (max - min) + min).toFixed(dec));
}
/**
 * Applies a small random delta to `val`, clamping the result to [min, max].
 *
 * @param val - Current value.
 * @param delta - Maximum total change magnitude (applied as ±delta/2).
 * @param min - Lower clamp bound.
 * @param max - Upper clamp bound.
 * @param dec - Decimal places to round the result to. Defaults to 1.
 * @returns New value after drift and clamp.
 */
function drift(val: number, delta: number, min: number, max: number, dec = 1) {
  return parseFloat(Math.min(max, Math.max(min, val + (Math.random() - 0.5) * delta)).toFixed(dec));
}
/**
 * Generates a seeded history array for equipment charts using a random walk.
 *
 * Starts from `init`, then for each step mutates each specified key by ±2% of its
 * current value, producing `len` entries that look like realistic historical data.
 *
 * @param keys - Keys of T whose numeric values should be randomly walked.
 * @param init - Starting values object (not mutated).
 * @param len - Number of history entries to generate. Defaults to 40.
 * @returns Array of `len` objects of type T.
 */
function makeHistory<T extends object>(keys: (keyof T)[], init: T, len = 40): T[] {
  const arr: T[] = [];
  let cur = { ...init };
  for (let i = 0; i < len; i++) {
    arr.push({ ...cur });
    // small random walk for each key
    for (const k of keys) {
      const v = cur[k] as number;
      (cur as any)[k] = parseFloat((v + (Math.random() - 0.5) * (v * 0.04)).toFixed(1));
    }
  }
  return arr;
}

// ── Initial State ─────────────────────────────────────────────

const VMC_INIT: HaasVMCData = {
  id: 'haas-vf2',
  name: 'Haas VF-2SS',
  type: 'VMC',
  status: 'running',
  program: 'O0042_BRACKET_V3.NC',
  spindleRpm: 4800,
  spindleLoad: 42,
  feedRate: 1200,
  rapidOverride: 100,
  feedOverride: 100,
  position: { x: -123.45, y: -67.20, z: -88.10 },
  coolantTemp: 22.4,
  coolantLevel: 78,
  toolNumber: 7,
  toolWear: 34,
  cycleTime: 420,
  cycleTimeTotal: 680,
  partsComplete: 12,
  partsTarget: 20,
  powerKw: 8.4,
  alarms: [],
  history: makeHistory(['rpm', 'load', 'power'] as any, { t: 0, rpm: 4800, load: 42, power: 8.4 }),
};

const LATHE_INIT: HaasLathData = {
  id: 'haas-tl1',
  name: 'Haas TL-1',
  type: 'Lathe',
  status: 'running',
  program: 'O0018_SHAFT_TURN.NC',
  spindleRpm: 1850,
  spindleLoad: 31,
  spindleOverride: 100,
  feedRate: 0.25,
  xAxisLoad: 12,
  zAxisLoad: 15,
  cssMode: true,
  cssTarget: 180,
  position: { x: -45.30, z: -112.80 },
  chuckPressure: 4.2,
  coolantTemp: 21.8,
  toolStation: 3,
  toolWear: 18,
  cycleTime: 185,
  cycleTimeTotal: 310,
  partsComplete: 28,
  partsTarget: 50,
  powerKw: 5.1,
  alarms: [],
  history: makeHistory(['rpm', 'load', 'power'] as any, { t: 0, rpm: 1850, load: 31, power: 5.1 }),
};

const UR5E_JOINTS: CobotJoint[] = [
  { id: 'base',     label: 'Base',      angle: 12.4,  speed: 8.2,  torque: 14.1 },
  { id: 'shoulder', label: 'Shoulder',  angle: -68.3, speed: 12.1, torque: 28.4 },
  { id: 'elbow',    label: 'Elbow',     angle: 94.7,  speed: 15.3, torque: 18.2 },
  { id: 'wrist1',   label: 'Wrist 1',   angle: -26.1, speed: 18.4, torque: 6.8  },
  { id: 'wrist2',   label: 'Wrist 2',   angle: 89.9,  speed: 22.1, torque: 5.4  },
  { id: 'wrist3',   label: 'Wrist 3',   angle: -14.5, speed: 31.0, torque: 3.2  },
];

const UR5E_INIT: UR5eData = {
  id: 'ur5e',
  name: 'UR5e Cobot',
  type: 'Cobot',
  status: 'running',
  program: 'PICK_AND_PLACE_V2.urp',
  mode: 'automatic',
  tcpSpeed: 148,
  tcpPosition: { x: 312.4, y: -88.1, z: 245.6, rx: -1.42, ry: 0.31, rz: 2.18 },
  payload: 2.8,
  payloadMax: 5,
  joints: UR5E_JOINTS,
  safetyStatus: 'normal',
  humanProximity: 182,
  collaborativeMode: true,
  cyclesComplete: 47,
  cycleTime: 18,
  cycleTimeTotal: 24,
  powerKw: 0.34,
  temperature: 38.2,
  alarms: [],
  history: makeHistory(['tcpSpeed', 'payload', 'power'] as any, { t: 0, tcpSpeed: 148, payload: 2.8, power: 0.34 }),
};

// ── Makino Initial States ─────────────────────────────────────

const MAKINO_A51NX_INIT: MakinoA51nxData = {
  id: 'makino-a51nx',
  name: 'Makino a51nx',
  type: 'HMC',
  status: 'running',
  program: 'O1042_HOUSING_HMC.NC',
  spindleRpm: 8400,
  spindleLoad: 58,
  feedRate: 2200,
  feedOverride: 100,
  rapidOverride: 100,
  position: { x: -88.40, y: -42.10, z: -155.30 },
  palletId: 1,
  palletStatus: 'machining',
  coolantTemp: 23.1,
  coolantLevel: 82,
  toolNumber: 12,
  toolWear: 22,
  cycleTime: 310,
  cycleTimeTotal: 540,
  partsComplete: 8,
  partsTarget: 16,
  powerKw: 14.2,
  alarms: [],
  history: makeHistory(['rpm', 'load', 'power'] as any, { t: 0, rpm: 8400, load: 58, power: 14.2 }),
};

const MAKINO_D200Z_INIT: MakinoD200ZData = {
  id: 'makino-d200z',
  name: 'Makino d200Z',
  type: '5-Axis VMC',
  status: 'running',
  program: 'O2018_IMPELLER_5AX.NC',
  spindleRpm: 16500,
  spindleLoad: 44,
  feedRate: 3800,
  feedOverride: 100,
  position: { x: -55.20, y: -28.80, z: -92.40, a: -35.0, c: 127.5 },
  tiltAngle: -35.0,
  rotaryAngle: 127.5,
  coolantTemp: 22.6,
  toolNumber: 5,
  toolWear: 31,
  cycleTime: 720,
  cycleTimeTotal: 1200,
  partsComplete: 3,
  partsTarget: 10,
  powerKw: 18.7,
  alarms: [],
  history: makeHistory(['rpm', 'load', 'power'] as any, { t: 0, rpm: 16500, load: 44, power: 18.7 }),
};

const MAKINO_PS95_INIT: MakinoPS95Data = {
  id: 'makino-ps95',
  name: 'Makino PS95',
  type: 'VMC',
  status: 'idle',
  program: 'O3005_BLOCK_MILL.NC',
  spindleRpm: 0,
  spindleLoad: 0,
  feedRate: 0,
  feedOverride: 100,
  rapidOverride: 100,
  position: { x: 0, y: 0, z: 0 },
  coolantTemp: 21.4,
  coolantLevel: 91,
  toolNumber: 1,
  toolWear: 8,
  cycleTime: 0,
  cycleTimeTotal: 480,
  partsComplete: 15,
  partsTarget: 20,
  powerKw: 1.2,
  alarms: [],
  history: makeHistory(['rpm', 'load', 'power'] as any, { t: 0, rpm: 0, load: 0, power: 1.2 }),
};

// ── WebSocket Live Data Integration ─────────────────────────
// Bridge scripts run on the lab PC (192.168.1.16)
// Haas TL-1  → ws://192.168.1.16:8765  (haas_ws_bridge.py)
// UR5e Cobot → ws://192.168.1.16:8766  (ur5e_unified_dashboard_v6_fixed.py --ws-port 8766)
//   Siri HTTP→ http://192.168.1.16:5000 (same script --siri-port 5000)
// Dashboard auto-switches from SIM to LIVE when a bridge connects.

export const BRIDGE_CONFIG = {
  haasTL1: {
    url: 'ws://192.168.1.16:8765',
    label: 'Haas TL-1',
  },
  ur5e: {
    url: 'ws://192.168.1.16:8766',
    label: 'UR5e Cobot',
  },
} as const;

export type BridgeStatus = 'connecting' | 'live' | 'offline' | 'sim';

// ── Reactive Store ────────────────────────────────────────────

type Listener = () => void;

class EquipmentStore {
  lathe: HaasLathData = { ...LATHE_INIT, history: [...LATHE_INIT.history] };
  cobot: UR5eData = { ...UR5E_INIT, joints: UR5E_INIT.joints.map(j => ({ ...j })), history: [...UR5E_INIT.history] };
  makinoA51nx: MakinoA51nxData = { ...MAKINO_A51NX_INIT, history: [...MAKINO_A51NX_INIT.history] };
  makinoD200Z: MakinoD200ZData = { ...MAKINO_D200Z_INIT, history: [...MAKINO_D200Z_INIT.history] };
  makinoPS95: MakinoPS95Data = { ...MAKINO_PS95_INIT, history: [...MAKINO_PS95_INIT.history] };

  // Bridge connection state
  haasBridgeStatus: BridgeStatus = 'sim';
  ur5eBridgeStatus: BridgeStatus = 'sim';
  private haasWs: WebSocket | null = null;
  private ur5eWs: WebSocket | null = null;
  private haasReconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private ur5eReconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private listeners = new Set<Listener>();
  private timer: ReturnType<typeof setInterval> | null = null;

  /**
   * Registers a listener for equipment data updates.
   *
   * On the first subscriber: starts the simulation fallback timer and attempts to open
   * WebSocket connections to both the Haas TL-1 and UR5e bridges. When the last
   * subscriber unsubscribes, the sim timer is stopped and both bridges are disconnected.
   *
   * @param fn - Callback invoked whenever equipment state changes.
   * @returns An unsubscribe function.
   */
  subscribe(fn: Listener) {
    this.listeners.add(fn);
    if (this.listeners.size === 1) {
      this.startSim();
      this.connectHaasBridge();
      this.connectUR5eBridge();
    }
    return () => {
      this.listeners.delete(fn);
      if (this.listeners.size === 0) {
        this.stopSim();
        this.disconnectBridges();
      }
    };
  }

  /**
   * Opens a WebSocket connection to the Haas TL-1 bridge at {@link BRIDGE_CONFIG.haasTL1.url}.
   *
   * Parses incoming `tier1` / `tier2` / `tier4` structured messages as well as the legacy
   * flat format, and maps fields onto `this.lathe`. Appends a history point on every
   * message. Schedules an 8-second auto-reconnect on close while subscribers remain.
   */
  // ── Haas TL-1 WebSocket bridge ──────────────────────────────
  private connectHaasBridge() {
    if (typeof WebSocket === 'undefined') return;
    try {
      const ws = new WebSocket(BRIDGE_CONFIG.haasTL1.url);
      this.haasWs = ws;
      this.haasBridgeStatus = 'connecting';

      ws.onopen = () => {
        this.haasBridgeStatus = 'live';
        this.notify();
      };

      ws.onmessage = (evt) => {
        try {
          const d = JSON.parse(evt.data as string);
          const l = this.lathe;

          // ── haas_ws_bridge.py status message ──
          if (d.type === 'status') {
            this.haasBridgeStatus = d.data?.connected ? 'live' : 'offline';
            this.notify();
            return;
          }

          // ── haas_ws_bridge.py / haas_server_v3: {type, data, timestamp} ──
          if (d.type === 'tier1' && d.data) {
            const t = d.data;
            const execStatus = (t.execution_status ?? '').toUpperCase();
            if      (execStatus.includes('ALARM'))     l.status = 'alarm';
            else if (execStatus.includes('FEED HOLD')) l.status = 'idle';
            else if (execStatus.includes('RUNNING'))   l.status = 'running';
            else if (execStatus === 'IDLE')            l.status = 'idle';
            // else: leave current status (no change on empty)
            if (t.program_name)                        l.program         = t.program_name;
            if (t.spindle_speed_rpm     != null)       l.spindleRpm      = t.spindle_speed_rpm;
            if (t.spindle_load_percent  != null)       l.spindleLoad     = t.spindle_load_percent;
            if (t.spindle_override_percent != null)    l.spindleOverride = t.spindle_override_percent;
            if (t.x_work_coord          != null)       l.position.x      = t.x_work_coord;
            if (t.z_work_coord          != null)       l.position.z      = t.z_work_coord;
            if (t.current_tool_number   != null)       l.toolStation     = Math.round(t.current_tool_number);
            if (t.x_axis_load_percent   != null)       l.xAxisLoad       = t.x_axis_load_percent;
            if (t.z_axis_load_percent   != null)       l.zAxisLoad       = t.z_axis_load_percent;
            l.powerKw = Math.round((l.spindleLoad / 100) * 7.5 * 10) / 10;
            if (t.current_alarm_codes)  l.alarms = [t.current_alarm_codes];
            else if (!d.data.current_alarm_codes)  l.alarms = [];
          }

          else if (d.type === 'tier2' && d.data) {
            const t = d.data;
            if (t.present_part_time_seconds != null) l.cycleTime     = t.present_part_time_seconds;
            if (t.active_tool_life_remaining != null) l.toolWear     = Math.max(0, Math.min(100, 100 - t.active_tool_life_remaining));
          }

          else if (d.type === 'tier4' && d.data) {
            const t = d.data;
            if (Array.isArray(t.active_alarms) && t.active_alarms.length > 0) {
              l.alarms = t.active_alarms.map((a: any) => a.title ?? String(a));
            } else if (t.alarm_count === 0) {
              l.alarms = [];
            }
          }

          // ── legacy simple bridge format (haas_bridge.py in machine-bridges) ──
          else if (!d.type) {
            if (d.status === 'offline') { this.haasBridgeStatus = 'offline'; this.notify(); return; }
            if (d.status)               l.status      = d.status as MachineStatus;
            if (d.program)              l.program     = d.program;
            if (d.spindleRpm  != null)  l.spindleRpm  = d.spindleRpm;
            if (d.spindleLoad != null)  l.spindleLoad = d.spindleLoad;
            if (d.feedRate    != null)  l.feedRate    = d.feedRate;
            if (d.position?.x != null)  l.position.x  = d.position.x;
            if (d.position?.z != null)  l.position.z  = d.position.z;
            if (d.toolNumber  != null)  l.toolStation = d.toolNumber;
            if (d.cycleTime   != null)  l.cycleTime   = d.cycleTime;
            if (d.partCount   != null)  l.partsComplete = d.partCount;
            if (d.powerKw     != null)  l.powerKw     = d.powerKw;
            if (Array.isArray(d.alarms)) l.alarms     = d.alarms;
          }

          const now = Date.now();
          l.history = [...l.history.slice(-39), { t: now, rpm: l.spindleRpm, load: l.spindleLoad, power: l.powerKw }];
          this.haasBridgeStatus = 'live';
          this.notify();
        } catch (_) { /* ignore malformed packets */ }
      };

      ws.onerror = () => {
        this.haasBridgeStatus = 'offline';
        this.notify();
      };

      ws.onclose = () => {
        this.haasBridgeStatus = 'sim';
        this.haasWs = null;
        this.notify();
        // Auto-reconnect after 8 seconds
        if (this.listeners.size > 0) {
          this.haasReconnectTimer = setTimeout(() => this.connectHaasBridge(), 8000);
        }
      };
    } catch (_) {
      this.haasBridgeStatus = 'sim';
    }
  }

  /**
   * Opens a WebSocket connection to the UR5e bridge at {@link BRIDGE_CONFIG.ur5e.url}.
   *
   * Parses joint positions/velocities/torques, TCP pose and speed, safety mode, and
   * robot/runtime mode codes, mapping them onto `this.cobot`. Appends a history point
   * on every message. Schedules an 8-second auto-reconnect on close while subscribers remain.
   */
  // ── UR5e WebSocket bridge ────────────────────────────────────
  private connectUR5eBridge() {
    if (typeof WebSocket === 'undefined') return;
    try {
      const ws = new WebSocket(BRIDGE_CONFIG.ur5e.url);
      this.ur5eWs = ws;
      this.ur5eBridgeStatus = 'connecting';

      ws.onopen = () => {
        this.ur5eBridgeStatus = 'live';
        this.notify();
      };

      ws.onmessage = (evt) => {
        try {
          const d = JSON.parse(evt.data as string);
          if (d.status === 'offline') {
            this.ur5eBridgeStatus = 'offline';
            this.notify();
            return;
          }
          const c = this.cobot;

          // ── Format A: ur5e_unified_dashboard_v5.py raw record ──
          // Top-level keys: joints, tcp, power, status, motion_scaling, timing
          if (d.joints && typeof d.joints === 'object' && !Array.isArray(d.joints)) {
            const JOINT_NAMES = ['base', 'shoulder', 'elbow', 'wrist1', 'wrist2', 'wrist3'];
            const JOINT_LABELS = ['Base', 'Shoulder', 'Elbow', 'Wrist 1', 'Wrist 2', 'Wrist 3'];
            const qPos  = d.joints.actual_position_rad   ?? {};
            const qVel  = d.joints.actual_velocity_rad_s ?? {};
            const qCur  = d.joints.actual_current_A      ?? {};
            const qTorq = d.joints.actual_current_as_torque_Nm ?? d.joints.target_moment_Nm ?? {};
            c.joints = JOINT_NAMES.map((k, i) => ({
              id:     `J${i+1}`,
              label:  JOINT_LABELS[i],
              angle:  Math.round(((qPos[k] ?? 0) * 180 / Math.PI) * 100) / 100,
              speed:  Math.round(((qVel[k] ?? 0) * 180 / Math.PI) * 100) / 100,
              torque: Math.round(Math.abs(qTorq[k] ?? qCur[k] ?? 0) * 10) / 10,
            }));

            // TCP
            const tcp = d.tcp?.actual_pose_m_rad ?? {};
            const tcpSpd = d.tcp?.actual_speed_m_s ?? {};
            c.tcpPosition.x  = Math.round((tcp.x  ?? 0) * 1e5) / 100;
            c.tcpPosition.y  = Math.round((tcp.y  ?? 0) * 1e5) / 100;
            c.tcpPosition.z  = Math.round((tcp.z  ?? 0) * 1e5) / 100;
            c.tcpPosition.rx = Math.round(((tcp.rx ?? 0) * 180 / Math.PI) * 100) / 100;
            c.tcpPosition.ry = Math.round(((tcp.ry ?? 0) * 180 / Math.PI) * 100) / 100;
            c.tcpPosition.rz = Math.round(((tcp.rz ?? 0) * 180 / Math.PI) * 100) / 100;
            const sv = Object.values(tcpSpd) as number[];
            c.tcpSpeed = sv.length >= 3
              ? Math.round(Math.sqrt(sv[0]**2 + sv[1]**2 + sv[2]**2) * 1000 * 10) / 10
              : 0;

            // Power
            const v48 = d.power?.robot_voltage_48V ?? 0;
            const iRobot = d.power?.robot_current_A ?? 0;
            c.powerKw = Math.round(v48 * iRobot) / 1000;

            // Speed scaling
            const ss = d.motion_scaling?.speed_scaling_factor ?? 1;
            c.payload = Math.round(ss * 500) / 100; // map 0-1 → 0-5 kg equiv display

            // Status
            const st = d.status ?? {};
            const robotMode = st.robot_mode_code ?? -1;
            const safetyCode = st.safety_status_code ?? 1;
            const runtimeCode = st.runtime_state_code ?? 0;
            if (safetyCode >= 3) c.status = 'alarm';
            else if (robotMode === 7 && runtimeCode === 2) c.status = 'running';
            else if (robotMode === 5) c.status = 'idle';
            else if (robotMode <= 4) c.status = 'offline';
            else c.status = 'idle';

            const safetyDesc = String(st.safety_mode_desc ?? st.safety_status_desc ?? '').toUpperCase();
            if (safetyDesc.includes('NORMAL'))    c.safetyStatus = 'normal';
            else if (safetyDesc.includes('REDUCED')) c.safetyStatus = 'reduced';
            else if (safetyDesc.includes('STOP'))    c.safetyStatus = 'protective_stop';
            else if (safetyDesc.includes('EMERGENCY')) c.safetyStatus = 'emergency_stop';

            c.alarms = [];
            if (st.is_protective_stopped) c.alarms.push('PROTECTIVE STOP');
            if (st.is_emergency_stopped)  c.alarms.push('EMERGENCY STOP');

          } else {
            // ── Format B: ur5e_bridge.py simple format ──
            if (d.status)        c.status    = d.status as MachineStatus;
            if (d.program)       c.program   = d.program;
            if (d.tcpSpeed !== undefined)    c.tcpSpeed  = d.tcpSpeed;
            if (d.tcpPosition) {
              c.tcpPosition.x  = d.tcpPosition.x  ?? c.tcpPosition.x;
              c.tcpPosition.y  = d.tcpPosition.y  ?? c.tcpPosition.y;
              c.tcpPosition.z  = d.tcpPosition.z  ?? c.tcpPosition.z;
              c.tcpPosition.rx = d.tcpPosition.rx ?? c.tcpPosition.rx;
              c.tcpPosition.ry = d.tcpPosition.ry ?? c.tcpPosition.ry;
              c.tcpPosition.rz = d.tcpPosition.rz ?? c.tcpPosition.rz;
            }
            if (d.speedFraction !== undefined) c.payload = d.speedFraction / 100 * 5;
            if (Array.isArray(d.joints) && d.joints.length === 6) {
              c.joints = d.joints.map((j: any, i: number) => ({
                id:     c.joints[i]?.id     ?? `J${i+1}`,
                label:  j.label             ?? c.joints[i]?.label ?? `Joint ${i+1}`,
                angle:  j.angle  ?? c.joints[i]?.angle  ?? 0,
                speed:  j.speed  ?? c.joints[i]?.speed  ?? 0,
                torque: j.torque ?? c.joints[i]?.torque ?? 0,
              }));
            }
            if (d.powerKw !== undefined) c.powerKw = d.powerKw;
            if (d.safetyMode) {
              if (d.safetyMode === 'NORMAL')           c.safetyStatus = 'normal';
              else if (d.safetyMode === 'REDUCED')     c.safetyStatus = 'reduced';
              else if (d.safetyMode.includes('STOP'))  c.safetyStatus = 'protective_stop';
              else if (d.safetyMode.includes('EMERGENCY')) c.safetyStatus = 'emergency_stop';
            }
            if (Array.isArray(d.alarms)) c.alarms = d.alarms;
          }

          const now = Date.now();
          c.history = [...c.history.slice(-39), { t: now, tcpSpeed: c.tcpSpeed, payload: c.payload, power: c.powerKw }];
          this.ur5eBridgeStatus = 'live';
          this.notify();
        } catch (_) { /* ignore malformed packets */ }
      };

      ws.onerror = () => {
        this.ur5eBridgeStatus = 'offline';
        this.notify();
      };

      ws.onclose = () => {
        this.ur5eBridgeStatus = 'sim';
        this.ur5eWs = null;
        this.notify();
        if (this.listeners.size > 0) {
          this.ur5eReconnectTimer = setTimeout(() => this.connectUR5eBridge(), 8000);
        }
      };
    } catch (_) {
      this.ur5eBridgeStatus = 'sim';
    }
  }

  /**
   * Closes both WebSocket connections and clears any pending reconnect timers.
   */
  private disconnectBridges() {
    if (this.haasWs)  { this.haasWs.close();  this.haasWs  = null; }
    if (this.ur5eWs)  { this.ur5eWs.close();  this.ur5eWs  = null; }
    if (this.haasReconnectTimer)  { clearTimeout(this.haasReconnectTimer);  this.haasReconnectTimer  = null; }
    if (this.ur5eReconnectTimer)  { clearTimeout(this.ur5eReconnectTimer);  this.ur5eReconnectTimer  = null; }
  }

  /** Calls all registered listeners to signal updated equipment state. */
  private notify() {
    this.listeners.forEach(fn => fn());
  }

  /** Starts the 1.5-second simulation tick interval used as a fallback when bridges are offline. */
  private startSim() {
    this.timer = setInterval(() => this.tick(), 1500);
  }
  /** Clears the simulation tick interval. */
  private stopSim() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /**
   * Advances simulation state for all five machines and notifies listeners.
   *
   * - **Lathe**: drifts spindle RPM/load, feed rate, coolant, chuck pressure, tool wear,
   *   and axis positions; increments cycle time and part count; sets a low-pressure alarm
   *   when chuck pressure < 2.8 bar.
   * - **Cobot**: drifts TCP speed/position, joint angles, payload, and temperature; triggers
   *   a protective stop when human proximity < 50 cm, or reduced-speed mode < 100 cm.
   * - **Makino A51NX / D200Z / PS95**: drifts spindle, feed, coolant, axes, and tool wear;
   *   A51NX alternates pallet IDs on cycle completion; PS95 randomly starts cycles from idle.
   *
   * A history point is appended for each machine (capped at 40 entries) on every tick.
   */
  private tick() {
    const now = Date.now();

    // ── Lathe ──
    const l = this.lathe;
    l.spindleRpm = drift(l.spindleRpm, 150, 0, 6000, 0);
    l.spindleLoad = drift(l.spindleLoad, 5, 0, 100, 1);
    l.feedRate = drift(l.feedRate, 0.02, 0.05, 1.5, 3);
    l.coolantTemp = drift(l.coolantTemp, 0.3, 18, 35, 1);
    l.chuckPressure = drift(l.chuckPressure, 0.1, 2.5, 6.0, 2);
    l.toolWear = Math.min(100, l.toolWear + rand(0, 0.05, 1));
    l.powerKw = drift(l.powerKw, 0.4, 0.3, 15, 2);
    l.position.x = drift(l.position.x, 3, -200, 0, 2);
    l.position.z = drift(l.position.z, 4, -400, 0, 2);
    l.cycleTime = Math.min(l.cycleTimeTotal, l.cycleTime + 1.5);
    if (l.cycleTime >= l.cycleTimeTotal) {
      l.cycleTime = 0;
      l.partsComplete = Math.min(l.partsTarget, l.partsComplete + 1);
    }
    l.alarms = l.chuckPressure < 2.8 ? ['LOW CHUCK PRESSURE — Check Hydraulics'] : [];
    l.history = [...l.history.slice(-39), { t: now, rpm: l.spindleRpm, load: l.spindleLoad, power: l.powerKw }];

    // ── Cobot ──
    const c = this.cobot;
    c.tcpSpeed = drift(c.tcpSpeed, 20, 0, 250, 1);
    c.payload = drift(c.payload, 0.2, 0, 5, 2);
    c.powerKw = drift(c.powerKw, 0.04, 0.05, 0.5, 3);
    c.temperature = drift(c.temperature, 0.3, 30, 55, 1);
    c.humanProximity = drift(c.humanProximity, 15, 30, 400, 0);
    c.tcpPosition.x = drift(c.tcpPosition.x, 8, -600, 600, 1);
    c.tcpPosition.y = drift(c.tcpPosition.y, 8, -600, 600, 1);
    c.tcpPosition.z = drift(c.tcpPosition.z, 6, 0, 800, 1);
    c.joints = c.joints.map(j => ({
      ...j,
      angle: drift(j.angle, 3, -180, 180, 1),
      speed: drift(j.speed, 2, 0, 60, 1),
      torque: drift(j.torque, 1, 0, 50, 1),
    }));
    c.cycleTime = Math.min(c.cycleTimeTotal, c.cycleTime + 1.5);
    if (c.cycleTime >= c.cycleTimeTotal) {
      c.cycleTime = 0;
      c.cyclesComplete++;
    }
    // Safety: if human too close, trigger protective stop
    if (c.humanProximity < 50) {
      c.safetyStatus = 'protective_stop';
      c.status = 'alarm';
      c.alarms = [`PROTECTIVE STOP — Human at ${c.humanProximity}cm`];
    } else if (c.humanProximity < 100) {
      c.safetyStatus = 'reduced';
      c.status = 'running';
      c.alarms = [`REDUCED SPEED — Human at ${c.humanProximity}cm`];
    } else {
      c.safetyStatus = 'normal';
      c.status = 'running';
      c.alarms = [];
    }
    c.history = [...c.history.slice(-39), { t: now, tcpSpeed: c.tcpSpeed, payload: c.payload, power: c.powerKw }];

    // ── Makino a51nx ──
    const ma = this.makinoA51nx;
    ma.spindleRpm = drift(ma.spindleRpm, 300, 0, 14000, 0);
    ma.spindleLoad = drift(ma.spindleLoad, 8, 0, 100, 1);
    ma.feedRate = drift(ma.feedRate, 150, 0, 6000, 0);
    ma.coolantTemp = drift(ma.coolantTemp, 0.3, 18, 38, 1);
    ma.coolantLevel = drift(ma.coolantLevel, 0.3, 20, 100, 1);
    ma.toolWear = Math.min(100, ma.toolWear + rand(0, 0.06, 1));
    ma.powerKw = drift(ma.powerKw, 1.0, 1.0, 30, 2);
    ma.position.x = drift(ma.position.x, 6, -500, 0, 2);
    ma.position.y = drift(ma.position.y, 4, -400, 0, 2);
    ma.position.z = drift(ma.position.z, 8, -600, 0, 2);
    ma.cycleTime = Math.min(ma.cycleTimeTotal, ma.cycleTime + 1.5);
    if (ma.cycleTime >= ma.cycleTimeTotal) {
      ma.cycleTime = 0;
      ma.partsComplete = Math.min(ma.partsTarget, ma.partsComplete + 1);
      ma.palletId = ma.palletId === 1 ? 2 : 1;
      ma.palletStatus = 'loading';
      setTimeout(() => { ma.palletStatus = 'machining'; this.notify(); }, 3000);
    }
    ma.alarms = ma.toolWear > 80 ? ['TOOL WEAR LIMIT — T12 Replace Soon'] : [];
    ma.history = [...ma.history.slice(-39), { t: now, rpm: ma.spindleRpm, load: ma.spindleLoad, power: ma.powerKw }];

    // ── Makino d200Z ──
    const md = this.makinoD200Z;
    md.spindleRpm = drift(md.spindleRpm, 500, 0, 20000, 0);
    md.spindleLoad = drift(md.spindleLoad, 7, 0, 100, 1);
    md.feedRate = drift(md.feedRate, 200, 0, 8000, 0);
    md.coolantTemp = drift(md.coolantTemp, 0.3, 18, 38, 1);
    md.toolWear = Math.min(100, md.toolWear + rand(0, 0.07, 1));
    md.powerKw = drift(md.powerKw, 1.5, 1.0, 35, 2);
    md.position.x = drift(md.position.x, 5, -400, 0, 2);
    md.position.y = drift(md.position.y, 4, -300, 0, 2);
    md.position.z = drift(md.position.z, 6, -500, 0, 2);
    md.tiltAngle = drift(md.tiltAngle, 2, -120, 30, 1);
    md.rotaryAngle = drift(md.rotaryAngle, 5, 0, 360, 1);
    md.position.a = md.tiltAngle;
    md.position.c = md.rotaryAngle;
    md.cycleTime = Math.min(md.cycleTimeTotal, md.cycleTime + 1.5);
    if (md.cycleTime >= md.cycleTimeTotal) {
      md.cycleTime = 0;
      md.partsComplete = Math.min(md.partsTarget, md.partsComplete + 1);
    }
    md.alarms = md.toolWear > 75 ? ['5-AXIS TOOL WEAR — T05 Inspect'] : [];
    md.history = [...md.history.slice(-39), { t: now, rpm: md.spindleRpm, load: md.spindleLoad, power: md.powerKw }];

    // ── Makino PS95 ──
    const mp = this.makinoPS95;
    // PS95 is idle — occasionally starts a cycle
    if (mp.status === 'idle' && Math.random() < 0.005) {
      mp.status = 'running';
      mp.spindleRpm = 3200;
    }
    if (mp.status === 'running') {
      mp.spindleRpm = drift(mp.spindleRpm, 200, 0, 12000, 0);
      mp.spindleLoad = drift(mp.spindleLoad, 5, 0, 100, 1);
      mp.feedRate = drift(mp.feedRate, 100, 0, 4000, 0);
      mp.powerKw = drift(mp.powerKw, 0.5, 1.0, 22, 2);
      mp.position.x = drift(mp.position.x, 5, -600, 0, 2);
      mp.position.y = drift(mp.position.y, 4, -500, 0, 2);
      mp.position.z = drift(mp.position.z, 5, -500, 0, 2);
      mp.cycleTime = Math.min(mp.cycleTimeTotal, mp.cycleTime + 1.5);
      if (mp.cycleTime >= mp.cycleTimeTotal) {
        mp.cycleTime = 0;
        mp.partsComplete = Math.min(mp.partsTarget, mp.partsComplete + 1);
        mp.status = 'idle';
        mp.spindleRpm = 0;
        mp.spindleLoad = 0;
        mp.feedRate = 0;
        mp.powerKw = 1.2;
      }
    }
    mp.coolantTemp = drift(mp.coolantTemp, 0.2, 18, 35, 1);
    mp.toolWear = Math.min(100, mp.toolWear + rand(0, 0.02, 1));
    mp.alarms = [];
    mp.history = [...mp.history.slice(-39), { t: now, rpm: mp.spindleRpm, load: mp.spindleLoad, power: mp.powerKw }];

    this.notify();
  }
}

export const equipmentStore = new EquipmentStore();

// ── Status helpers ────────────────────────────────────────────

export const MACHINE_STATUS_COLOR: Record<MachineStatus, string> = {
  running: '#22c55e',
  idle:    '#60a5fa',
  alarm:   '#ef4444',
  setup:   '#f59e0b',
  offline: '#6b7280',
};

export const MACHINE_STATUS_LABEL: Record<MachineStatus, string> = {
  running: 'RUNNING',
  idle:    'IDLE',
  alarm:   'ALARM',
  setup:   'SETUP',
  offline: 'OFFLINE',
};
