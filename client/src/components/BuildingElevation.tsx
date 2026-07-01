/* ============================================================
   BuildingElevation.tsx — Isometric 3D Building Overview
   V3.1: Shows Basement + Floor 1 + Floor 2 as stacked isometric slabs.
   Basement is rendered below ground level with a distinct dark tint.
   Clicking a floor triggers zoom-in to detailed floor plan.
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import React, { useState } from 'react';
import type { Floor, Wing, Zone, ZoneStatus } from '@/lib/buildingData';
import { STATUS_COLORS } from '@/lib/buildingData';

interface BuildingElevationProps {
  zones: Zone[];
  onSelectFloor: (floor: Floor) => void;
}

// ── Isometric projection helpers ──
const ISO_COS = Math.cos(Math.PI / 6);
const ISO_SIN = Math.sin(Math.PI / 6);

/**
 * Projects world-space coordinates (x, y, z) into a 2D isometric screen
 * position using a standard 30° cabinet-projection. The x and y axes are
 * flattened by ISO_COS / ISO_SIN; z is subtracted to lift points vertically.
 *
 * @param x - World x coordinate.
 * @param y - World y coordinate.
 * @param z - World z coordinate (positive = up).
 * @returns `[screenX, screenY]` tuple in isometric screen space.
 */
function iso(x: number, y: number, z: number): [number, number] {
  return [
    (x - y) * ISO_COS,
    (x + y) * ISO_SIN - z,
  ];
}

// ── T-shape footprint in world coords ──
// East block:  x 0→21, y 0→37.5
// North spine: x 21→35, y 0→67.5
// West block:  x 35→60, y 0→37.5
// Floor height: 12 units, Basement height: 10 units

const SCALE = 8;
const FLOOR_H = 12;       // world units per above-ground floor
const BASEMENT_H = 10;    // world units for basement
const WALL_THICKNESS = 0.5;

// Z levels: basement bottom = -BASEMENT_H, basement top = 0, floor1 top = FLOOR_H, floor2 top = 2*FLOOR_H
/**
 * Returns the world-space z coordinate of the bottom face of a floor slab.
 * Basement bottom is at `-BASEMENT_H`; floor 1 base is at `0`; floor 2 base at `FLOOR_H`.
 *
 * @param floor - Floor level (0 = Basement, 1 = Floor 1, 2 = Floor 2).
 */
function floorZBottom(floor: Floor): number {
  if (floor === 0) return -BASEMENT_H;
  if (floor === 1) return 0;
  return FLOOR_H;
}
/**
 * Returns the world-space z coordinate of the top face of a floor slab.
 * Basement top is at `0` (ground level); floor 1 top at `FLOOR_H`; floor 2 top at `2 * FLOOR_H`.
 *
 * @param floor - Floor level.
 */
function floorZTop(floor: Floor): number {
  if (floor === 0) return 0;
  if (floor === 1) return FLOOR_H;
  return FLOOR_H * 2;
}

const T_FOOTPRINT: [number, number][] = [
  [0, 0],
  [60, 0],
  [60, 37.5],
  [35, 37.5],
  [35, 67.5],
  [21, 67.5],
  [21, 37.5],
  [0, 37.5],
];

// Basement footprint: only East + West wings (no North spine — it's above ground)
// Basement spans the full T width but is shown as a slightly inset slab
const BASEMENT_FOOTPRINT: [number, number][] = [
  [0, 0],
  [60, 0],
  [60, 37.5],
  [35, 37.5],
  [35, 67.5],
  [21, 67.5],
  [21, 37.5],
  [0, 37.5],
];

const WING_REGIONS: { wing: Wing; x: number; y: number; w: number; h: number }[] = [
  { wing: 'east',  x: 0,  y: 0, w: 21,  h: 37.5 },
  { wing: 'north', x: 21, y: 0, w: 14,  h: 67.5 },
  { wing: 'west',  x: 35, y: 0, w: 25,  h: 37.5 },
];

