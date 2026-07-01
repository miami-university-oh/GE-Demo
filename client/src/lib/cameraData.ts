/* ============================================================
   cameraData.ts — YOLO Camera Simulation
   Makino Lab — 2 cameras with live detection simulation
   CAM-01: RealSense L515 — Human/arm detection, safety zone
           enforcement, proximity alerts near cobot cell
   CAM-02: Amcrest IP — PPE compliance, human detection,
           hard hat/vest monitoring, occupancy counting
   ============================================================ */

export type DetectionClass =
  | 'person'
  | 'hardhat'
  | 'vest'
  | 'no_hardhat'
  | 'no_vest'
  | 'safety_zone_breach';

export interface BoundingBox {
  id: string;
  cls: DetectionClass;
  label: string;
  confidence: number;
  x: number;   // 0–1 normalized
  y: number;
  w: number;
  h: number;
  color: string;
}

export interface PPECompliance {
  total: number;
  compliant: number;
  violations: string[];
}

export interface SafetyZone {
  id: string;
  label: string;
  status: 'clear' | 'breached' | 'warning';
  color: string;
}

export interface YOLOCameraData {
  id: string;
  name: string;
  location: string;
  streamUrl: string | null;
  status: 'live' | 'connecting' | 'offline';
  fps: number;
  resolution: string;
  detections: BoundingBox[];
  personCount: number;
  ppeCompliance: PPECompliance;
  safetyZones: SafetyZone[];
  lastAlarm: string | null;
  alarmActive: boolean;
  frameTs: number;
  totalDetections: number;
  reportReady: boolean;
}

// ── Detection color map ──────────────────────────────────────

export const DETECTION_COLORS: Record<DetectionClass, string> = {
  person:              '#22c55e',
  hardhat:             '#60a5fa',
  vest:                '#a78bfa',
  no_hardhat:          '#ef4444',
  no_vest:             '#f97316',
  safety_zone_breach:  '#ef4444',
};

// ── Helpers ──────────────────────────────────────────────────

/**
 * Returns a random float in [min, max).
 *
 * @param min - Lower bound (inclusive).
 * @param max - Upper bound (exclusive).
 */
function randF(min: number, max: number) {
  return Math.random() * (max - min) + min;
}
/**
 * Returns a random integer in [min, max].
 *
 * @param min - Lower bound (inclusive).
 * @param max - Upper bound (inclusive).
 */
