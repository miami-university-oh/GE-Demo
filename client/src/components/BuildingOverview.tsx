/* ============================================================
   BuildingOverview.tsx — Collapsible bottom stats panel
   Shows per-wing summaries and building-wide donut chart
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import type { Wing, Zone } from '@/lib/buildingData';
import { STATUS_COLORS, WING_LABELS } from '@/lib/buildingData';
import { Activity, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface BuildingOverviewProps {
  zones: Zone[];
}

const WING_ORDER: Wing[] = ['east', 'west', 'north'];
const WING_ACCENT: Record<Wing, string> = {
  east: '#22c55e',
  west: '#3b82f6',
  north: '#ef4444',
};

function WingCard({ wing, zones }: { wing: Wing; zones: Zone[] }) {
  const ok = zones.filter(z => z.status === 'ok').length;
  const warn = zones.filter(z => z.status === 'warn').length;
  const critical = zones.filter(z => z.status === 'critical').length;
  const offline = zones.filter(z => z.status === 'offline').length;
  const avgTemp = zones.reduce((s, z) => s + z.sensors.temperature, 0) / (zones.length || 1);
  const totalEnergy = zones.reduce((s, z) => s + z.sensors.energyKw, 0);
  const accent = WING_ACCENT[wing];

  const data = [
    { name: 'OK', value: ok, color: '#22c55e' },
    { name: 'Warn', value: warn, color: '#f59e0b' },
    { name: 'Critical', value: critical, color: '#ef4444' },
    { name: 'Offline', value: offline, color: '#64748b' },
  ].filter(d => d.value > 0);

  return (
    <div
      className="flex items-center gap-4 px-4 py-3 rounded flex-1"
      style={{
        background: 'oklch(0.12 0.025 240)',
        border: `1px solid ${accent}25`,
        borderLeft: `3px solid ${accent}`,
      }}
    >
      {/* Mini donut */}
      <div style={{ width: 52, height: 52, flexShrink: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data.length ? data : [{ name: 'none', value: 1, color: '#1e293b' }]}
              cx="50%"
              cy="50%"
              innerRadius={16}
              outerRadius={24}
              dataKey="value"
              strokeWidth={0}
              isAnimationActive={false}
            >
              {(data.length ? data : [{ color: '#1e293b' }]).map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Wing info */}
      <div className="flex flex-col gap-1 min-w-0">
        <span className="text-[11px] font-bold tracking-wider uppercase" style={{ color: accent }}>
          {WING_LABELS[wing]}
        </span>
        <div className="flex items-center gap-2">
          {ok > 0 && <span className="font-data text-[10px]" style={{ color: '#22c55e' }}>{ok} OK</span>}
          {warn > 0 && <span className="font-data text-[10px]" style={{ color: '#f59e0b' }}>{warn} WARN</span>}
          {critical > 0 && <span className="font-data text-[10px]" style={{ color: '#ef4444' }}>{critical} CRIT</span>}
          {offline > 0 && <span className="font-data text-[10px]" style={{ color: '#64748b' }}>{offline} OFF</span>}
        </div>
        <div className="flex items-center gap-3">
          <span className="font-data text-[10px]" style={{ color: 'oklch(0.55 0.015 230)' }}>
            {avgTemp.toFixed(1)}°C avg
          </span>
          <span className="font-data text-[10px]" style={{ color: 'oklch(0.55 0.015 230)' }}>
            {totalEnergy.toFixed(1)} kW
          </span>
        </div>
      </div>
    </div>
  );
}

export function BuildingOverview({ zones }: BuildingOverviewProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className="flex-shrink-0"
      style={{ borderTop: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.09 0.025 240)' }}
    >
      {/* Toggle header */}
      <button
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/5 transition-colors"
        onClick={() => setCollapsed(c => !c)}
      >
        <div className="flex items-center gap-2">
          <Activity size={11} style={{ color: '#60a5fa' }} />
          <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.50 0.015 230)' }}>
            Wing Overview
          </span>
        </div>
        {collapsed
          ? <ChevronUp size={12} style={{ color: 'oklch(0.45 0.015 230)' }} />
          : <ChevronDown size={12} style={{ color: 'oklch(0.45 0.015 230)' }} />
        }
      </button>

      {!collapsed && (
        <div className="flex gap-3 px-4 pb-3 max-w-[1600px] mx-auto w-full">
          {WING_ORDER.map(wing => (
            <WingCard
              key={wing}
              wing={wing}
              zones={zones.filter(z => z.wing === wing)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