const WING_COLORS: Record<Wing, { top: string; front: string; side: string }> = {
  east: {
    top:   'rgba(34,197,94,0.18)',
    front: 'rgba(34,197,94,0.10)',
    side:  'rgba(34,197,94,0.07)',
  },
  north: {
    top:   'rgba(239,68,68,0.16)',
    front: 'rgba(239,68,68,0.09)',
    side:  'rgba(239,68,68,0.06)',
  },
  west: {
    top:   'rgba(59,130,246,0.18)',
    front: 'rgba(59,130,246,0.10)',
    side:  'rgba(59,130,246,0.07)',
  },
};

// Basement gets a distinct amber/orange tint to signal underground
const BASEMENT_WING_COLORS: Record<Wing, string> = {
  east:  'rgba(251,146,60,0.20)',
  north: 'rgba(251,146,60,0.14)',
  west:  'rgba(251,146,60,0.18)',
};

const WING_STROKE: Record<Wing, string> = {
  east:  'rgba(34,197,94,0.55)',
  north: 'rgba(239,68,68,0.50)',
  west:  'rgba(96,165,250,0.55)',
};

const WING_LABEL: Record<Wing, string> = {
  east:  '#22c55e',
  north: '#ef4444',
  west:  '#60a5fa',
};

/**
 * Converts a world-space point to SVG screen coordinates by scaling by
 * `SCALE`, applying the isometric projection, then offsetting by the
 * canvas center (cx, cy).
 *
 * @param wx - World x.
 * @param wy - World y.
 * @param wz - World z.
 * @param cx - Canvas center x offset.
 * @param cy - Canvas center y offset.
 * @returns `[svgX, svgY]` ready to use in an SVG element.
 */
function projectPoint(wx: number, wy: number, wz: number, cx: number, cy: number): [number, number] {
  const [ix, iy] = iso(wx * SCALE, wy * SCALE, wz * SCALE);
  return [cx + ix, cy + iy];
}

/**
 * Builds an SVG `points` string for a horizontal polygon (floor/ceiling slab
 * face) at a constant world z level by projecting each world (x, y) vertex.
 *
 * @param pts - Array of (world x, world y) vertices forming the polygon.
 * @param z   - World z level for all vertices (constant horizontal face).
 * @param cx  - Canvas center x offset.
 * @param cy  - Canvas center y offset.
 * @returns Space-separated `"x,y"` pairs suitable for an SVG `<polygon points>`.
 */
function floorPolygon(pts: [number, number][], z: number, cx: number, cy: number): string {
  return pts.map(([x, y]) => projectPoint(x, y, z, cx, cy).join(',')).join(' ');
}

/**
 * Builds an SVG `points` string for a vertical wall quad between two world
 * (x, y) points running from `zBottom` to `zTop`. Returns four projected
 * corners: bottom-left, bottom-right, top-right, top-left.
 *
 * @param x1      - World x of the first wall edge.
 * @param y1      - World y of the first wall edge.
 * @param x2      - World x of the second wall edge.
 * @param y2      - World y of the second wall edge.
 * @param zBottom - World z of the base of the wall.
 * @param zTop    - World z of the top of the wall.
 * @param cx      - Canvas center x offset.
 * @param cy      - Canvas center y offset.
 * @returns Space-separated `"x,y"` pairs for an SVG `<polygon>`.
 */
function vertFace(
  x1: number, y1: number,
  x2: number, y2: number,
  zBottom: number, zTop: number,
  cx: number, cy: number
): string {
  const [ax, ay] = projectPoint(x1, y1, zBottom, cx, cy);
  const [bx, by] = projectPoint(x2, y2, zBottom, cx, cy);
  const [cx2, cy2] = projectPoint(x2, y2, zTop, cx, cy);
  const [dx, dy] = projectPoint(x1, y1, zTop, cx, cy);
  return `${ax},${ay} ${bx},${by} ${cx2},${cy2} ${dx},${dy}`;
}

const VISIBLE_EDGES: { x1: number; y1: number; x2: number; y2: number }[] = [
  { x1: 0, y1: 37.5, x2: 21, y2: 37.5 },
  { x1: 35, y1: 37.5, x2: 60, y2: 37.5 },
  { x1: 60, y1: 0, x2: 60, y2: 37.5 },
  { x1: 21, y1: 67.5, x2: 35, y2: 67.5 },
  { x1: 35, y1: 37.5, x2: 35, y2: 67.5 },
  { x1: 0, y1: 0, x2: 0, y2: 37.5 },
];

