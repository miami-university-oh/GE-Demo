// ============================================================
// BUILDING DATA MODEL — IIoT Dashboard
// T-shaped building: East Wing, West Wing, North Wing
// Two floors per wing, multiple lab zones per floor
// ============================================================

export type ZoneStatus = 'ok' | 'warn' | 'critical' | 'offline';

export interface SensorData {
  temperature: number;       // °C
  humidity: number;          // %
  co2: number;               // ppm
  energyKw: number;          // kW
  occupancy: number;         // count
  equipmentOnline: number;   // count
  equipmentTotal: number;    // count
  airQuality: number;        // AQI 0-500
  networkLoad: number;       // % utilization
  powerFactor: number;       // 0-1
}

export interface SensorHistory {
  timestamp: number;
  temperature: number;
  humidity: number;
  energyKw: number;
  co2: number;
}

export interface Zone {
  id: string;
  name: string;
  shortName: string;
  wing: 'east' | 'west' | 'north';
  floor: Floor;
  type: 'lab' | 'office' | 'server' | 'conference' | 'corridor' | 'utility';
  area: number;              // m²
  status: ZoneStatus;
  sensors: SensorData;
  history: SensorHistory[];
  alerts: Alert[];
  description: string;
}

export interface Alert {
  id: string;
  zoneId: string;
  zoneName: string;
  type: 'temperature' | 'humidity' | 'co2' | 'energy' | 'equipment' | 'network';
  severity: 'warn' | 'critical';
  message: string;
  timestamp: number;
}

export type Wing = 'east' | 'west' | 'north';
export type Floor = 0 | 1 | 2; // 0 = Basement, 1 = Ground Floor, 2 = Upper Floor

// ---- Sensor simulation helpers ----
function rand(min: number, max: number, decimals = 1): number {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals));
}

function generateHistory(baseTemp: number, baseEnergy: number): SensorHistory[] {
  const now = Date.now();
  return Array.from({ length: 20 }, (_, i) => ({
    timestamp: now - (19 - i) * 3 * 60 * 1000,
    temperature: parseFloat((baseTemp + (Math.random() - 0.5) * 2).toFixed(1)),
    humidity: parseFloat((45 + (Math.random() - 0.5) * 10).toFixed(1)),
    energyKw: parseFloat((baseEnergy + (Math.random() - 0.5) * 3).toFixed(2)),
    co2: parseFloat((600 + (Math.random() - 0.5) * 200).toFixed(0)),
  }));
}

function computeStatus(sensors: SensorData): ZoneStatus {
  if (sensors.temperature > 30 || sensors.co2 > 1200 || sensors.airQuality > 150) return 'critical';
  if (sensors.temperature > 26 || sensors.co2 > 900 || sensors.humidity > 70 || sensors.airQuality > 100) return 'warn';
  if (sensors.equipmentOnline === 0) return 'offline';
  return 'ok';
}

function makeSensors(overrides: Partial<SensorData> = {}): SensorData {
  const base: SensorData = {
    temperature: rand(20, 24),
    humidity: rand(40, 60),
    co2: rand(450, 800, 0),
    energyKw: rand(5, 25),
    occupancy: rand(0, 20, 0),
    equipmentOnline: rand(8, 15, 0),
    equipmentTotal: 15,
    airQuality: rand(20, 80, 0),
    networkLoad: rand(20, 75),
    powerFactor: rand(0.85, 0.98),
  };
  return { ...base, ...overrides };
}

