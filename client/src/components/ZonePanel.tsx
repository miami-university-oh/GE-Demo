/* ============================================================
   ZonePanel.tsx — Right-side data panel for selected zone
   Design: Aerospace HMI / SCADA Control Room
   - IBM Plex Mono for all sensor values
   - Recharts for sparklines and history
   - Status-coded metrics with live update animation
   ============================================================ */

import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { Zone } from '@/lib/buildingData';
import { STATUS_COLORS, STATUS_LABELS } from '@/lib/buildingData';
import {
  Activity,
  AlertTriangle,
  Building2,
  Cpu,
  Droplets,
  Flame,
  Gauge,
  Users,
  Wind,
  Wifi,
  X,
  Zap,
} from 'lucide-react';

interface ZonePanelProps {
  zone: Zone;
  onClose: () => void;
}

/**
 * Metric tile displaying an icon, label, monospace value with unit, and
 * an optional sub-text line. Re-triggers a CSS count-up animation
 * (`count-up` class) each time `value` changes by tracking the previous
 * value via a ref.
 *
 * @param icon  - Lucide icon component shown in the tile header.
 * @param label - Short uppercase descriptor.
 * @param value - Numeric or string value to display prominently.
 * @param unit  - Unit suffix displayed after the value (e.g. "°C").
 * @param color - Accent color for the icon and value text.
 * @param sub   - Optional secondary text line below the value.
 */
function MetricCard({
  icon: Icon,
  label,
  value,
  unit,
  color,
  sub,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  unit: string;
  color: string;
  sub?: string;
}) {
  const [animKey, setAnimKey] = useState(0);
  const prevVal = useRef(value);

  useEffect(() => {
    if (prevVal.current !== value) {
      setAnimKey(k => k + 1);
      prevVal.current = value;
    }
  }, [value]);

  return (
    <div
      className="panel-glow rounded p-3 flex flex-col gap-1"
      style={{ background: 'oklch(0.13 0.025 240)' }}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon size={11} style={{ color }} />
        <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
          {label}
        </span>
      </div>
      <div className="flex items-baseline gap-1">
        <span
          key={animKey}
          className="font-data text-xl font-semibold count-up"
          style={{ color }}
        >
          {value}
        </span>
        <span className="font-data text-xs" style={{ color: 'oklch(0.50 0.015 230)' }}>
          {unit}
        </span>
      </div>
      {sub && (
        <span className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
          {sub}
        </span>
      )}
    </div>
  );
}

/**
 * SVG 270° arc gauge that fills proportionally to `value / max`. The
 * track arc is rendered in a dark background color; the fill arc is
 * accented and glow-filtered. A percentage label is centered inside.
 *
 * @param value - Current metric value.
 * @param max   - Maximum expected value (maps to 100% fill).
 * @param color - Stroke and glow color for the filled arc.
 * @param label - Short label displayed below the gauge SVG.
 */
function RadialGauge({ value, max, color, label }: { value: number; max: number; color: string; label: string }) {
  const pct = Math.min(value / max, 1);
  const r = 22;
  const circ = 2 * Math.PI * r;
  const dash = pct * circ * 0.75; // 270° arc
  const rotation = -225; // start at bottom-left
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="56" height="56" viewBox="0 0 56 56">
        {/* Track */}
        <circle cx="28" cy="28" r={r} fill="none" stroke="oklch(0.18 0.025 240)" strokeWidth="4"
          strokeDasharray={`${circ * 0.75} ${circ * 0.25}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform={`rotate(${rotation} 28 28)`}
        />
        {/* Fill */}
        <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform={`rotate(${rotation} 28 28)`}
          style={{ filter: `drop-shadow(0 0 4px ${color}80)` }}
        />
        <text x="28" y="31" textAnchor="middle" fill={color} fontSize="10" fontWeight="700"
          style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
          {Math.round(pct * 100)}%
        </text>
      </svg>
      <span className="text-[9px] tracking-wider uppercase" style={{ color: 'oklch(0.50 0.015 230)' }}>{label}</span>
    </div>
  );
}

/**
 * Thin Recharts `AreaChart` sparkline with a gradient fill and a minimal
 * hover tooltip. Animation is disabled for live-data performance.
 *
 * @param data    - Array of data objects (zone history entries).
 * @param dataKey - Key in each data object to plot on the y-axis.
 * @param color   - Stroke color; also used for the gradient fill start.
 */
function Sparkline({ data, dataKey, color }: { data: any[]; dataKey: string; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={60}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#grad-${dataKey})`}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{
            background: 'oklch(0.12 0.025 240)',
            border: '1px solid oklch(0.65 0.18 220 / 30%)',
            borderRadius: '4px',
            fontSize: '10px',
            fontFamily: "'IBM Plex Mono', monospace",
            color: '#e2e8f0',
          }}
          labelFormatter={() => ''}
          formatter={(v: number) => [v.toFixed(1), dataKey]}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/**
 * Horizontal bar showing the online/total equipment ratio. The filled
 * portion is color-coded: green when >80 %, amber when >50 %, red
 * otherwise. The label above the bar shows the raw "online/total ONLINE"
 * counts.
 *
 * @param online - Number of equipment items currently online.
 * @param total  - Total number of equipment items in the zone.
 */
