export type MachineStatus = 'running' | 'idle' | 'alarm' | 'offline';

export interface HaasData {
  machine: 'haas-tl1';
  status: MachineStatus;
  program: string;
  spindleRpm: number;
  spindleLoad: number;
  feedRate: number;
  position: { x: number; z: number };
  toolNumber: number;
  cycleTime: number;
  partCount: number;
  powerKw: number;
  coolant: boolean;
  alarms: string[];
}

export interface CobotJoint {
  id: string;
  label: string;
  angle: number;
  speed: number;
  torque: number;
}

export interface UR5eData {
  machine: 'ur5e';
  status: MachineStatus;
  program: string;
  robotMode: string;
  safetyMode: string;
  tcpPosition: { x: number; y: number; z: number; rx: number; ry: number; rz: number };
  tcpSpeed: number;
  speedFraction: number;
  joints: CobotJoint[];
  powerKw: number;
  voltage: number;
  current: number;
  alarms: string[];
  digitalOutputs: number;
}

export interface MakinoData {
  machine: 'makino-a51nx' | 'makino-d200z' | 'makino-ps95';
  status: MachineStatus;
  program: string;
  spindleRpm: number;
  spindleLoad: number;
  feedRate: number;
  position: { x: number; y: number; z: number };
  toolNumber: number;
  cycleTime: number;
  partCount: number;
  powerKw: number;
  alarms: string[];
}

export type MachineData = HaasData | UR5eData | MakinoData;

const DEFAULT_JOINTS: CobotJoint[] = [
  { id: 'J1', label: 'Base', angle: 0, speed: 0, torque: 0 },
  { id: 'J2', label: 'Shoulder', angle: 0, speed: 0, torque: 0 },
  { id: 'J3', label: 'Elbow', angle: 0, speed: 0, torque: 0 },
  { id: 'J4', label: 'Wrist 1', angle: 0, speed: 0, torque: 0 },
  { id: 'J5', label: 'Wrist 2', angle: 0, speed: 0, torque: 0 },
  { id: 'J6', label: 'Wrist 3', angle: 0, speed: 0, torque: 0 },
];

export const HAAS_DEFAULTS: HaasData = {
  machine: 'haas-tl1', status: 'offline', program: '—',
  spindleRpm: 0, spindleLoad: 0, feedRate: 0,
  position: { x: 0, z: 0 }, toolNumber: 0, cycleTime: 0,
  partCount: 0, powerKw: 0, coolant: false, alarms: [],
};

export const UR5E_DEFAULTS: UR5eData = {
  machine: 'ur5e', status: 'offline', program: '—',
  robotMode: 'DISCONNECTED', safetyMode: 'NORMAL',
  tcpPosition: { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 },
  tcpSpeed: 0, speedFraction: 0, joints: DEFAULT_JOINTS,
  powerKw: 0, voltage: 0, current: 0, alarms: [], digitalOutputs: 0,
};

export const MAKINO_A51NX_DEFAULTS: MakinoData = {
  machine: 'makino-a51nx', status: 'offline', program: '—',
  spindleRpm: 0, spindleLoad: 0, feedRate: 0,
  position: { x: 0, y: 0, z: 0 }, toolNumber: 0,
  cycleTime: 0, partCount: 0, powerKw: 0, alarms: [],
};

export const MAKINO_D200Z_DEFAULTS: MakinoData = {
  machine: 'makino-d200z', status: 'offline', program: '—',
  spindleRpm: 0, spindleLoad: 0, feedRate: 0,
  position: { x: 0, y: 0, z: 0 }, toolNumber: 0,
  cycleTime: 0, partCount: 0, powerKw: 0, alarms: [],
};

export const MAKINO_PS95_DEFAULTS: MakinoData = {
  machine: 'makino-ps95', status: 'offline', program: '—',
  spindleRpm: 0, spindleLoad: 0, feedRate: 0,
  position: { x: 0, y: 0, z: 0 }, toolNumber: 0,
  cycleTime: 0, partCount: 0, powerKw: 0, alarms: [],
};
