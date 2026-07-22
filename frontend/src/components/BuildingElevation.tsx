import React from 'react';
import { FLOORS, floorSummary, machinesForFloor } from '../lib/buildingLayout';
import type { FloorId } from '../lib/buildingLayout';
import { isActivateKey } from '../lib/keys';
import { useEquipmentStore } from '../stores/equipmentStore';

// 30° isometric projection of the T-shaped footprint, in world units scaled
// into the viewBox. Only this component draws the elevation, so the math
// stays module-local.
const COS30 = Math.cos(Math.PI / 6);
const SCALE = 4.2;
const TX = 175;
const TY = 110;
const FLOOR_H = 12;
const BASEMENT_H = 10;

const FOOTPRINT: [number, number][] = [
  [0, 0], [60, 0], [60, 37.5], [35, 37.5],
  [35, 67.5], [21, 67.5], [21, 37.5], [0, 37.5],
];

// Only walls facing the viewer (+x and +y faces) are drawn.
const VISIBLE_WALL_EDGES: [number, number, number, number][] = [
  [0, 37.5, 21, 37.5],
  [35, 37.5, 60, 37.5],
  [21, 67.5, 35, 67.5],
  [60, 0, 60, 37.5],
  [35, 37.5, 35, 67.5],
];

function project(x: number, y: number, z: number): [number, number] {
  return [(x - y) * COS30 * SCALE + TX, ((x + y) * 0.5 - z) * SCALE + TY];
}

function toPoints(coords: [number, number][]): string {
  return coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
}

function wallQuad(edge: [number, number, number, number], zBottom: number, zTop: number): string {
  const [x1, y1, x2, y2] = edge;
  return toPoints([
    project(x1, y1, zBottom),
    project(x2, y2, zBottom),
    project(x2, y2, zTop),
    project(x1, y1, zTop),
  ]);
}

function slabZ(index: number): { zBottom: number; zTop: number } {
  if (index === 0) return { zBottom: -BASEMENT_H, zTop: 0 };
  return { zBottom: (index - 1) * FLOOR_H, zTop: index * FLOOR_H };
}

interface BuildingElevationProps {
  onSelectFloor: (floorId: FloorId) => void;
}

export const BuildingElevation: React.FC<BuildingElevationProps> = ({ onSelectFloor }) => {
  const store = useEquipmentStore();

  return (
    <svg className="map-svg" viewBox="0 0 560 400" aria-label="Building elevation — select a floor">
      {FLOORS.map((floor, i) => {
        const { zBottom, zTop } = slabZ(i);
        const summary = floorSummary(machinesForFloor(floor.id).map(p => store[p.storeKey]));
        const metrics = summary.total === 0
          ? 'NO CONNECTED EQUIPMENT'
          : `${summary.total} MACHINES · ${summary.totalPowerKw.toFixed(1)} KW`;
        const alarms = summary.byStatus.alarm;
        const [labelX, labelY] = project(62, 0, (zBottom + zTop) / 2);
        const activate = () => onSelectFloor(floor.id);

        return (
          <g
            key={floor.id}
            className={`iso-slab ${i === 0 ? 'iso-slab-below-grade' : ''}`}
            role="button"
            tabIndex={0}
            aria-label={`${floor.label} — ${metrics}${alarms > 0 ? ` — ${alarms} in alarm` : ''}`}
            onClick={activate}
            onKeyDown={e => {
              if (isActivateKey(e)) {
                e.preventDefault();
                activate();
              }
            }}
          >
            {VISIBLE_WALL_EDGES.map((edge, w) => (
              <polygon key={w} className="iso-face iso-wall" points={wallQuad(edge, zBottom, zTop)} />
            ))}
            <polygon
              className="iso-face iso-top"
              points={toPoints(FOOTPRINT.map(([x, y]) => project(x, y, zTop)))}
            />
            <text className="iso-floor-label" x={labelX} y={labelY - 4}>{floor.label}</text>
            <text className="iso-floor-metrics" x={labelX} y={labelY + 10}>{metrics}</text>
            {alarms > 0 && (
              <text className="iso-floor-alarm live-indicator" x={labelX} y={labelY + 24}>
                {alarms} IN ALARM
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
};