function EquipmentBar({ online, total }: { online: number; total: number }) {
  const pct = total > 0 ? (online / total) * 100 : 0;
  const color = pct > 80 ? '#22c55e' : pct > 50 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <span className="text-[10px] tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
          Equipment Status
        </span>
        <span className="font-data text-xs" style={{ color }}>
          {online}/{total} ONLINE
        </span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: 'oklch(0.18 0.025 240)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 6px ${color}60` }}
        />
      </div>
    </div>
  );
}

/**
 * Right-side detail panel for a selected building zone. Renders:
 * - A status/location header with zone name and description.
 * - A 2-column metric grid (temperature, humidity, CO₂, power, occupancy, AQI).
 * - A row of radial gauges (humidity, air quality, network, equipment).
 * - A network load progress bar.
 * - An equipment online/total bar.
 * - Three 60-minute sparkline trend charts (temperature, energy, CO₂).
 * - An active alerts list (shown only when alerts exist).
 * - A zone ID / timestamp footer.
 *
 * @param zone    - The zone whose data is displayed.
 * @param onClose - Callback invoked when the panel's close button is clicked.
 */
export function ZonePanel({ zone, onClose }: ZonePanelProps) {
  const statusColor = STATUS_COLORS[zone.status];
  const s = zone.sensors;

  const tempColor = s.temperature > 28 ? '#ef4444' : s.temperature > 25 ? '#f59e0b' : '#22c55e';
  const co2Color = s.co2 > 1000 ? '#ef4444' : s.co2 > 800 ? '#f59e0b' : '#22c55e';
  const humColor = s.humidity > 65 ? '#f59e0b' : '#60a5fa';

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: 'oklch(0.10 0.025 240)', fontFamily: "'Space Grotesk', sans-serif" }}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between p-4 pb-3"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)' }}
      >
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="text-[9px] font-data font-semibold tracking-widest px-1.5 py-0.5 rounded"
              style={{ background: `${statusColor}20`, color: statusColor, border: `1px solid ${statusColor}40` }}
            >
              ● {STATUS_LABELS[zone.status]}
            </span>
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>
              {zone.wing.toUpperCase()} WING · {zone.floor === 0 ? 'BASEMENT' : `FL${zone.floor}`}
            </span>
          </div>
          <h2 className="text-base font-bold leading-tight text-white truncate">
            {zone.name}
          </h2>
          <p className="text-[11px] leading-snug" style={{ color: 'oklch(0.55 0.015 230)' }}>
            {zone.description}
          </p>
        </div>
        <button
          onClick={onClose}
          className="ml-3 mt-0.5 p-1 rounded transition-colors hover:bg-white/10 flex-shrink-0"
          style={{ color: 'oklch(0.50 0.015 230)' }}
        >
          <X size={14} />
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">

        {/* Zone meta */}
        <div className="flex gap-3 text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
          <span className="flex items-center gap-1"><Building2 size={10} /> {zone.area} m²</span>
          <span className="flex items-center gap-1"><Cpu size={10} /> {zone.type.toUpperCase()}</span>
          <span className="flex items-center gap-1"><Activity size={10} /> LIVE</span>
          <span className="pulse-live flex items-center gap-1 text-green-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
            UPDATING
          </span>
        </div>

        {/* Primary metrics grid */}
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            icon={Flame}
            label="Temperature"
            value={s.temperature.toFixed(1)}
            unit="°C"
            color={tempColor}
            sub={s.temperature > 26 ? '↑ Above threshold' : 'Within range'}
          />
          <MetricCard
            icon={Droplets}
            label="Humidity"
            value={s.humidity.toFixed(1)}
            unit="%"
            color={humColor}
            sub={`${s.humidity > 65 ? 'High' : s.humidity < 35 ? 'Low' : 'Normal'} humidity`}
          />
          <MetricCard
            icon={Wind}
            label="CO₂ Level"
            value={Math.round(s.co2)}
            unit="ppm"
            color={co2Color}
            sub={s.co2 > 1000 ? 'Ventilation needed' : 'Air quality OK'}
          />
          <MetricCard
            icon={Zap}
            label="Power Draw"
            value={s.energyKw.toFixed(1)}
            unit="kW"
            color="#60a5fa"
            sub={`PF: ${s.powerFactor.toFixed(2)}`}
          />
          <MetricCard
            icon={Users}
            label="Occupancy"
            value={s.occupancy}
            unit="persons"
            color="#a78bfa"
          />
          <MetricCard
            icon={Gauge}
            label="Air Quality"
            value={Math.round(s.airQuality)}
            unit="AQI"
            color={s.airQuality > 100 ? '#f59e0b' : '#22c55e'}
            sub={s.airQuality < 50 ? 'Good' : s.airQuality < 100 ? 'Moderate' : 'Unhealthy'}
          />
        </div>

        {/* Radial gauges row */}
        <div
          className="panel-glow rounded p-3 flex items-center justify-around"
          style={{ background: 'oklch(0.13 0.025 240)' }}
        >
          <RadialGauge value={s.humidity} max={100} color={humColor} label="Humidity" />
          <RadialGauge value={s.airQuality} max={300} color={s.airQuality > 100 ? '#f59e0b' : '#22c55e'} label="Air Quality" />
          <RadialGauge value={s.networkLoad} max={100} color="#60a5fa" label="Network" />
          <RadialGauge value={(s.equipmentOnline / s.equipmentTotal) * 100} max={100} color="#a78bfa" label="Equipment" />
        </div>

        {/* Network load */}
        <div className="panel-glow rounded p-3" style={{ background: 'oklch(0.13 0.025 240)' }}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Wifi size={11} style={{ color: '#60a5fa' }} />
              <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
                Network Load
              </span>
            </div>
            <span className="font-data text-sm font-semibold" style={{ color: '#60a5fa' }}>
              {s.networkLoad.toFixed(1)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full" style={{ background: 'oklch(0.18 0.025 240)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${s.networkLoad}%`,
                background: s.networkLoad > 80 ? '#ef4444' : '#3b82f6',
                boxShadow: `0 0 6px ${s.networkLoad > 80 ? '#ef444460' : '#3b82f660'}`,
              }}
            />
          </div>
        </div>

        {/* Equipment status */}
        <div className="panel-glow rounded p-3" style={{ background: 'oklch(0.13 0.025 240)' }}>
          <EquipmentBar online={s.equipmentOnline} total={s.equipmentTotal} />
        </div>

        {/* Temperature history sparkline */}
        <div className="panel-glow rounded p-3" style={{ background: 'oklch(0.13 0.025 240)' }}>
          <div className="flex items-center gap-1.5 mb-2">
            <Flame size={11} style={{ color: tempColor }} />
            <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
              Temperature Trend (60 min)
            </span>
          </div>
          <Sparkline data={zone.history} dataKey="temperature" color={tempColor} />
        </div>

        {/* Energy history sparkline */}
        <div className="panel-glow rounded p-3" style={{ background: 'oklch(0.13 0.025 240)' }}>
          <div className="flex items-center gap-1.5 mb-2">
            <Zap size={11} style={{ color: '#60a5fa' }} />
            <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
              Power Consumption (60 min)
            </span>
          </div>
          <Sparkline data={zone.history} dataKey="energyKw" color="#60a5fa" />
        </div>

        {/* CO2 history sparkline */}
        <div className="panel-glow rounded p-3" style={{ background: 'oklch(0.13 0.025 240)' }}>
          <div className="flex items-center gap-1.5 mb-2">
            <Wind size={11} style={{ color: co2Color }} />
            <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
              CO₂ Trend (60 min)
            </span>
          </div>
          <Sparkline data={zone.history} dataKey="co2" color={co2Color} />
        </div>

        {/* Active alerts */}
        {zone.alerts.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={11} style={{ color: '#f59e0b' }} />
              <span className="text-[10px] font-semibold tracking-widest uppercase" style={{ color: 'oklch(0.55 0.015 230)' }}>
                Active Alerts ({zone.alerts.length})
              </span>
            </div>
            {zone.alerts.map(alert => (
              <div
                key={alert.id}
                className="rounded p-2.5 flex items-start gap-2"
                style={{
                  background: alert.severity === 'critical' ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)',
                  border: `1px solid ${alert.severity === 'critical' ? 'rgba(239,68,68,0.30)' : 'rgba(245,158,11,0.30)'}`,
                }}
              >
                <AlertTriangle
                  size={11}
                  className="mt-0.5 flex-shrink-0"
                  style={{ color: alert.severity === 'critical' ? '#ef4444' : '#f59e0b' }}
                />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-[11px] font-medium text-white">{alert.message}</span>
                  <span className="text-[9px] font-data" style={{ color: 'oklch(0.50 0.015 230)' }}>
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Zone ID footer */}
        <div className="hairline pt-3 flex justify-between items-center">
          <span className="font-data text-[9px]" style={{ color: 'oklch(0.35 0.015 230)' }}>
            ZONE ID: {zone.id}
          </span>
          <span className="font-data text-[9px]" style={{ color: 'oklch(0.35 0.015 230)' }}>
            {new Date().toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}
