import { describe, expect, it } from 'vitest';
import {
  CAMERA_MARKERS,
  FLOOR_PLAN_VIEWBOX,
  FLOORS,
  floorSummary,
  machinesForFloor,
  machinesForRoom,
  PLACEMENTS,
  ROOM_SCHEMATIC_WALL,
  ROOMS,
  roomsForFloor,
  summaryLine,
} from '../src/lib/buildingLayout';
import { HAAS_DEFAULTS, MAKINO_A51NX_DEFAULTS } from '../src/types/equipment';

describe('data integrity', () => {
  const roomIds = new Set(ROOMS.map(r => r.id));
  const floorIds = new Set(FLOORS.map(f => f.id));

  it('every placement points at an existing room', () => {
    for (const p of PLACEMENTS) {
      expect(roomIds.has(p.roomId), `placement ${p.storeKey} → ${p.roomId}`).toBe(true);
    }
  });

  it('every camera marker points at an existing room', () => {
    for (const c of CAMERA_MARKERS) {
      expect(roomIds.has(c.roomId), `camera ${c.label} → ${c.roomId}`).toBe(true);
    }
  });

  it('every room belongs to an existing floor', () => {
    for (const r of ROOMS) {
      expect(floorIds.has(r.floorId), `room ${r.id} → ${r.floorId}`).toBe(true);
    }
  });

  it('room ids and store keys are unique', () => {
    expect(roomIds.size).toBe(ROOMS.length);
    expect(new Set(PLACEMENTS.map(p => p.storeKey)).size).toBe(PLACEMENTS.length);
  });
});

describe('geometry bounds', () => {
  it('every room rect fits inside the floor plan viewbox', () => {
    for (const r of ROOMS) {
      expect(r.rect.x, `room ${r.id}`).toBeGreaterThanOrEqual(0);
      expect(r.rect.y, `room ${r.id}`).toBeGreaterThanOrEqual(0);
      expect(r.rect.x + r.rect.w, `room ${r.id}`).toBeLessThanOrEqual(FLOOR_PLAN_VIEWBOX.w);
      expect(r.rect.y + r.rect.h, `room ${r.id}`).toBeLessThanOrEqual(FLOOR_PLAN_VIEWBOX.h);
    }
  });

  it('every machine rect fits inside the room schematic wall', () => {
    const wall = ROOM_SCHEMATIC_WALL;
    for (const p of PLACEMENTS) {
      expect(p.rect.x, `machine ${p.storeKey}`).toBeGreaterThanOrEqual(wall.x);
      expect(p.rect.y, `machine ${p.storeKey}`).toBeGreaterThanOrEqual(wall.y);
      expect(p.rect.x + p.rect.w, `machine ${p.storeKey}`).toBeLessThanOrEqual(wall.x + wall.w);
      expect(p.rect.y + p.rect.h, `machine ${p.storeKey}`).toBeLessThanOrEqual(wall.y + wall.h);
    }
  });

  it('every camera marker sits inside the room schematic wall', () => {
    const wall = ROOM_SCHEMATIC_WALL;
    for (const c of CAMERA_MARKERS) {
      expect(c.x, `camera ${c.label}`).toBeGreaterThanOrEqual(wall.x);
      expect(c.x, `camera ${c.label}`).toBeLessThanOrEqual(wall.x + wall.w);
      expect(c.y, `camera ${c.label}`).toBeGreaterThanOrEqual(wall.y);
      expect(c.y, `camera ${c.label}`).toBeLessThanOrEqual(wall.y + wall.h);
    }
  });

  it('rooms on the same floor do not overlap', () => {
    for (const floor of FLOORS) {
      const rooms = roomsForFloor(floor.id);
      for (let i = 0; i < rooms.length; i++) {
        for (let j = i + 1; j < rooms.length; j++) {
          const a = rooms[i].rect;
          const b = rooms[j].rect;
          const separated =
            a.x + a.w <= b.x || b.x + b.w <= a.x ||
            a.y + a.h <= b.y || b.y + b.h <= a.y;
          expect(separated, `${rooms[i].id} overlaps ${rooms[j].id}`).toBe(true);
        }
      }
    }
  });
});

describe('queries', () => {
  it('all five machines are in the basement', () => {
    expect(machinesForFloor('basement')).toHaveLength(5);
    expect(machinesForFloor('floor1')).toHaveLength(0);
    expect(machinesForFloor('floor2')).toHaveLength(0);
  });

  it('all five machines are in the Makino Lab', () => {
    expect(machinesForRoom('b0-mak')).toHaveLength(5);
  });
});

describe('floorSummary', () => {
  it('counts statuses and sums power', () => {
    const machines = [
      { ...HAAS_DEFAULTS, status: 'running' as const, powerKw: 3.2 },
      { ...MAKINO_A51NX_DEFAULTS, status: 'running' as const, powerKw: 5.1 },
      { ...MAKINO_A51NX_DEFAULTS, status: 'alarm' as const, powerKw: 0.5 },
    ];
    const s = floorSummary(machines);
    expect(s.total).toBe(3);
    expect(s.byStatus.running).toBe(2);
    expect(s.byStatus.alarm).toBe(1);
    expect(s.byStatus.idle).toBe(0);
    expect(s.totalPowerKw).toBeCloseTo(8.8);
  });
});

describe('summaryLine', () => {
  it('reports no equipment for an empty floor', () => {
    expect(summaryLine(floorSummary([]))).toBe('NO CONNECTED EQUIPMENT');
  });

  it('lists each non-zero status and the total power', () => {
    const line = summaryLine(floorSummary([
      { ...HAAS_DEFAULTS, status: 'running' as const, powerKw: 3.25 },
      { ...MAKINO_A51NX_DEFAULTS, status: 'offline' as const, powerKw: 0 },
    ]));
    expect(line).toBe('2 MACHINES · 1 RUNNING · 1 OFFLINE · 3.3 KW');
  });
});