const WINDOWS: { x1: number; y1: number; x2: number; y2: number; count: number }[] = [
  { x1: 0, y1: 37.5, x2: 21, y2: 37.5, count: 5 },
  { x1: 35, y1: 37.5, x2: 60, y2: 37.5, count: 6 },
  { x1: 60, y1: 0, x2: 60, y2: 37.5, count: 4 },
  { x1: 21, y1: 67.5, x2: 35, y2: 67.5, count: 3 },
];

interface WindowProps {
  x1: number; y1: number; x2: number; y2: number;
  count: number; zBot: number; zTop: number; cx: number; cy: number;
}

/**
 * Renders a row of `count` evenly spaced window quads on an isometric wall
 * face. Each window spans 60% of the inter-window spacing and is vertically
 * centred in the floor's z range. Windows are drawn as translucent blue
 * polygons with a lighter border.
 */
function WindowRow({ x1, y1, x2, y2, count, zBot, zTop, cx, cy }: WindowProps) {
  const zMid = (zBot + zTop) / 2;
  const wh = (zTop - zBot) * 0.35;
  const wz1 = zMid - wh / 2;
  const wz2 = zMid + wh / 2;
  const windows = [];
  for (let i = 0; i < count; i++) {
    const t1 = (i + 0.2) / count;
    const t2 = (i + 0.8) / count;
    const wx1 = x1 + (x2 - x1) * t1;
    const wy1 = y1 + (y2 - y1) * t1;
    const wx2 = x1 + (x2 - x1) * t2;
    const wy2 = y1 + (y2 - y1) * t2;
    const pts = vertFace(wx1, wy1, wx2, wy2, wz1, wz2, cx, cy);
    windows.push(
      <polygon key={i} points={pts}
        fill="rgba(147,197,253,0.15)" stroke="rgba(147,197,253,0.35)" strokeWidth="0.5" />
    );
  }
  return <>{windows}</>;
}

/**
 * Derives a single aggregate ZoneStatus for a wing + floor combination.
 * Returns `critical` if any zone is critical, `warn` if any is warn,
 * `offline` only if every zone is offline, and `ok` otherwise.
 *
 * @param zones - Full building zone array.
 * @param wing  - Wing to filter.
 * @param floor - Floor to filter.
 */
function wingFloorStatus(zones: Zone[], wing: Wing, floor: Floor): ZoneStatus {
  const wz = zones.filter(z => z.wing === wing && z.floor === floor);
  if (wz.some(z => z.status === 'critical')) return 'critical';
  if (wz.some(z => z.status === 'warn')) return 'warn';
  if (wz.every(z => z.status === 'offline')) return 'offline';
  return 'ok';
}

/**
 * Computes the average temperature across all zones in a wing + floor.
 * Returns `0` if no zones match.
 *
 * @param zones - Full building zone array.
 * @param wing  - Wing to filter.
 * @param floor - Floor to filter.
 * @returns Average temperature in °C.
 */
function wingFloorAvgTemp(zones: Zone[], wing: Wing, floor: Floor): number {
  const wz = zones.filter(z => z.wing === wing && z.floor === floor);
  if (!wz.length) return 0;
  return wz.reduce((s, z) => s + z.sensors.temperature, 0) / wz.length;
}

/**
 * Renders an interactive isometric 3D overview of the T-shaped building.
 * Each floor (Basement, Floor 1, Floor 2) is drawn as a stacked slab with
 * status-colored top faces, vertical wall faces, window rows, and status
 * indicator pillars. Hovering a slab highlights it; clicking calls
 * `onSelectFloor` to drill into that floor's 2D plan.
 *
 * @param zones         - All building zones used to derive per-floor status and temperature.
 * @param onSelectFloor - Callback invoked with the clicked floor level.
 */
