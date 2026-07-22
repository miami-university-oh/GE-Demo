import type { MachineData, MachineStatus } from '../types/equipment';

// Static physical layout of the building. The backend has no notion of
// location, so floors, rooms, and machine placement live here.

export type FloorId = 'basement' | 'floor1' | 'floor2';

export interface Floor {
  id: FloorId;
  label: string;
}

// Ordered bottom-up: the elevation stacks slabs in this order, and the list
// view lists the basement (the only floor with machines) first.
export const FLOORS: Floor[] = [
  { id: 'basement', label: 'BASEMENT' },
  { id: 'floor1', label: 'FLOOR 1' },
  { id: 'floor2', label: 'FLOOR 2' },
];

export function floorById(floorId: FloorId): Floor {
  return FLOORS.find(f => f.id === floorId) ?? FLOORS[0];
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const FLOOR_PLAN_VIEWBOX = { w: 560, h: 600 };

// T-shaped footprint as three wing blocks: east, north spine, west.
export const FLOOR_WINGS: Rect[] = [
  { x: 20, y: 20, w: 168, h: 300 },
  { x: 218, y: 20, w: 110, h: 560 },
  { x: 338, y: 20, w: 192, h: 300 },
];

export interface Room {
  id: string;
  floorId: FloorId;
  label: string;
  roomNumber?: string;
  rect: Rect;
}

// Floors 1 and 2 share one physical room grid; only the labels differ.
const UPPER_ROOM_RECTS: Rect[] = [
  { x: 26, y: 34, w: 75, h: 137 },
  { x: 107, y: 34, w: 75, h: 137 },
  { x: 26, y: 177, w: 75, h: 137 },
  { x: 107, y: 177, w: 75, h: 137 },
  { x: 224, y: 34, w: 98, h: 130 },
  { x: 224, y: 170, w: 98, h: 130 },
  { x: 224, y: 306, w: 98, h: 130 },
  { x: 224, y: 442, w: 98, h: 130 },
  { x: 344, y: 34, w: 87, h: 137 },
  { x: 437, y: 34, w: 87, h: 137 },
  { x: 344, y: 177, w: 87, h: 137 },
  { x: 437, y: 177, w: 87, h: 137 },
];

const FLOOR1_LABELS = [
  'ROBOTICS', 'CNC', 'ELECTRONICS', 'STORAGE',
  'FABRICATION', 'TESTING', 'CONTROL', 'CORRIDOR',
  'NETWORK', 'IIOT', 'SERVER', 'CALIBRATION',
];

const FLOOR2_LABELS = [
  'AI LAB', 'VR LAB', 'OFFICE', 'CONFERENCE',
  'SENSOR', 'EDGE', 'COLLAB', 'UTILITY',
  'CYBER', 'DATA SCI', 'ADMIN', 'BOARDROOM',
];

function upperFloorRooms(floorId: FloorId, prefix: string, labels: string[]): Room[] {
  return UPPER_ROOM_RECTS.map((rect, i) => ({
    id: `${prefix}-${i + 1}`,
    floorId,
    label: labels[i],
    rect,
  }));
}

export const ROOMS: Room[] = [
  {
    id: 'b0-mak', floorId: 'basement', label: 'MAKINO LAB', roomNumber: '1067',
    rect: { x: 26, y: 34, w: 142, h: 264 },
  },
  {
    id: 'b0-wld', floorId: 'basement', label: 'WELDING LAB',
    rect: { x: 224, y: 34, w: 98, h: 124 },
  },
  {
    id: 'b0-wldx', floorId: 'basement', label: 'WELDING ANNEX',
    rect: { x: 224, y: 170, w: 98, h: 124 },
  },
  {
    id: 'b0-int', floorId: 'basement', label: 'INTEGRATED INDUSTRY LAB', roomNumber: '1059',
    rect: { x: 344, y: 34, w: 180, h: 264 },
  },
  ...upperFloorRooms('floor1', 'f1', FLOOR1_LABELS),
  ...upperFloorRooms('floor2', 'f2', FLOOR2_LABELS),
];

export function roomsForFloor(floorId: FloorId): Room[] {
  return ROOMS.filter(r => r.floorId === floorId);
}

export function roomById(roomId: string): Room | undefined {
  return ROOMS.find(r => r.id === roomId);
}

// Keys into useEquipmentStore for machines that physically exist in the lab.
export type StoreMachineKey = 'haas' | 'ur5e' | 'makinoA51nx' | 'makinoD200Z' | 'makinoPS95';

export const ROOM_SCHEMATIC_VIEWBOX = { w: 480, h: 200 };
export const ROOM_SCHEMATIC_WALL: Rect = { x: 10, y: 10, w: 460, h: 180 };

export interface MachinePlacement {
  storeKey: StoreMachineKey;
  title: string;
  shortLabel: string;
  kind: string;
  roomId: string;
  rect: Rect;
}

export const PLACEMENTS: MachinePlacement[] = [
  {
    storeKey: 'haas', title: 'HAAS TL-1', shortLabel: 'HAAS TL-1', kind: 'LATHE',
    roomId: 'b0-mak', rect: { x: 18, y: 55, w: 85, h: 62 },
  },
  {
    storeKey: 'ur5e', title: 'UR5E COBOT', shortLabel: 'UR5E', kind: 'COBOT',
    roomId: 'b0-mak', rect: { x: 120, y: 55, w: 60, h: 60 },
  },
  {
    storeKey: 'makinoA51nx', title: 'MAKINO A51NX', shortLabel: 'A51NX', kind: 'HMC',
    roomId: 'b0-mak', rect: { x: 198, y: 50, w: 80, h: 68 },
  },
  {
    storeKey: 'makinoD200Z', title: 'MAKINO D200Z', shortLabel: 'D200Z', kind: '5-AXIS',
    roomId: 'b0-mak', rect: { x: 296, y: 50, w: 80, h: 68 },
  },
  {
    storeKey: 'makinoPS95', title: 'MAKINO PS95', shortLabel: 'PS95', kind: 'VMC',
    roomId: 'b0-mak', rect: { x: 394, y: 50, w: 70, h: 68 },
  },
];

export interface CameraMarker {
  label: string;
  roomId: string;
  x: number;
  y: number;
}

export const CAMERA_MARKERS: CameraMarker[] = [
  { label: 'CAM-01', roomId: 'b0-mak', x: 158, y: 22 },
  { label: 'CAM-02', roomId: 'b0-mak', x: 340, y: 22 },
];

export function machinesForRoom(roomId: string): MachinePlacement[] {
  return PLACEMENTS.filter(p => p.roomId === roomId);
}

export function machinesForFloor(floorId: FloorId): MachinePlacement[] {
  const roomIds = new Set(roomsForFloor(floorId).map(r => r.id));
  return PLACEMENTS.filter(p => roomIds.has(p.roomId));
}

export function camerasForRoom(roomId: string): CameraMarker[] {
  return CAMERA_MARKERS.filter(c => c.roomId === roomId);
}

export interface FloorSummary {
  total: number;
  byStatus: Record<MachineStatus, number>;
  totalPowerKw: number;
}

export function floorSummary(machines: MachineData[]): FloorSummary {
  const byStatus: Record<MachineStatus, number> = { running: 0, idle: 0, alarm: 0, offline: 0 };
  let totalPowerKw = 0;
  for (const m of machines) {
    byStatus[m.status] += 1;
    totalPowerKw += m.powerKw;
  }
  return { total: machines.length, byStatus, totalPowerKw };
}

const STATUS_ORDER: MachineStatus[] = ['running', 'idle', 'alarm', 'offline'];

export function summaryLine(s: FloorSummary): string {
  if (s.total === 0) return 'NO CONNECTED EQUIPMENT';
  const counts = STATUS_ORDER
    .filter(status => s.byStatus[status] > 0)
    .map(status => `${s.byStatus[status]} ${status.toUpperCase()}`);
  return [`${s.total} MACHINES`, ...counts, `${s.totalPowerKw.toFixed(1)} KW`].join(' · ');
}