// ---- Zone definitions ----
// Real lab layout — room numbers: 1xxx = Floor 1, 2xxx = Floor 2, Basement = Floor 0
const zoneDefinitions: Omit<Zone, 'status' | 'sensors' | 'history' | 'alerts'>[] = [
  // ── BASEMENT (FLOOR 0) ──
  { id: 'B0-MAK', name: 'Subtractive Mfg Lab (Makino)', shortName: 'MAK', wing: 'east', floor: 0, type: 'lab', area: 420, description: 'Room 1067 · Large-format Makino CNC machining centers, 5-axis mills, horizontal machining cells and precision subtractive manufacturing' },
  { id: 'B0-WLD', name: 'Welding Lab', shortName: 'WLD', wing: 'east', floor: 0, type: 'lab', area: 140, description: 'Welding Lab · MIG, TIG, Stick and plasma cutting stations; fume extraction, welding curtains and PPE storage — positioned between Makino and Integrated Industry labs' },
  { id: 'B0-INT', name: 'Subtractive Mfg Lab (Integrated Industry)', shortName: 'INTI', wing: 'west', floor: 0, type: 'lab', area: 380, description: 'Room 1059 · Integrated industry subtractive manufacturing — multi-axis CNC lathes, turning centers, inspection stations and industry-partner equipment' },

  // ── EAST WING FLOOR 1 ──
  { id: 'E1-SUB1', name: 'Subtractive Mfg Lab (Makino / Welding)', shortName: 'SUB1', wing: 'east', floor: 1, type: 'lab', area: 240, description: 'Room 1067 · Makino CNC machining centers, MIG/TIG welding stations and metal fabrication' },
  { id: 'E1-SUB2', name: 'Subtractive Mfg Lab (Integrated Industry)', shortName: 'SUB2', wing: 'east', floor: 1, type: 'lab', area: 210, description: 'Room 1059 · Integrated industry subtractive manufacturing with multi-axis CNC and inspection' },
  { id: 'E1-ELE', name: 'Electronics Lab', shortName: 'ELE', wing: 'east', floor: 1, type: 'lab', area: 155, description: 'Room 1061 · PCB design, embedded systems, soldering stations and electronics testing benches' },
  { id: 'E1-MET', name: 'Metrology Lab', shortName: 'MET', wing: 'east', floor: 1, type: 'lab', area: 140, description: 'Room 1063 · CMM machines, precision measurement, dimensional inspection and calibration' },

  // ── EAST WING FLOOR 2 ──
  { id: 'E2-PROJ', name: 'Projects Lab / Robotics Arena / Biobubble', shortName: 'PROJ', wing: 'east', floor: 2, type: 'lab', area: 320, description: 'Room 2040 · Butler Tech projects lab, open robotics arena and biobubble research environment' },
  { id: 'E2-ADD', name: 'Additive Manufacturing Lab', shortName: 'ADD', wing: 'east', floor: 2, type: 'lab', area: 175, description: 'Room 1057 · FDM/SLA/SLS 3D printing, metal AM, post-processing and rapid prototyping' },
  { id: 'E2-NET', name: 'Networking Lab', shortName: 'NET', wing: 'east', floor: 2, type: 'lab', area: 160, description: 'Room 1056 · Industrial networking, Cisco infrastructure, 5G testbed and micro-processing' },
  { id: 'E2-THERM', name: 'Thermal & Fluid Science Lab', shortName: 'TFS', wing: 'east', floor: 2, type: 'lab', area: 185, description: 'Room 1053 · Heat transfer, fluid dynamics, HVAC systems and thermodynamics experiments' },

  // ── WEST WING FLOOR 1 ──
  { id: 'W1-ROB', name: 'Robotics & Automation Lab', shortName: 'ROB', wing: 'west', floor: 1, type: 'lab', area: 220, description: 'Room 1050 · Industrial robot arms, PLC automation, conveyor systems and cobots' },
  { id: 'W1-ELEC', name: 'Electromechanical Lab', shortName: 'EMC', wing: 'west', floor: 1, type: 'lab', area: 190, description: 'Room 1049 · Motor drives, servo systems, electromechanical integration and power electronics' },
  { id: 'W1-SRV', name: 'Server Room', shortName: 'SRV', wing: 'west', floor: 1, type: 'server', area: 100, description: 'Data center, rack servers, UPS, cooling and power distribution for all labs' },
  { id: 'W1-UTIL', name: 'Utility & Storage', shortName: 'UTL', wing: 'west', floor: 1, type: 'utility', area: 85, description: 'HVAC plant, electrical panels, building management systems and equipment storage' },

  // ── WEST WING FLOOR 2 ──
  { id: 'W2-IND', name: 'Industry Partnership R&D Lab', shortName: 'R&D', wing: 'west', floor: 2, type: 'lab', area: 200, description: 'Collaborative R&D space for industry partners, prototyping and applied research projects' },
  { id: 'W2-DAT', name: 'Data Science & IIoT Lab', shortName: 'DAT', wing: 'west', floor: 2, type: 'lab', area: 175, description: 'Industrial IoT sensor integration, data pipelines, MQTT brokers and edge analytics' },
  { id: 'W2-OFF', name: 'Faculty & Research Offices', shortName: 'OFF', wing: 'west', floor: 2, type: 'office', area: 130, description: 'Faculty offices, research coordinator workspaces and advising rooms' },
  { id: 'W2-CONF', name: 'Conference & Collaboration Room', shortName: 'CONF', wing: 'west', floor: 2, type: 'conference', area: 115, description: 'Meeting room with video conferencing, whiteboard walls and presentation displays' },

  // ── NORTH WING FLOOR 1 ──
  { id: 'N1-SUB3', name: 'Subtractive Mfg Lab (Makino / Welding) — Annex', shortName: 'SUBX', wing: 'north', floor: 1, type: 'lab', area: 195, description: 'Annex extension of Room 1067 · Overflow welding bays and secondary Makino CNC stations' },
  { id: 'N1-CTRL', name: 'Control Systems Lab', shortName: 'CTL', wing: 'north', floor: 1, type: 'lab', area: 170, description: 'PLC programming, SCADA systems, HMI panels and industrial control networks' },
  { id: 'N1-CORR', name: 'Main Corridor / Lobby', shortName: 'LBY', wing: 'north', floor: 1, type: 'corridor', area: 110, description: 'Main entrance lobby, reception and connecting corridor between wings' },
  { id: 'N1-MECH', name: 'Mechanical Systems Room', shortName: 'MECH', wing: 'north', floor: 1, type: 'utility', area: 75, description: 'Compressed air, coolant distribution, ventilation and mechanical building services' },

  // ── NORTH WING FLOOR 2 ──
  { id: 'N2-PROJ2', name: 'Projects Lab Overflow / Open Studio', shortName: 'STD', wing: 'north', floor: 2, type: 'lab', area: 165, description: 'Open studio for student capstone projects, maker space and collaborative build area' },
  { id: 'N2-EDGE', name: 'Edge Computing & Sensor Lab', shortName: 'EDGE', wing: 'north', floor: 2, type: 'lab', area: 150, description: 'Edge AI nodes, fog computing, industrial sensor R&D and real-time signal processing' },
  { id: 'N2-COLLAB', name: 'Innovation & Collaboration Hub', shortName: 'HUB', wing: 'north', floor: 2, type: 'office', area: 135, description: 'Open collaboration space, innovation sprints, team workstations and ideation zone' },
  { id: 'N2-UTIL', name: 'Utility Room', shortName: 'UTL2', wing: 'north', floor: 2, type: 'utility', area: 60, description: 'Second-floor HVAC, electrical sub-panels and network distribution' },
];

