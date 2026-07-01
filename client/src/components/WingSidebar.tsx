/* ============================================================
   WingSidebar.tsx — Left sidebar with wing navigation and zone list
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { Building2, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import type { Wing, Zone, ZoneStatus } from '@/lib/buildingData';
import { STATUS_COLORS, WING_LABELS } from '@/lib/buildingData';

interface WingSidebarProps {
  zones: Zone[];
  selectedZoneId: string | null;
  onSelectZone: (id: string) => void;
  activeWing: Wing;
  onSelectWing: (wing: Wing) => void;
}

const WING_ORDER: Wing[] = ['east', 'west', 'north'];

const WING_ACCENT: Record<Wing, string> = {
  east: '#22c55e',
  west: '#3b82f6',
  north: '#ef4444',
};

function ZoneRow({
  zone,
  isSelected,
  onClick,
}: {
  zone: Zone;
  isSelected: boolean;
  onClick: () => void;
}) {
  const statusColor = STATUS_COLORS[zone.status];
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-3 py-2 rounded text-left transition-all duration-150"
      style={{
        background: isSelected ? 'oklch(0.65 0.18 220 / 12%)' : 'transparent',
        border: isSelected ? '1px solid oklch(0.65 0.18 220 / 30%)' : '1px solid transparent',
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ background: statusColor, boxShadow: `0 0 5px ${statusColor}80` }}
      />
      <span
        className="font-data text-[9px] font-semibold tracking-wider flex-shrink-0 w-7"
        style={{ color: isSelected ? '#93c5fd' : 'oklch(0.50 0.015 230)' }}
      >
        {zone.shortName}
      </span>
      <span
        className="text-[11px] truncate flex-1"
        style={{ color: isSelected ? '#e2e8f0' : 'oklch(0.65 0.015 230)' }}
      >
        {zone.name}
      </span>
      <span
        className="font-data text-[9px] flex-shrink-0"
        style={{ color: zone.sensors.temperature > 26 ? '#f59e0b' : 'oklch(0.45 0.015 230)' }}
      >
        {zone.sensors.temperature.toFixed(1)}°
      </span>
    </button>
  );
}

function WingSection({
  wing,
  zones,
  selectedZoneId,
  onSelectZone,
  isActive,
  onActivate,
}: {
  wing: Wing;
  zones: Zone[];
  selectedZoneId: string | null;
  onSelectZone: (id: string) => void;
  isActive: boolean;
  onActivate: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const accent = WING_ACCENT[wing];
  const basement = zones.filter(z => z.floor === 0);
  const floor1 = zones.filter(z => z.floor === 1);
  const floor2 = zones.filter(z => z.floor === 2);
  const critCount = zones.filter(z => z.status === 'critical').length;
  const warnCount = zones.filter(z => z.status === 'warn').length;

  return (
    <div className="flex flex-col">
      {/* Wing header */}
      <button
        className="flex items-center gap-2 px-3 py-2.5 text-left transition-all duration-150 hover:bg-white/5"
        style={{
          borderLeft: `2px solid ${isActive ? accent : 'transparent'}`,
          background: isActive ? `${accent}08` : 'transparent',
        }}
        onClick={() => { onActivate(); setExpanded(e => !e); }}
      >
        <Building2 size={12} style={{ color: isActive ? accent : 'oklch(0.45 0.015 230)' }} />
        <span
          className="text-[11px] font-bold tracking-wider uppercase flex-1"
          style={{ color: isActive ? accent : 'oklch(0.60 0.015 230)' }}
        >
          {WING_LABELS[wing]}
        </span>
        <div className="flex items-center gap-1">
          {critCount > 0 && (
            <span
              className="font-data text-[9px] px-1 rounded"
              style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}
            >
              {critCount}
            </span>
          )}
          {warnCount > 0 && (
            <span
              className="font-data text-[9px] px-1 rounded"
              style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}
            >
              {warnCount}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronDown size={11} style={{ color: 'oklch(0.45 0.015 230)' }} />
        ) : (
          <ChevronRight size={11} style={{ color: 'oklch(0.45 0.015 230)' }} />
        )}
      </button>

      {/* Zone list */}
      {expanded && (
        <div className="flex flex-col px-1 pb-1">
          {/* Basement */}
          {basement.length > 0 && (
            <>
              <div className="px-2 py-1">
                <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'rgba(251,146,60,0.65)' }}>
                  ▼ Basement
                </span>
              </div>
              {basement.map(zone => (
                <ZoneRow
                  key={zone.id}
                  zone={zone}
                  isSelected={zone.id === selectedZoneId}
                  onClick={() => onSelectZone(zone.id)}
                />
              ))}
            </>
          )}
          {/* Floor 1 */}
          {floor1.length > 0 && (
            <>
              <div className="px-2 py-1 mt-1">
                <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.38 0.015 230)' }}>
                  Floor 1
                </span>
              </div>
              {floor1.map(zone => (
                <ZoneRow
                  key={zone.id}
                  zone={zone}
                  isSelected={zone.id === selectedZoneId}
                  onClick={() => onSelectZone(zone.id)}
                />
              ))}
            </>
          )}
          {/* Floor 2 */}
          {floor2.length > 0 && (
            <>
              <div className="px-2 py-1 mt-1">
                <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.38 0.015 230)' }}>
                  Floor 2
                </span>
              </div>
              {floor2.map(zone => (
                <ZoneRow
                  key={zone.id}
                  zone={zone}
                  isSelected={zone.id === selectedZoneId}
                  onClick={() => onSelectZone(zone.id)}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function WingSidebar({
  zones,
  selectedZoneId,
  onSelectZone,
  activeWing,
  onSelectWing,
}: WingSidebarProps) {
  return (
    <aside
      className="flex flex-col h-full overflow-hidden flex-shrink-0"
      style={{
        width: 'clamp(180px, 16vw, 240px)',
        background: 'oklch(0.09 0.025 240)',
        borderRight: '1px solid oklch(1 0 0 / 8%)',
      }}
    >
      {/* Sidebar header */}
      <div
        className="px-3 py-3 flex-shrink-0"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)' }}
      >
        <div className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.45 0.015 230)' }}>
          Building Zones
        </div>
        <div className="font-data text-[10px] mt-0.5" style={{ color: 'oklch(0.38 0.015 230)' }}>
          {zones.length} zones monitored
        </div>
      </div>

      {/* Wing sections */}
      <div className="flex-1 overflow-y-auto py-1">
        {WING_ORDER.map(wing => (
          <WingSection
            key={wing}
            wing={wing}
            zones={zones.filter(z => z.wing === wing)}
            selectedZoneId={selectedZoneId}
            onSelectZone={onSelectZone}
            isActive={activeWing === wing}
            onActivate={() => onSelectWing(wing)}
          />
        ))}
      </div>
    </aside>
  );
}
