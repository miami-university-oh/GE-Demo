/* ============================================================
   FloorPlan.tsx — Architectural Map-Style T-shaped Building
   V3: Single-floor detail view (used after zoom-in from elevation)
   - Thick outer walls, inner room dividers, door arcs
   - Corridor spine running through North Wing
   - Stairwell / elevator shafts at wing junctions
   - Status heat-fill inside rooms, glowing outlines
   - Compass rose + scale bar
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { useRef, useState } from 'react';
import type { Floor, Wing, Zone, ZoneStatus } from '@/lib/buildingData';
import { STATUS_COLORS } from '@/lib/buildingData';

interface FloorPlanProps {
  zones: Zone[];
  selectedZoneId: string | null;
  onSelectZone: (id: string) => void;
  floor: Floor;
}

interface RoomDef {
  id: string;
  floor: Floor;
  wing: Wing;
  x: number; y: number; w: number; h: number;
  label: string;
  shortName: string;
  type: string;
  door?: { side: 'top' | 'bottom' | 'left' | 'right'; pos: number };
}

// ─────────────────────────────────────────────────────────────
// Single-floor viewBox: 960 × 580
// Origin offset: OX=20, OY=20
// East Wing block:   x 20→188,  y 20→320
// North Wing spine:  x 198→308, y 20→560
// West Wing block:   x 318→510, y 20→320
// ─────────────────────────────────────────────────────────────

const W  = 6;  // outer wall thickness
const IW = 3;  // inner wall thickness
const OX = 20;
const OY = 20;

function makeRooms(floor: Floor): RoomDef[] {
  // ── BASEMENT LAYOUT ──
  if (floor === 0) {
    return [
      // Makino Subtractive Lab — East Wing (large, left side)
      {
        id: 'B0-MAK',
        floor: 0, wing: 'east',
        x: OX + W, y: OY + 14, w: 148 - W, h: 270 - W,
        label: 'Subtractive Mfg Lab (Makino)',
        shortName: 'MAK',
        type: 'lab',
        door: { side: 'right', pos: 0.3 },
      },
      // Welding Lab — small room in middle, closer to East
      {
        id: 'B0-WLD',
        floor: 0, wing: 'east',
        x: OX + 198 + W, y: OY + 14, w: 70 - W, h: 130 - W,
        label: 'Welding Lab',
        shortName: 'WLD',
        type: 'lab',
        door: { side: 'bottom', pos: 0.5 },
      },
      // Utility / corridor space in North spine basement
      {
        id: 'B0-WLD',
        floor: 0, wing: 'north',
        x: OX + 198 + W, y: OY + 150, w: 70 - W, h: 130 - W,
        label: 'Welding Annex',
        shortName: 'WLDX',
        type: 'utility',
        door: { side: 'top', pos: 0.5 },
      },
      // Integrated Industry Subtractive Lab — West Wing (large, right side)
      {
        id: 'B0-INT',
        floor: 0, wing: 'west',
        x: OX + 318 + W, y: OY + 14, w: 186 - W, h: 270 - W,
        label: 'Subtractive Mfg Lab (Integrated Industry)',
        shortName: 'INTI',
        type: 'lab',
        door: { side: 'left', pos: 0.3 },
      },
    ];
  }

  return [
    // ── EAST WING ──
    {
      id: floor === 1 ? 'E1-ROB' : 'E2-AI',
      floor, wing: 'east',
      x: OX + W, y: OY + 14, w: 80 - W, h: 140 - W,
      label: floor === 1 ? 'Robotics Lab' : 'AI & ML Lab',
      shortName: floor === 1 ? 'ROB' : 'AI',
      type: 'lab',
      door: { side: 'right', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'E1-CNC' : 'E2-VR',
      floor, wing: 'east',
      x: OX + 86, y: OY + 14, w: 80, h: 140 - W,
      label: floor === 1 ? 'CNC Machining Lab' : 'XR / VR Lab',
      shortName: floor === 1 ? 'CNC' : 'XR',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'E1-ELE' : 'E2-OFF',
      floor, wing: 'east',
      x: OX + W, y: OY + 160, w: 80 - W, h: 140 - W,
      label: floor === 1 ? 'Electronics Lab' : 'Research Office',
      shortName: floor === 1 ? 'ELE' : 'OFF',
      type: floor === 1 ? 'lab' : 'office',
      door: { side: 'right', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'E1-STR' : 'E2-CONF',
      floor, wing: 'east',
      x: OX + 86, y: OY + 160, w: 80, h: 140 - W,
      label: floor === 1 ? 'Storage & Utility' : 'Conference Room',
      shortName: floor === 1 ? 'STR' : 'CNF',
      type: floor === 1 ? 'utility' : 'conference',
      door: { side: 'top', pos: 0.5 },
    },

    // ── NORTH WING ──
    {
      id: floor === 1 ? 'N1-FAB' : 'N2-SENS',
      floor, wing: 'north',
      x: OX + 198 + W, y: OY + 14, w: 52 - W, h: 130 - W,
      label: floor === 1 ? 'Fabrication Lab' : 'Sensor Lab',
      shortName: floor === 1 ? 'FAB' : 'SNS',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'N1-TEST' : 'N2-EDGE',
      floor, wing: 'north',
      x: OX + 256, y: OY + 14, w: 46 - W, h: 130 - W,
      label: floor === 1 ? 'Testing Lab' : 'Edge Computing',
      shortName: floor === 1 ? 'TST' : 'EDG',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'N1-CTRL' : 'N2-COLLAB',
      floor, wing: 'north',
      x: OX + 198 + W, y: OY + 150, w: 52 - W, h: 130 - W,
      label: floor === 1 ? 'Control Systems' : 'Collaboration Hub',
      shortName: floor === 1 ? 'CTL' : 'HUB',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'N1-CORR' : 'N2-UTIL',
      floor, wing: 'north',
      x: OX + 256, y: OY + 150, w: 46 - W, h: 130 - W,
      label: floor === 1 ? 'Corridor / Lobby' : 'Utility Room',
      shortName: floor === 1 ? 'LBY' : 'UTL',
      type: floor === 1 ? 'corridor' : 'utility',
      door: { side: 'top', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'N1-FAB' : 'N2-SENS',
      floor, wing: 'north',
      x: OX + 198 + W, y: OY + 286, w: 52 - W, h: 130 - W,
      label: floor === 1 ? 'Fab. Annex' : 'Sensor Annex',
      shortName: floor === 1 ? 'FAX' : 'SAX',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'N1-TEST' : 'N2-EDGE',
      floor, wing: 'north',
      x: OX + 256, y: OY + 286, w: 46 - W, h: 130 - W,
      label: floor === 1 ? 'Test Annex' : 'Edge Annex',
      shortName: floor === 1 ? 'TAX' : 'EAX',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },

    // ── WEST WING ──
    {
      id: floor === 1 ? 'W1-NET' : 'W2-CYB',
      floor, wing: 'west',
      x: OX + 318 + W, y: OY + 14, w: 58 - W, h: 140 - W,
      label: floor === 1 ? 'Network Lab' : 'Cybersecurity Lab',
      shortName: floor === 1 ? 'NET' : 'CYB',
      type: 'lab',
      door: { side: 'right', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'W1-IOT' : 'W2-DAT',
      floor, wing: 'west',
      x: OX + 382, y: OY + 14, w: 64 - W, h: 140 - W,
      label: floor === 1 ? 'IIoT Lab' : 'Data Science Lab',
      shortName: floor === 1 ? 'IOT' : 'DAT',
      type: 'lab',
      door: { side: 'bottom', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'W1-SRV' : 'W2-OFF',
      floor, wing: 'west',
      x: OX + 452, y: OY + 14, w: 52 - W, h: 140 - W,
      label: floor === 1 ? 'Server Room' : 'Admin Office',
      shortName: floor === 1 ? 'SRV' : 'ADM',
      type: floor === 1 ? 'server' : 'office',
      door: { side: 'left', pos: 0.5 },
    },
    {
      id: floor === 1 ? 'W1-CAL' : 'W2-CONF',
      floor, wing: 'west',
      x: OX + 318 + W, y: OY + 160, w: 186 - W, h: 140 - W,
      label: floor === 1 ? 'Calibration Lab' : 'Boardroom',
      shortName: floor === 1 ? 'CAL' : 'BRD',
      type: floor === 1 ? 'lab' : 'conference',
      door: { side: 'top', pos: 0.3 },
    },
  ];
}

// T-shape outer wall path (single floor)
function tShapePath(): string {
  const x0 = OX, x1 = OX + 168, x2 = OX + 198, x3 = OX + 308, x4 = OX + 318, x5 = OX + 510;
  const y0 = OY, y1 = OY + 300, y2 = OY + 560;
  return [
    `M ${x0} ${y0}`, `L ${x1} ${y0}`, `L ${x2} ${y0}`, `L ${x3} ${y0}`,
    `L ${x4} ${y0}`, `L ${x5} ${y0}`, `L ${x5} ${y1}`, `L ${x4} ${y1}`,
    `L ${x3} ${y1}`, `L ${x3} ${y2}`, `L ${x2} ${y2}`, `L ${x2} ${y1}`,
    `L ${x1} ${y1}`, `L ${x0} ${y1}`, `Z`,
  ].join(' ');
}

const STATUS_FILL: Record<ZoneStatus, string> = {
  ok:       'rgba(34,197,94,0.09)',
  warn:     'rgba(245,158,11,0.11)',
  critical: 'rgba(239,68,68,0.14)',
  offline:  'rgba(100,116,139,0.06)',
};
const STATUS_STROKE: Record<ZoneStatus, string> = {
  ok:       'rgba(34,197,94,0.55)',
  warn:     'rgba(245,158,11,0.60)',
  critical: 'rgba(239,68,68,0.70)',
  offline:  'rgba(100,116,139,0.30)',
};
const SELECTED_FILL   = 'rgba(59,130,246,0.16)';
const SELECTED_STROKE = 'rgba(96,165,250,0.90)';
const HOVER_FILL      = 'rgba(96,165,250,0.10)';

const WING_LABEL_COLOR: Record<Wing, string> = {
  east:  'rgba(34,197,94,0.80)',
  north: 'rgba(239,68,68,0.75)',
  west:  'rgba(96,165,250,0.80)',
};
const WING_BAND_COLOR: Record<Wing, string> = {
  east:  'rgba(34,197,94,0.12)',
  north: 'rgba(239,68,68,0.10)',
  west:  'rgba(59,130,246,0.10)',
};

function DoorArc({ room, color }: { room: RoomDef; color: string }) {
  if (!room.door) return null;
  const { side, pos } = room.door;
  const DW = 16;
  if (side === 'bottom') {
    const bx = room.x + room.w * pos - DW / 2;
    const by = room.y + room.h;
    return <g>
      <line x1={bx} y1={by} x2={bx + DW} y2={by} stroke={color} strokeWidth="2.5" />
      <path d={`M ${bx} ${by} Q ${bx} ${by - DW} ${bx + DW} ${by}`} fill="none" stroke={color} strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
    </g>;
  }
  if (side === 'top') {
    const bx = room.x + room.w * pos - DW / 2;
    const by = room.y;
    return <g>
      <line x1={bx} y1={by} x2={bx + DW} y2={by} stroke={color} strokeWidth="2.5" />
      <path d={`M ${bx} ${by} Q ${bx} ${by + DW} ${bx + DW} ${by}`} fill="none" stroke={color} strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
    </g>;
  }
  if (side === 'right') {
    const bx = room.x + room.w;
    const by = room.y + room.h * pos - DW / 2;
    return <g>
      <line x1={bx} y1={by} x2={bx} y2={by + DW} stroke={color} strokeWidth="2.5" />
      <path d={`M ${bx} ${by} Q ${bx - DW} ${by} ${bx} ${by + DW}`} fill="none" stroke={color} strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
    </g>;
  }
  if (side === 'left') {
    const bx = room.x;
    const by = room.y + room.h * pos - DW / 2;
    return <g>
      <line x1={bx} y1={by} x2={bx} y2={by + DW} stroke={color} strokeWidth="2.5" />
      <path d={`M ${bx} ${by} Q ${bx + DW} ${by} ${bx} ${by + DW}`} fill="none" stroke={color} strokeWidth="1" strokeDasharray="2 2" opacity="0.5" />
    </g>;
  }
  return null;
}

function Stairwell({ x, y, w, h }: { x: number; y: number; w: number; h: number }) {
  const steps = 6;
  return <g>
    <rect x={x} y={y} width={w} height={h} fill="rgba(96,165,250,0.05)" stroke="rgba(96,165,250,0.30)" strokeWidth="1.5" strokeDasharray="4 2" />
    {Array.from({ length: steps }, (_, i) => (
      <line key={i} x1={x} y1={y + (h / steps) * (i + 1)} x2={x + w} y2={y + (h / steps) * (i + 1)}
        stroke="rgba(96,165,250,0.20)" strokeWidth="1" />
    ))}
    <text x={x + w / 2} y={y + h / 2 + 4} textAnchor="middle" fill="rgba(96,165,250,0.45)" fontSize="8" fontWeight="600" letterSpacing="1">STAIR</text>
  </g>;
}

function Elevator({ x, y, w, h }: { x: number; y: number; w: number; h: number }) {
  return <g>
    <rect x={x} y={y} width={w} height={h} fill="rgba(167,139,250,0.08)" stroke="rgba(167,139,250,0.35)" strokeWidth="1.5" />
    <line x1={x} y1={y} x2={x + w} y2={y + h} stroke="rgba(167,139,250,0.25)" strokeWidth="1" />
    <line x1={x + w} y1={y} x2={x} y2={y + h} stroke="rgba(167,139,250,0.25)" strokeWidth="1" />
    <text x={x + w / 2} y={y + h / 2 + 3} textAnchor="middle" fill="rgba(167,139,250,0.55)" fontSize="7" fontWeight="600">LIFT</text>
  </g>;
}

function CompassRose({ x, y }: { x: number; y: number }) {
  return <g transform={`translate(${x},${y})`}>
    <circle cx="0" cy="0" r="16" fill="rgba(13,31,60,0.80)" stroke="rgba(96,165,250,0.30)" strokeWidth="1" />
    <polygon points="0,-12 3.5,-4 0,-7 -3.5,-4" fill="rgba(96,165,250,0.80)" />
    <polygon points="0,12 3.5,4 0,7 -3.5,4" fill="rgba(96,165,250,0.30)" />
    <polygon points="-12,0 -4,-3.5 -7,0 -4,3.5" fill="rgba(96,165,250,0.30)" />
    <polygon points="12,0 4,-3.5 7,0 4,3.5" fill="rgba(96,165,250,0.30)" />
    <text x="0" y="-16" textAnchor="middle" fill="rgba(96,165,250,0.80)" fontSize="8" fontWeight="700">N</text>
  </g>;
}

export function FloorPlan({ zones, selectedZoneId, onSelectZone, floor }: FloorPlanProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; room: RoomDef } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const rooms = makeRooms(floor);

  // Deduplicate by id
  const seen = new Set<string>();
  const uniqueRooms = rooms.filter(r => {
    if (seen.has(r.id)) return false;
    seen.add(r.id);
    return true;
  });

  const handleMouseMove = (e: React.MouseEvent<SVGGElement>, room: RoomDef) => {
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const sp = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    setTooltip({ x: sp.x, y: sp.y, room });
  };

  return (
    <div className="relative w-full h-full">
      <svg
        ref={svgRef}
        viewBox="0 0 560 600"
        className="w-full h-full"
        style={{ fontFamily: "'Space Grotesk', sans-serif" }}
        onMouseLeave={() => { setHoveredId(null); setTooltip(null); }}
      >
        <defs>
          <filter id="fp-glow-sel" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="fp-glow-crit" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <pattern id="fp-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(96,165,250,0.04)" strokeWidth="0.5" />
          </pattern>
        </defs>

        {/* Grid background */}
        <rect width="560" height="600" fill="url(#fp-grid)" />

        {/* Building shadow */}
        <path d={tShapePath()} fill="rgba(0,0,0,0.30)" transform="translate(4,5)" />

        {/* Building floor fill */}
        <path d={tShapePath()} fill="rgba(8,20,42,0.92)" />

        {/* Floor indicator badge */}
        {floor === 0 && (
          <>
            <rect x={OX} y={OY - 14} width={490} height={12} fill="rgba(251,146,60,0.10)" stroke="rgba(251,146,60,0.30)" strokeWidth="0.8" rx="2" />
            <text x={OX + 245} y={OY - 5} textAnchor="middle" fill="rgba(251,146,60,0.80)" fontSize="7.5" fontWeight="700" letterSpacing="2">▼ BASEMENT LEVEL · SUBTRACTIVE MANUFACTURING ZONE</text>
          </>
        )}

        {/* Wing label bands */}
        <rect x={OX} y={OY} width={168} height={14} fill={floor === 0 ? 'rgba(251,146,60,0.12)' : WING_BAND_COLOR.east} />
        <text x={OX + 84} y={OY + 10} textAnchor="middle" fill={floor === 0 ? 'rgba(251,146,60,0.80)' : WING_LABEL_COLOR.east} fontSize="7.5" fontWeight="700" letterSpacing="2" style={{ textTransform: 'uppercase' }}>{floor === 0 ? 'EAST WING — MAKINO' : 'EAST WING'}</text>

        <rect x={OX + 198} y={OY} width={110} height={14} fill={floor === 0 ? 'rgba(251,146,60,0.08)' : WING_BAND_COLOR.north} />
        <text x={OX + 253} y={OY + 10} textAnchor="middle" fill={floor === 0 ? 'rgba(251,146,60,0.60)' : WING_LABEL_COLOR.north} fontSize="7.5" fontWeight="700" letterSpacing="2" style={{ textTransform: 'uppercase' }}>{floor === 0 ? 'WELDING' : 'NORTH'}</text>

        <rect x={OX + 318} y={OY} width={192} height={14} fill={floor === 0 ? 'rgba(251,146,60,0.12)' : WING_BAND_COLOR.west} />
        <text x={OX + 414} y={OY + 10} textAnchor="middle" fill={floor === 0 ? 'rgba(251,146,60,0.80)' : WING_LABEL_COLOR.west} fontSize="7.5" fontWeight="700" letterSpacing="2" style={{ textTransform: 'uppercase' }}>{floor === 0 ? 'WEST WING — INTEGRATED INDUSTRY' : 'WEST WING'}</text>

        {/* Corridor spine */}
        <rect x={OX + 198 + W} y={OY + 14} width={110 - W * 2} height={546 - 14}
          fill="rgba(96,165,250,0.03)" stroke="rgba(96,165,250,0.10)" strokeWidth="1" strokeDasharray="6 4" />
        <line x1={OX + 253} y1={OY + 14} x2={OX + 253} y2={OY + 554}
          stroke="rgba(96,165,250,0.08)" strokeWidth="1" strokeDasharray="4 4" />

        {/* Stairwells */}
        <Stairwell x={OX + 148} y={OY + 14} w={22} h={42} />
        <Stairwell x={OX + 308} y={OY + 14} w={22} h={42} />

        {/* Elevators */}
        <Elevator x={OX + 148} y={OY + 62} w={22} h={24} />
        <Elevator x={OX + 308} y={OY + 62} w={22} h={24} />

        {/* Inner walls — East Wing */}
        <line x1={OX + W} y1={OY + 160} x2={OX + 162} y2={OY + 160} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />
        <line x1={OX + 86} y1={OY + 14} x2={OX + 86} y2={OY + 294} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />

        {/* Inner walls — West Wing */}
        <line x1={OX + 324} y1={OY + 160} x2={OX + 504} y2={OY + 160} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />
        <line x1={OX + 382} y1={OY + 14} x2={OX + 382} y2={OY + 154} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />
        <line x1={OX + 452} y1={OY + 14} x2={OX + 452} y2={OY + 154} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />

        {/* Inner walls — North Wing */}
        <line x1={OX + 204} y1={OY + 150} x2={OX + 302} y2={OY + 150} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />
        <line x1={OX + 204} y1={OY + 286} x2={OX + 302} y2={OY + 286} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />
        <line x1={OX + 256} y1={OY + 14} x2={OX + 256} y2={OY + 554} stroke="rgba(96,165,250,0.25)" strokeWidth={IW} />

        {/* Rooms */}
        {uniqueRooms.map(room => {
          const zone = zones.find(z => z.id === room.id);
          const status: ZoneStatus = zone?.status ?? 'offline';
          const isSelected = room.id === selectedZoneId;
          const isHovered  = room.id === hoveredId;
          const fill   = isSelected ? SELECTED_FILL : isHovered ? HOVER_FILL : STATUS_FILL[status];
          const stroke = isSelected ? SELECTED_STROKE : STATUS_STROKE[status];
          const cx = room.x + room.w / 2;
          const cy = room.y + room.h / 2;
          const isSmall = room.w < 55 || room.h < 55;

          return (
            <g
              key={room.id}
              style={{ cursor: 'pointer' }}
              onClick={() => onSelectZone(room.id)}
              onMouseEnter={() => setHoveredId(room.id)}
              onMouseLeave={() => { setHoveredId(null); setTooltip(null); }}
              onMouseMove={e => handleMouseMove(e, room)}
            >
              <rect x={room.x} y={room.y} width={room.w} height={room.h}
                fill={fill} stroke="none"
                style={{ transition: 'fill 0.18s ease-out' }} />
              <rect x={room.x + 1} y={room.y + 1} width={room.w - 2} height={room.h - 2}
                fill="none" stroke={stroke} strokeWidth={isSelected ? 1.5 : 1} rx="1"
                filter={isSelected || status === 'critical' ? 'url(#fp-glow-sel)' : undefined}
                style={{ transition: 'stroke 0.18s ease-out' }} />
              {/* Corner ticks */}
              <path d={`M ${room.x + 9} ${room.y + 2} L ${room.x + 2} ${room.y + 2} L ${room.x + 2} ${room.y + 9}`}
                fill="none" stroke={stroke} strokeWidth="1.5" opacity="0.8" />
              <path d={`M ${room.x + room.w - 9} ${room.y + room.h - 2} L ${room.x + room.w - 2} ${room.y + room.h - 2} L ${room.x + room.w - 2} ${room.y + room.h - 9}`}
                fill="none" stroke={stroke} strokeWidth="1.5" opacity="0.8" />
              {/* Status dot */}
              <circle cx={room.x + room.w - 8} cy={room.y + 8} r="4"
                fill={STATUS_COLORS[status]} opacity="0.9" />
              {status === 'critical' && (
                <circle cx={room.x + room.w - 8} cy={room.y + 8} r="7"
                  fill="none" stroke={STATUS_COLORS.critical} strokeWidth="1" opacity="0.4" />
              )}
              {/* Short name */}
              <text x={cx} y={cy + (isSmall ? 3 : -5)} textAnchor="middle"
                fill={isSelected ? '#bfdbfe' : 'rgba(226,232,240,0.88)'}
                fontSize={isSmall ? "8.5" : "10"} fontWeight="700" letterSpacing="1.5"
                style={{ textTransform: 'uppercase', pointerEvents: 'none' }}>
                {room.shortName}
              </text>
              {/* Full name */}
              {!isSmall && (
                <text x={cx} y={cy + 8} textAnchor="middle"
                  fill={isSelected ? '#93c5fd' : 'rgba(148,163,184,0.70)'}
                  fontSize="7" style={{ pointerEvents: 'none' }}>
                  {room.label.length > 17 ? room.label.slice(0, 16) + '…' : room.label}
                </text>
              )}
              {/* Type tag */}
              {!isSmall && room.h > 80 && (
                <text x={cx} y={room.y + room.h - 8} textAnchor="middle"
                  fill={isSelected ? '#60a5fa' : 'rgba(100,116,139,0.55)'}
                  fontSize="6.5" fontWeight="500" letterSpacing="0.8"
                  style={{ textTransform: 'uppercase', pointerEvents: 'none' }}>
                  {room.type}
                </text>
              )}
              <DoorArc room={room} color={stroke} />
            </g>
          );
        })}

        {/* Outer walls on top */}
        <path d={tShapePath()} fill="none" stroke="rgba(96,165,250,0.55)" strokeWidth={W} strokeLinejoin="miter" />

        {/* Compass */}
        <CompassRose x={530} y={44} />

        {/* Scale bar */}
        <g transform={`translate(${OX + 10}, 578)`}>
          <line x1="0" y1="0" x2="60" y2="0" stroke="rgba(96,165,250,0.50)" strokeWidth="1.5" />
          <line x1="0" y1="-4" x2="0" y2="4" stroke="rgba(96,165,250,0.50)" strokeWidth="1.5" />
          <line x1="60" y1="-4" x2="60" y2="4" stroke="rgba(96,165,250,0.50)" strokeWidth="1.5" />
          <text x="30" y="-6" textAnchor="middle" fill="rgba(96,165,250,0.50)" fontSize="7">10 m</text>
        </g>

        {/* Tooltip */}
        {tooltip && (() => {
          const zone = zones.find(z => z.id === tooltip.room.id);
          const tx = Math.min(tooltip.x + 12, 440);
          const ty = Math.max(tooltip.y - 52, 8);
          const status: ZoneStatus = zone?.status ?? 'offline';
          return (
            <g style={{ pointerEvents: 'none' }}>
              <rect x={tx} y={ty} width="155" height="46"
                fill="rgba(8,20,40,0.96)" stroke="rgba(96,165,250,0.45)" strokeWidth="1" rx="3" />
              <text x={tx + 8} y={ty + 13} fill="#e2e8f0" fontSize="9" fontWeight="700">{tooltip.room.label}</text>
              <text x={tx + 8} y={ty + 25} fill={STATUS_COLORS[status]} fontSize="8" fontWeight="600">
                ● {status.toUpperCase()} · {tooltip.room.wing.toUpperCase()} WING
              </text>
              {zone && (
                <text x={tx + 8} y={ty + 37} fill="rgba(148,163,184,0.80)" fontSize="7.5">
                  {zone.sensors.temperature.toFixed(1)}°C · {zone.sensors.energyKw.toFixed(1)} kW · {zone.sensors.occupancy} pax
                </text>
              )}
            </g>
          );
        })()}
      </svg>
    </div>
  );
}