// ---- Build initial zones with simulated data ----
function buildZones(): Zone[] {
  return zoneDefinitions.map(def => {
    // Inject variety: basement machining labs run high energy; welding lab has elevated AQI/fumes
    const isBasement = def.floor === 0;
    const isWelding = def.id === 'B0-WLD';
    const isMachining = def.id === 'B0-MAK' || def.id === 'B0-INT';
    const tempOverride = def.type === 'server' ? rand(22, 28) : isBasement ? rand(21, 26) : def.type === 'lab' ? rand(20, 25) : rand(19, 23);
    const energyOverride = def.type === 'server' ? rand(30, 60) : isMachining ? rand(45, 90) : isWelding ? rand(20, 40) : def.type === 'lab' ? rand(10, 30) : rand(3, 12);
    const co2Override = def.type === 'corridor' ? rand(400, 600, 0) : rand(450, 900, 0);

    const sensors = makeSensors({
      temperature: tempOverride,
      energyKw: energyOverride,
      co2: co2Override,
      airQuality: isWelding ? rand(60, 130, 0) : isMachining ? rand(30, 70, 0) : rand(20, 80, 0),
      equipmentTotal: isMachining ? 20 : def.type === 'server' ? 24 : def.type === 'lab' ? 15 : 8,
      equipmentOnline: isMachining ? rand(10, 18, 0) : rand(6, 15, 0),
    });

    const status = computeStatus(sensors);

    const alerts: Alert[] = [];
    if (status === 'warn' || status === 'critical') {
      if (sensors.temperature > 26) {
        alerts.push({
          id: `${def.id}-temp`,
          zoneId: def.id,
          zoneName: def.name,
          type: 'temperature',
          severity: sensors.temperature > 30 ? 'critical' : 'warn',
          message: `Temperature elevated: ${sensors.temperature}°C`,
          timestamp: Date.now() - rand(0, 600000, 0),
        });
      }
      if (sensors.co2 > 900) {
        alerts.push({
          id: `${def.id}-co2`,
          zoneId: def.id,
          zoneName: def.name,
          type: 'co2',
          severity: sensors.co2 > 1200 ? 'critical' : 'warn',
          message: `CO₂ level high: ${sensors.co2} ppm`,
          timestamp: Date.now() - rand(0, 300000, 0),
        });
      }
    }

    return {
      ...def,
      status,
      sensors,
      history: generateHistory(tempOverride, energyOverride),
      alerts,
    };
  });
}