export function BuildingElevation({ zones, onSelectFloor }: BuildingElevationProps) {
  const [hoveredFloor, setHoveredFloor] = useState<Floor | null>(null);

  const CX = 420;
  const CY = 270; // slightly lower to accommodate basement below

  const allFloors: Floor[] = [0, 1, 2];

  function floorStatus(floor: Floor): ZoneStatus {
    const fz = zones.filter(z => z.floor === floor);
    if (!fz.length) return 'ok';
    if (fz.some(z => z.status === 'critical')) return 'critical';
    if (fz.some(z => z.status === 'warn')) return 'warn';
    if (fz.every(z => z.status === 'offline')) return 'offline';
    return 'ok';
  }

  function renderFloorSlab(floor: Floor) {
    const zBot = floorZBottom(floor);
    const zTop = floorZTop(floor);
    const isHovered = hoveredFloor === floor;
    const isBasement = floor === 0;
    const status = floorStatus(floor);
    const statusColor = STATUS_COLORS[status];
    const footprint = isBasement ? BASEMENT_FOOTPRINT : T_FOOTPRINT;

    const topPoly = floorPolygon(footprint, zTop, CX, CY);

    const faces = VISIBLE_EDGES.map((e, i) => ({
      pts: vertFace(e.x1, e.y1, e.x2, e.y2, zBot, zTop, CX, CY),
      key: i,
    }));

    const glowFilter = status === 'critical' ? 'url(#glow-crit)' : isHovered ? 'url(#glow-hover)' : undefined;

    // Basement face fill is darker/earthier
    const faceFill = isBasement
      ? (isHovered ? 'rgba(120,53,15,0.55)' : 'rgba(30,15,5,0.90)')
      : (isHovered ? 'rgba(96,165,250,0.12)' : 'rgba(8,20,42,0.85)');
    const faceStroke = isBasement
      ? (isHovered ? 'rgba(251,146,60,0.70)' : 'rgba(251,146,60,0.35)')
      : (isHovered ? 'rgba(96,165,250,0.70)' : 'rgba(96,165,250,0.30)');

    const floorLabel = isBasement ? 'BASEMENT' : `FLOOR ${floor}`;

    return (
      <g
        key={floor}
        style={{ cursor: 'pointer' }}
        onClick={() => onSelectFloor(floor)}
        onMouseEnter={() => setHoveredFloor(floor)}
        onMouseLeave={() => setHoveredFloor(null)}
        filter={glowFilter}
      >
        {/* Vertical faces */}
        {faces.map(f => (
          <polygon key={f.key} points={f.pts}
            fill={faceFill}
            stroke={faceStroke}
            strokeWidth={isHovered ? 1.5 : 1}
            style={{ transition: 'fill 0.2s, stroke 0.2s' }}
          />
        ))}

        {/* Wing-colored top face regions */}
        {WING_REGIONS.map(wr => {
          const pts: [number, number][] = [
            [wr.x, wr.y],
            [wr.x + wr.w, wr.y],
            [wr.x + wr.w, wr.y + wr.h],
            [wr.x, wr.y + wr.h],
          ];
          const poly = floorPolygon(pts, zTop, CX, CY);
          const topColor = isBasement
            ? BASEMENT_WING_COLORS[wr.wing]
            : (isHovered
                ? WING_COLORS[wr.wing].top.replace('0.18', '0.28').replace('0.16', '0.26')
                : WING_COLORS[wr.wing].top);
          const strokeColor = isBasement ? 'rgba(251,146,60,0.45)' : WING_STROKE[wr.wing];
          return (
            <polygon key={wr.wing} points={poly}
              fill={topColor}
              stroke={strokeColor}
              strokeWidth={isHovered ? 1.2 : 0.8}
              style={{ transition: 'fill 0.2s' }}
            />
          );
        })}

        {/* Top face outline */}
        <polygon points={topPoly} fill="none"
          stroke={isHovered
            ? (isBasement ? 'rgba(251,146,60,0.80)' : 'rgba(96,165,250,0.80)')
            : `${statusColor}60`}
          strokeWidth={isHovered ? 2 : 1.2}
          style={{ transition: 'stroke 0.2s' }}
        />

        {/* Windows — only for above-ground floors */}
        {!isBasement && WINDOWS.map((w, i) => (
          <WindowRow key={i} {...w} zBot={zBot} zTop={zTop} cx={CX} cy={CY} />
        ))}

        {/* Basement: hatching lines on top face to indicate underground */}
        {isBasement && (() => {
          const lines = [];
          for (let xi = 2; xi < 60; xi += 5) {
            const [ax, ay] = projectPoint(xi, 0, zTop, CX, CY);
            const [bx, by] = projectPoint(xi, 37.5, zTop, CX, CY);
            lines.push(
              <line key={xi} x1={ax} y1={ay} x2={bx} y2={by}
                stroke="rgba(251,146,60,0.12)" strokeWidth="0.8" />
            );
          }
          return <>{lines}</>;
        })()}

        {/* Floor label on top face (East block center) */}
        {(() => {
          const [lx, ly] = projectPoint(10.5, 18.75, zTop + 0.5, CX, CY);
          return (
            <text x={lx} y={ly} textAnchor="middle"
              fill={isHovered
                ? (isBasement ? '#fb923c' : '#93c5fd')
                : (isBasement ? 'rgba(251,146,60,0.70)' : 'rgba(148,163,184,0.70)')}
              fontSize="9" fontWeight="700" letterSpacing="2"
              style={{ pointerEvents: 'none', transition: 'fill 0.2s' }}
            >
              {floorLabel}
            </text>
          );
        })()}

        {/* Wing labels + avg temp on top face */}
        {WING_REGIONS.map(wr => {
          const [lx, ly] = projectPoint(wr.x + wr.w / 2, wr.y + wr.h / 2, zTop + 0.5, CX, CY);
          const avgTemp = wingFloorAvgTemp(zones, wr.wing, floor);
          if (avgTemp === 0) return null;
          return (
            <g key={wr.wing} style={{ pointerEvents: 'none' }}>
              <text x={lx} y={ly - 5} textAnchor="middle"
                fill={isBasement ? '#fb923c' : WING_LABEL[wr.wing]}
                fontSize="7.5" fontWeight="700" letterSpacing="1.5"
                opacity={isHovered ? 1 : 0.75}
                style={{ textTransform: 'uppercase' }}
              >
                {wr.wing.toUpperCase()}
              </text>
              <text x={lx} y={ly + 5} textAnchor="middle"
                fill="rgba(148,163,184,0.65)" fontSize="6.5" fontWeight="500"
                opacity={isHovered ? 1 : 0.65}
                style={{ fontFamily: "'IBM Plex Mono', monospace" }}
              >
                {avgTemp.toFixed(1)}°C
              </text>
            </g>
          );
        })}

        {/* Hover click prompt */}
        {isHovered && (() => {
          const [lx, ly] = projectPoint(47.5, 18.75, zTop + 0.5, CX, CY);
          const promptColor = isBasement ? 'rgba(251,146,60,0.25)' : 'rgba(59,130,246,0.25)';
          const promptStroke = isBasement ? 'rgba(251,146,60,0.60)' : 'rgba(96,165,250,0.60)';
          const promptText = isBasement ? '#fb923c' : '#93c5fd';
          return (
            <g style={{ pointerEvents: 'none' }}>
              <rect x={lx - 36} y={ly - 9} width={72} height={16} rx="3"
                fill={promptColor} stroke={promptStroke} strokeWidth="1" />
              <text x={lx} y={ly + 2} textAnchor="middle"
                fill={promptText} fontSize="7.5" fontWeight="700" letterSpacing="1">
                CLICK TO INSPECT
              </text>
            </g>
          );
        })()}
      </g>
    );
  }

  // Dashed separator line at ground level (z=0)
  function renderGroundLine() {
    const groundPts = T_FOOTPRINT.map(([x, y]) => projectPoint(x, y, 0, CX, CY));
    const d = groundPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ') + ' Z';
    return (
      <path d={d} fill="none"
        stroke="rgba(251,146,60,0.45)" strokeWidth="1.5" strokeDasharray="5 3" />
    );
  }

  // Dashed connector between floor 1 and floor 2
  function renderFloorConnector() {
    const pts = T_FOOTPRINT.map(([x, y]) => projectPoint(x, y, FLOOR_H, CX, CY));
    const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ') + ' Z';
    return (
      <path d={d} fill="none"
        stroke="rgba(96,165,250,0.40)" strokeWidth="1.5" strokeDasharray="6 3" />
    );
  }

  function renderGroundShadow() {
    const shadowPts = T_FOOTPRINT.map(([x, y]) => {
      const [sx, sy] = projectPoint(x, y, 0, CX, CY);
      return `${sx + 6},${sy + 8}`;
    }).join(' ');
    return (
      <polygon points={shadowPts} fill="rgba(0,0,0,0.25)"
        style={{ filter: 'blur(6px)' }} />
    );
  }

  function renderStatusPillars() {
    const pills: React.ReactElement[] = [];
    const [bx, by] = projectPoint(62, 37.5, 0, CX, CY);
    allFloors.forEach((floor, fi) => {
      const status = floorStatus(floor);
      const color = floor === 0 ? '#fb923c' : STATUS_COLORS[status];
      const label = floor === 0 ? 'B' : `FL${floor}`;
      // basement is below ground: fi=0 → negative offset
      const py = by - (floor - 0) * FLOOR_H * SCALE * ISO_SIN - 10;
      pills.push(
        <g key={floor}>
          <circle cx={bx + 14} cy={py} r="5" fill={color} opacity="0.85"
            style={{ filter: `drop-shadow(0 0 4px ${color}80)` }} />
          <text x={bx + 22} y={py + 4} fill={color} fontSize="8" fontWeight="700">{label}</text>
        </g>
      );
    });
    return <>{pills}</>;
  }

  const totalZones = zones.length;
  const basementZones = zones.filter(z => z.floor === 0).length;

  return (
    <svg
      viewBox="0 0 860 520"
      className="w-full h-full"
      style={{ fontFamily: "'Space Grotesk', sans-serif" }}
    >
      <defs>
        <filter id="glow-hover" x="-15%" y="-15%" width="130%" height="130%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-crit" x="-15%" y="-15%" width="130%" height="130%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <radialGradient id="ground-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(96,165,250,0.08)" />
          <stop offset="100%" stopColor="rgba(96,165,250,0)" />
        </radialGradient>
      </defs>

      {/* Ground plane ellipse */}
      <ellipse cx={CX} cy={CY + 30} rx="340" ry="60" fill="url(#ground-grad)" />

      {/* Ground shadow */}
      {renderGroundShadow()}

      {/* Render bottom-up: Basement → Floor 1 → Floor 2 */}
      {renderFloorSlab(0)}
      {renderGroundLine()}
      {renderFloorSlab(1)}
      {renderFloorConnector()}
      {renderFloorSlab(2)}

      {/* Status pillars */}
      {renderStatusPillars()}

      {/* Building title */}
      <text x="20" y="30" fill="rgba(96,165,250,0.60)" fontSize="10" fontWeight="700" letterSpacing="3">
        ADVANCED MANUFACTURING HUB
      </text>
      <text x="20" y="44" fill="rgba(96,165,250,0.35)" fontSize="8" letterSpacing="2">
        T-SHAPE · BASEMENT + 2 FLOORS · {totalZones} ZONES
      </text>

      {/* Basement legend badge */}
      <rect x="20" y="54" width="110" height="14" rx="3"
        fill="rgba(251,146,60,0.12)" stroke="rgba(251,146,60,0.35)" strokeWidth="0.8" />
      <text x="75" y="64" textAnchor="middle" fill="rgba(251,146,60,0.75)" fontSize="7.5" fontWeight="700" letterSpacing="1.5">
        ▼ BASEMENT · {basementZones} LABS
      </text>

      {/* Instruction hint */}
      <text x="430" y="505" textAnchor="middle" fill="rgba(96,165,250,0.35)" fontSize="8" letterSpacing="1.5">
        HOVER A FLOOR TO PREVIEW · CLICK TO INSPECT
      </text>
    </svg>
  );
}