function randI(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
/**
 * Returns a 6-character random alphanumeric string suitable for use as a {@link BoundingBox} ID.
 */
function uid() {
  return Math.random().toString(36).slice(2, 8);
}

/**
 * Creates a {@link BoundingBox} array representing one detected person at normalised position (x, y).
 *
 * Always emits a `person` box. If `withPPE` is true, adds compliant `hardhat` and `vest` boxes;
 * otherwise adds a single random violation box (`no_hardhat` or `no_vest`).
 *
 * @param withPPE - Whether the person is wearing full PPE.
 * @param x - Normalised horizontal position (0–1).
 * @param y - Normalised vertical position (0–1).
 * @returns Array of bounding boxes (person + PPE/violation overlays).
 */
function makePerson(withPPE: boolean, x: number, y: number): BoundingBox[] {
  const boxes: BoundingBox[] = [
    {
      id: uid(), cls: 'person', label: 'Person',
      confidence: randF(0.82, 0.99),
      x, y, w: randF(0.06, 0.10), h: randF(0.18, 0.28),
      color: DETECTION_COLORS.person,
    },
  ];
  if (withPPE) {
    boxes.push({
      id: uid(), cls: 'hardhat', label: 'Hard Hat ✓',
      confidence: randF(0.88, 0.99),
      x: x + randF(-0.01, 0.01), y: y - 0.02, w: 0.06, h: 0.05,
      color: DETECTION_COLORS.hardhat,
    });
    boxes.push({
      id: uid(), cls: 'vest', label: 'Safety Vest ✓',
      confidence: randF(0.85, 0.99),
      x: x + randF(-0.01, 0.01), y: y + 0.08, w: 0.08, h: 0.08,
      color: DETECTION_COLORS.vest,
    });
  } else {
    // Randomly choose violation type
    if (Math.random() > 0.4) {
      boxes.push({
        id: uid(), cls: 'no_hardhat', label: '⚠ No Hard Hat',
        confidence: randF(0.80, 0.96),
        x: x + randF(-0.01, 0.01), y: y - 0.02, w: 0.06, h: 0.05,
        color: DETECTION_COLORS.no_hardhat,
      });
    } else {
      boxes.push({
        id: uid(), cls: 'no_vest', label: '⚠ No Vest',
        confidence: randF(0.78, 0.94),
        x: x + randF(-0.01, 0.01), y: y + 0.08, w: 0.08, h: 0.08,
        color: DETECTION_COLORS.no_vest,
      });
    }
  }
  return boxes;
}

// ── Initial camera states ─────────────────────────────────────

/**
 * Creates the initial {@link YOLOCameraData} state for CAM-01 (Intel RealSense L515).
 *
 * CAM-01 monitors the UR5e cobot cell for human proximity and safety-zone breaches.
 * Starts with no detections and three clear safety zones (Cobot Reach, Pinch Point, Tool Change).
 *
 * @returns Initial YOLOCameraData for CAM-01.
 */
function makeInitialCam1(): YOLOCameraData {
  return {
    id: 'cam-01',
    name: 'CAM-01 — Machine Vision',
    location: 'Makino Lab — RealSense L515 (UR5e Cell)',
    streamUrl: 'http://localhost:8080/video_feed',
    status: 'live',
    fps: 30,
    resolution: '1280×720',
    detections: [],
    personCount: 0,
    ppeCompliance: { total: 0, compliant: 0, violations: [] },
    safetyZones: [
      { id: 'sz1', label: 'Cobot Reach Zone', status: 'clear', color: '#22c55e' },
      { id: 'sz2', label: 'Pinch Point Zone', status: 'clear', color: '#22c55e' },
      { id: 'sz3', label: 'Tool Change Area', status: 'clear', color: '#22c55e' },
    ],
    lastAlarm: null,
    alarmActive: false,
    frameTs: Date.now(),
    totalDetections: 0,
    reportReady: false,
  };
}

/**
 * Creates the initial {@link YOLOCameraData} state for CAM-02 (Amcrest IP overhead camera).
 *
 * CAM-02 monitors PPE compliance and occupancy across the Makino Lab. Initialises with a
 * randomised group of 2–4 persons, each with an 80% probability of wearing full PPE.
 *
 * @returns Initial YOLOCameraData for CAM-02.
 */
function makeInitialCam2(): YOLOCameraData {
  const persons = randI(2, 4);
  const detections: BoundingBox[] = [];
  let compliant = 0;
  const violations: string[] = [];

  for (let i = 0; i < persons; i++) {
    const hasPPE = Math.random() > 0.2;
    if (hasPPE) compliant++;
    else violations.push(`Person ${i + 1}: Missing hard hat`);
    detections.push(...makePerson(hasPPE, randF(0.08, 0.85), randF(0.25, 0.70)));
  }

  return {
    id: 'cam-02',
    name: 'CAM-02 — PPE Compliance',
    location: 'Makino Lab — Amcrest IP Camera (Overhead)',
    streamUrl: 'http://192.168.1.16:8888/cam02/index.m3u8',
    status: 'live',
    fps: 30,
    resolution: '1920×1080',
    detections,
    personCount: persons,
    ppeCompliance: { total: persons, compliant, violations },
    safetyZones: [
      { id: 'csz1', label: 'Machine Perimeter', status: 'clear', color: '#22c55e' },
      { id: 'csz2', label: 'Emergency Exit', status: 'clear', color: '#22c55e' },
      { id: 'csz3', label: 'Walkway', status: 'clear', color: '#22c55e' },
    ],
    lastAlarm: null,
    alarmActive: false,
    frameTs: Date.now( ),
    totalDetections: detections.length,
    reportReady: false,
  };
}

// ── Reactive Store ────────────────────────────────────────────

type Listener = () => void;

class CameraStore {
  cam1: YOLOCameraData = makeInitialCam1();
  cam2: YOLOCameraData = makeInitialCam2();

  private listeners = new Set<Listener>();
  private timer: ReturnType<typeof setInterval> | null = null;

  /**
   * Registers a listener for camera data updates. Starts the simulation timer on the first
   * subscriber and stops it when the last subscriber unsubscribes.
   *
   * @param fn - Callback invoked after every simulation tick.
   * @returns An unsubscribe function.
   */
  subscribe(fn: Listener) {
    this.listeners.add(fn);
    if (this.listeners.size === 1) this.startSim();
    return () => {
      this.listeners.delete(fn);
      if (this.listeners.size === 0) this.stopSim();
    };
  }

  /** Calls all registered listeners to signal updated camera data. */
  private notify() { this.listeners.forEach(fn => fn()); }

  /** Starts the 2-second tick interval that drives camera simulation. */
  private startSim() {
    this.timer = setInterval(() => this.tick(), 2000);
  }
  /** Clears the simulation tick interval. */
  private stopSim() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  /**
   * Advances simulation state for both cameras and notifies listeners.
   *
   * - CAM-01: Randomly places a human near the cobot (20% probability) and evaluates
   *   cobot reach / pinch-point zone breaches, triggering an alarm if breached.
   * - CAM-02: Drifts personnel count by ±1, re-evaluates PPE compliance for each person
   *   (15% violation rate), and independently checks each safety zone for a random breach
   *   (6% per zone per tick).
   */
  private tick() {
    // ── CAM-01 update: Human/Arm Detection ──
    const c1 = this.cam1;
    const humanNearCobot = Math.random() < 0.20;

    const cam1Detections: BoundingBox[] = [];
    if (humanNearCobot) {
      cam1Detections.push({
        id: uid(), cls: 'person', label: 'Human Detected',
        confidence: randF(0.85, 0.97),
        x: randF(0.30, 0.70), y: randF(0.20, 0.50), w: randF(0.08, 0.14), h: randF(0.22, 0.35),
        color: DETECTION_COLORS.person,
      });
    }

    // Safety zone logic for CAM-01
    const zones1 = c1.safetyZones.map(z => {
      let breach = false;
      if (z.id === 'sz1' && humanNearCobot && Math.random() < 0.6) breach = true;
      if (z.id === 'sz2' && Math.random() < 0.04) breach = true;
      return { ...z, status: breach ? 'breached' as const : 'clear' as const, color: breach ? '#ef4444' : '#22c55e' };
    });
    const anyBreach1 = zones1.some(z => z.status === 'breached');

    c1.personCount = humanNearCobot ? 1 : 0;
    c1.detections = cam1Detections;
    c1.ppeCompliance = { total: 0, compliant: 0, violations: [] };
    c1.safetyZones = zones1;
    c1.frameTs = Date.now();
    c1.totalDetections = cam1Detections.length;
    c1.alarmActive = anyBreach1;
    c1.lastAlarm = anyBreach1
      ? `Human entered cobot reach zone — Protective stop triggered`
      : c1.lastAlarm;

    // ── CAM-02 update: PPE/Personnel monitoring ──
    const c2 = this.cam2;
    const persons = Math.max(1, c2.personCount + randI(-1, 1));
    const detections: BoundingBox[] = [];
    let compliant = 0;
    const violations: string[] = [];

    for (let i = 0; i < persons; i++) {
      const hasPPE = Math.random() > 0.15;
      if (hasPPE) compliant++;
      else {
        if (Math.random() > 0.4) {
          violations.push(`Person ${i + 1}: Missing hard hat`);
        } else {
          violations.push(`Person ${i + 1}: Missing safety vest`);
        }
      }
      detections.push(...makePerson(hasPPE, randF(0.05, 0.88), randF(0.20, 0.72)));
    }

    // Safety zone logic for CAM-02
    const zones2 = c2.safetyZones.map(z => {
      const breach = Math.random() < 0.06;
      return { ...z, status: breach ? 'breached' as const : 'clear' as const, color: breach ? '#ef4444' : '#22c55e' };
    });
    const anyBreach2 = zones2.some(z => z.status === 'breached');
    const ppeViolation = violations.length > 0;

    c2.personCount = persons;
    c2.detections = detections;
    c2.ppeCompliance = { total: persons, compliant, violations };
    c2.safetyZones = zones2;
    c2.frameTs = Date.now();
    c2.totalDetections = detections.length;
    c2.alarmActive = anyBreach2 || ppeViolation;
    c2.lastAlarm = anyBreach2
      ? `Safety zone breach — ${zones2.find(z => z.status === 'breached')?.label}`
      : ppeViolation
        ? `PPE violation — ${violations[0]}`
        : c2.lastAlarm;

    this.notify();
  }
}

export const cameraStore = new CameraStore();