// ---- Singleton store with live simulation ----
let zones: Zone[] = buildZones();
let listeners: (() => void)[] = [];
let simTimer: ReturnType<typeof setInterval> | null = null;

function notifyListeners() {
  listeners.forEach(fn => fn());
}

function tickZones() {
  zones = zones.map(zone => {
    if (zone.status === 'offline') return zone;

    const drift = (v: number, range: number, decimals = 1) =>
      parseFloat(Math.max(0, v + (Math.random() - 0.5) * range).toFixed(decimals));

    const newSensors: SensorData = {
      ...zone.sensors,
      temperature: drift(zone.sensors.temperature, 0.4),
      humidity: Math.min(100, Math.max(20, drift(zone.sensors.humidity, 1))),
      co2: Math.max(350, drift(zone.sensors.co2, 30, 0)),
      energyKw: Math.max(0.5, drift(zone.sensors.energyKw, 1.5)),
      occupancy: Math.max(0, Math.round(zone.sensors.occupancy + (Math.random() - 0.5) * 2)),
      networkLoad: Math.min(100, Math.max(0, drift(zone.sensors.networkLoad, 3))),
      airQuality: Math.max(0, drift(zone.sensors.airQuality, 5, 0)),
    };

    const newHistory = [
      ...zone.history.slice(-19),
      {
        timestamp: Date.now(),
        temperature: newSensors.temperature,
        humidity: newSensors.humidity,
        energyKw: newSensors.energyKw,
        co2: newSensors.co2,
      },
    ];

    const newStatus = computeStatus(newSensors);

    return { ...zone, sensors: newSensors, history: newHistory, status: newStatus };
  });
  notifyListeners();
}

export function subscribeToZones(fn: () => void): () => void {
  listeners.push(fn);
  if (listeners.length === 1) {
    simTimer = setInterval(tickZones, 3000);
  }
  return () => {
    listeners = listeners.filter(l => l !== fn);
    if (listeners.length === 0 && simTimer !== null) {
      clearInterval(simTimer);
      simTimer = null;
    }
  };
}

export function getZones(): Zone[] {
  return zones;
}

// ---- Utility functions ----
export function getZonesByWingAndFloor(wing: Wing, floor: Floor): Zone[] {
  return zones.filter(z => z.wing === wing && z.floor === floor);
}

export function getZoneById(id: string): Zone | undefined {
  return zones.find(z => z.id === id);
}

export function getAllAlerts(): Alert[] {
  return zones.flatMap(z => z.alerts).sort((a, b) => b.timestamp - a.timestamp);
}

export function getBuildingSummary() {
  const total = zones.length;
  const ok = zones.filter(z => z.status === 'ok').length;
  const warn = zones.filter(z => z.status === 'warn').length;
  const critical = zones.filter(z => z.status === 'critical').length;
  const offline = zones.filter(z => z.status === 'offline').length;
  const totalEnergy = zones.reduce((sum, z) => sum + z.sensors.energyKw, 0);
  const totalOccupancy = zones.reduce((sum, z) => sum + z.sensors.occupancy, 0);
  const avgTemp = zones.reduce((sum, z) => sum + z.sensors.temperature, 0) / total;
  return { total, ok, warn, critical, offline, totalEnergy, totalOccupancy, avgTemp };
}

export const WING_LABELS: Record<Wing, string> = {
  east: 'East Wing',
  west: 'West Wing',
  north: 'North Wing',
};

export const FLOOR_LABELS: Record<Floor, string> = {
  0: 'Basement',
  1: 'Floor 1',
  2: 'Floor 2',
};

export const FLOOR_SHORT: Record<Floor, string> = {
  0: 'B',
  1: 'FL 1',
  2: 'FL 2',
};

export const ZONE_TYPE_COLORS: Record<string, string> = {
  lab: 'oklch(0.65 0.18 220 / 20%)',
  server: 'oklch(0.65 0.18 280 / 20%)',
  office: 'oklch(0.65 0.18 155 / 15%)',
  conference: 'oklch(0.72 0.18 85 / 15%)',
  corridor: 'oklch(1 0 0 / 5%)',
  utility: 'oklch(0.45 0.01 240 / 20%)',
};

export const STATUS_COLORS: Record<ZoneStatus, string> = {
  ok: '#22c55e',
  warn: '#f59e0b',
  critical: '#ef4444',
  offline: '#64748b',
};

export const STATUS_LABELS: Record<ZoneStatus, string> = {
  ok: 'OPERATIONAL',
  warn: 'WARNING',
  critical: 'CRITICAL',
  offline: 'OFFLINE',
};
