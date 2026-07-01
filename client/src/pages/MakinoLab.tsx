/* ============================================================
   MakinoLab.tsx — Makino Lab Deep-Dive View
   Area M / Grid 14 — Advanced Manufacturing Hub
   Sections:
     - Lab floor map with equipment positions
     - 3× Equipment data panels (Haas VF-2SS, Haas ST-10, UR5e)
     - 2× YOLO camera tiles (Overview, Cobot)
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Area, AreaChart, ResponsiveContainer, Tooltip,
} from 'recharts';
import {
  Activity, AlertTriangle, ArrowLeft, ChevronDown, ChevronRight,
  Cpu, Gauge, RotateCcw, Settings, Shield, Thermometer, Zap,
} from 'lucide-react';
import { equipmentStore, MACHINE_STATUS_COLOR, MACHINE_STATUS_LABEL } from '@/lib/equipmentData';
import type { HaasVMCData, HaasLathData, UR5eData, MakinoA51nxData, MakinoD200ZData, MakinoPS95Data, BridgeStatus } from '@/lib/equipmentData';
import { cameraStore } from '@/lib/cameraData';
import type { YOLOCameraData } from '@/lib/cameraData';
import { CameraTile } from '@/components/CameraTile';

// ── Machine image assets ─────────────────────────────────────
const MACHINE_IMAGES = {
  'haas-tl1':      'https://d2xsxph8kpxj0f.cloudfront.net/310419663028680363/Ep5djjbvyvd9aLWmbyfucZ/haas-st10-NoauKRWTg4JzNbQQiA778S.webp',
  'ur5e':          'https://d2xsxph8kpxj0f.cloudfront.net/310419663028680363/Ep5djjbvyvd9aLWmbyfucZ/ur5e-cobot-7aBoZbEnZTkZY7DyrwCnCd.webp',
  'makino-a51nx':  'https://d2xsxph8kpxj0f.cloudfront.net/310419663028680363/Ep5djjbvyvd9aLWmbyfucZ/makino-a51nx-HeAyWYY3UNa9PmSVq4ohJF.webp',
  'makino-d200z':  'https://d2xsxph8kpxj0f.cloudfront.net/310419663028680363/Ep5djjbvyvd9aLWmbyfucZ/makino-d200z-jWNxSjJvPHARomNF9XebYS.webp',
  'makino-ps95':   'https://d2xsxph8kpxj0f.cloudfront.net/310419663028680363/Ep5djjbvyvd9aLWmbyfucZ/makino-ps95-7oCUpHpPpMKhAUKk6LXzBf.webp',
};

// ── Machine image banner sub-component ───────────────────────
/**
 * Renders a hero image banner for a machine with an animated status pill
 * overlay. Shows the machine photo cropped to 160 px height with a dark
 * gradient overlay. The status pill displays "SIMULATED" when the bridge
 * is not live, or the actual status string when live data is available.
 *
 * @param id           - Machine identifier key matching `MACHINE_IMAGES`.
 * @param name         - Display name shown at the bottom of the banner.
 * @param status       - Current machine status (e.g. "running", "idle").
 * @param statusColor  - CSS color for the status pill accent.
 * @param bridgeStatus - WebSocket bridge connection state; omit for always-live.
 */
function MachineBanner({ id, name, status, statusColor, bridgeStatus }: { id: string; name: string; status: string; statusColor: string; bridgeStatus?: string }) {
  const src = MACHINE_IMAGES[id as keyof typeof MACHINE_IMAGES];
  if (!src) return null;
  const isLive = bridgeStatus === 'live';
  const pillColor = isLive ? statusColor : '#6b7280';
  const pillLabel = isLive ? String(status ?? '').toUpperCase() : 'SIMULATED';
  return (
    <div className="relative overflow-hidden" style={{ height: 160 }}>
      <img
        src={src}
        alt={name}
        className="w-full h-full object-cover"
        style={{ objectPosition: 'center 30%' }}
      />
      {/* Dark gradient overlay at bottom */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(to bottom, transparent 30%, oklch(0.10 0.025 240) 100%)' }}
      />
      {/* Status pill overlay */}
      <div className="absolute top-2 right-2">
        <motion.span
          animate={isLive && status === 'running' ? { opacity: [1, 0.5, 1] } : {}}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="text-[9px] font-bold tracking-widest px-2 py-0.5 rounded"
          style={{ background: `${pillColor}22`, color: pillColor, border: `1px solid ${pillColor}50`, backdropFilter: 'blur(4px)' }}
        >
          ● {pillLabel}
        </motion.span>
      </div>
      {/* Machine name overlay at bottom */}
      <div className="absolute bottom-2 left-3">
        <span className="text-xs font-bold text-white" style={{ textShadow: '0 1px 4px rgba(0,0,0,0.8)' }}>{name}</span>
      </div>
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────

/**
 * Renders a single label–value row with an optional unit suffix and
 * accent color. A faint bottom border separates consecutive rows.
 *
 * @param label - Human-readable row label.
 * @param value - Numeric or string value to display.
 * @param unit  - Optional unit string appended after the value.
 * @param color - Optional accent color for the value text.
 */
function DataRow({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1" style={{ borderBottom: '1px solid oklch(1 0 0 / 5%)' }}>
      <span className="text-[10px] tracking-wide" style={{ color: 'oklch(0.55 0.015 230)' }}>{label}</span>
      <span className="font-data text-[11px] font-semibold" style={{ color: color || '#e2e8f0' }}>
        {value}{unit && <span className="text-[9px] ml-0.5" style={{ color: 'oklch(0.50 0.015 230)' }}>{unit}</span>}
      </span>
    </div>
  );
}

/**
 * Renders a compact 36 px Recharts `AreaChart` sparkline with a gradient
 * fill and a minimal tooltip. Used inside machine panels to show recent
 * history for a single metric.
 *
 * @param data    - Array of data objects (e.g. equipment history records).
 * @param dataKey - Key of the numeric field to plot.
 * @param color   - Stroke and gradient accent color.
 */
function MiniSparkline({ data, dataKey, color }: { data: any[]; dataKey: string; color: string }) {
  return (
    <ResponsiveContainer width="100%" height={36}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`mg-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5}
          fill={`url(#mg-${dataKey})`} dot={false} isAnimationActive={false} />
        <Tooltip
          contentStyle={{ background: 'oklch(0.12 0.025 240)', border: 'none', fontSize: 9, fontFamily: "'IBM Plex Mono'" }}
          labelFormatter={() => ''} formatter={(v: number) => [v.toFixed(1), dataKey]}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/**
 * Renders an animated status badge pill. When the bridge is live and the
 * machine is running, the badge pulses. Shows "SIM" in grey when the bridge
 * is offline (simulated data).
 *
 * @param status       - Machine status key (e.g. "running", "alarm").
 * @param bridgeStatus - Optional bridge connection state; defaults to treating as live.
 */
function StatusBadge({ status, bridgeStatus }: { status: string; bridgeStatus?: string }) {
  const isLive = bridgeStatus === 'live' || bridgeStatus === undefined;
  const color = isLive
    ? (MACHINE_STATUS_COLOR[status as keyof typeof MACHINE_STATUS_COLOR] || '#6b7280')
    : '#6b7280';
  const label = isLive
    ? (MACHINE_STATUS_LABEL[status as keyof typeof MACHINE_STATUS_LABEL] || status)
    : 'SIM';
  return (
    <motion.span
      animate={isLive && status === 'running' ? { opacity: [1, 0.6, 1] } : {}}
      transition={{ duration: 1.5, repeat: Infinity }}
      className="text-[9px] font-bold tracking-widest px-2 py-0.5 rounded"
      style={{ background: `${color}18`, color, border: `1px solid ${color}40` }}
    >
      ● {label}
    </motion.span>
  );
}

/**
 * Renders a labeled progress bar showing how far through the current cycle
 * the machine is. Both `current` and `total` are in seconds and are
 * formatted as `M:SS` above the bar.
 *
 * @param current - Elapsed cycle time in seconds.
 * @param total   - Total expected cycle time in seconds.
 * @param color   - Accent color for the progress bar fill and glow.
 */
function CycleProgress({ current, total, color }: { current: number; total: number; color: string }) {
  const pct = total > 0 ? (current / total) * 100 : 0;
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-[9px]">
        <span style={{ color: 'oklch(0.50 0.015 230)' }}>Cycle Progress</span>
        <span className="font-data" style={{ color }}>{fmt(current)} / {fmt(total)}</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: 'oklch(0.18 0.025 240)' }}>
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 6px ${color}60` }} />
      </div>
    </div>
  );
}

/**
 * Renders a list of active alarm strings as red-accented rows. Returns
 * `null` when the `alarms` array is empty.
 *
 * @param alarms - Array of alarm description strings.
 */
function AlarmList({ alarms }: { alarms: string[] }) {
  if (!alarms.length) return null;
  return (
    <div className="flex flex-col gap-1 mt-1">
      {alarms.map((a, i) => (
        <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded"
          style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.25)' }}>
          <AlertTriangle size={9} style={{ color: '#ef4444', flexShrink: 0 }} />
          <span className="text-[9px] font-semibold" style={{ color: '#fca5a5' }}>{a}</span>
        </div>
      ))}
    </div>
  );
}

// ── Haas VF-2SS Panel ─────────────────────────────────────────

/**
 * Collapsible data panel for the Haas VF-2SS Vertical Machining Centre.
 * Displays spindle RPM/load, axis positions, feed/rapid overrides, coolant
 * state, active tool, cycle progress, power draw, and active alarms.
 *
 * @param data - Live or simulated Haas VMC telemetry.
 */
function VMCPanel({ data }: { data: HaasVMCData }) {
  const [open, setOpen] = useState(true);
  const sc = MACHINE_STATUS_COLOR[data.status];

  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}25` }}>
      {/* Machine image banner */}
      <MachineBanner id={data.id} name={data.name} status={data.status} statusColor={sc} />
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
        style={{ borderBottom: open ? '1px solid oklch(1 0 0 / 8%)' : 'none' }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded flex items-center justify-center"
            style={{ background: `${sc}15`, border: `1px solid ${sc}30` }}>
            <Settings size={14} style={{ color: sc }} />
          </div>
          <div className="text-left">
            <div className="text-sm font-bold text-white">{data.name}</div>
            <div className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              Vertical Machining Center · Area M
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={data.status} />
          <span className="font-data text-xs font-semibold" style={{ color: '#60a5fa' }}>
            {data.powerKw.toFixed(1)} kW
          </span>
          {open ? <ChevronDown size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />
                : <ChevronRight size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </button>

      {open && (
        <div className="p-4 flex flex-col gap-4">
          {/* Program */}
          <div className="flex items-center gap-2 px-2 py-1.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <Cpu size={10} style={{ color: '#60a5fa' }} />
            <span className="font-data text-[10px]" style={{ color: '#93c5fd' }}>PROG:</span>
            <span className="font-data text-[10px] font-semibold text-white">{data.program}</span>
            <span className="ml-auto font-data text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              T{String(data.toolNumber).padStart(2, '0')}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Left: Spindle + Feed */}
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Spindle & Feed
              </span>
              <DataRow label="Spindle RPM" value={data.spindleRpm.toLocaleString()} color="#22c55e" />
              <DataRow label="Spindle Load" value={data.spindleLoad.toFixed(1)} unit="%" color={data.spindleLoad > 80 ? '#ef4444' : '#22c55e'} />
              <DataRow label="Feed Rate" value={data.feedRate.toLocaleString()} unit="mm/min" />
              <DataRow label="Feed Override" value={data.feedOverride} unit="%" />
              <DataRow label="Rapid Override" value={data.rapidOverride} unit="%" />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="rpm" color="#22c55e" />
              </div>
            </div>

            {/* Right: Position + Coolant */}
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Axis Position (mm)
              </span>
              <DataRow label="X Axis" value={data.position.x.toFixed(2)} color="#60a5fa" />
              <DataRow label="Y Axis" value={data.position.y.toFixed(2)} color="#a78bfa" />
              <DataRow label="Z Axis" value={data.position.z.toFixed(2)} color="#f472b6" />
              <DataRow label="Coolant Temp" value={data.coolantTemp.toFixed(1)} unit="°C" color={data.coolantTemp > 30 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Coolant Level" value={data.coolantLevel.toFixed(0)} unit="%" color={data.coolantLevel < 30 ? '#ef4444' : '#22c55e'} />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="power" color="#60a5fa" />
              </div>
            </div>
          </div>

          {/* Tool wear + cycle */}
          <div className="flex flex-col gap-2 px-3 py-2.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <div className="flex justify-between items-center">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Tool T{String(data.toolNumber).padStart(2, '0')} Wear
              </span>
              <span className="font-data text-xs font-bold" style={{ color: data.toolWear > 80 ? '#ef4444' : data.toolWear > 60 ? '#f59e0b' : '#22c55e' }}>
                {data.toolWear.toFixed(1)}%
              </span>
            </div>
            <div className="h-1.5 rounded-full" style={{ background: 'oklch(0.18 0.025 240)' }}>
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${data.toolWear}%`, background: data.toolWear > 80 ? '#ef4444' : data.toolWear > 60 ? '#f59e0b' : '#22c55e' }} />
            </div>
            <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#60a5fa" />
            <div className="flex justify-between text-[9px] mt-0.5">
              <span style={{ color: 'oklch(0.50 0.015 230)' }}>Parts Complete</span>
              <span className="font-data font-bold text-white">{data.partsComplete} / {data.partsTarget}</span>
            </div>
          </div>

          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}

// ── Training Panel ────────────────────────────────────────────

const TRAINING_CLIPS = [
  { src: '/videos/vr-demo.mp4',      title: 'VR Demo' },
  { src: '/videos/chip-removal.mp4', title: 'Chip Removal' },
  { src: '/videos/demo1.mp4',        title: 'Demo — Nov 19' },
];

/**
 * Collapsible panel listing embedded training video clips for the Makino
 * Lab. Videos are rendered as `<video>` elements with controls.
 */
function TrainingPanel() {
  const [open, setOpen] = useState(true);
  const accent = '#f472b6';

  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${accent}25` }}>
      {/* Header row — matches LathePanel / CobotPanel style */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
        style={{ borderBottom: open ? '1px solid oklch(1 0 0 / 8%)' : 'none' }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded flex items-center justify-center"
            style={{ background: `${accent}15`, border: `1px solid ${accent}30` }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill={accent}><path d="M8 5v14l11-7z"/></svg>
          </div>
          <div className="text-left">
            <div className="text-sm font-bold text-white">Training Videos</div>
            <div className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              Makino Lab · 3 clips
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded"
            style={{ background: `${accent}15`, color: accent, border: `1px solid ${accent}35` }}>
            {TRAINING_CLIPS.length} VIDEOS
          </span>
          {open ? <ChevronDown size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />
                : <ChevronRight size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </button>

      {open && (
        <div className="grid grid-cols-3" style={{ borderTop: '1px solid oklch(1 0 0 / 6%)' }}>
          {TRAINING_CLIPS.map(({ src, title }, i) => (
            <div key={src} style={{ borderRight: i < 2 ? '1px solid oklch(1 0 0 / 8%)' : 'none' }}>
              <div className="flex items-center gap-2 px-3 py-2"
                style={{ background: 'oklch(0.12 0.025 240)', borderBottom: '1px solid oklch(1 0 0 / 8%)' }}>
                <svg width="9" height="9" viewBox="0 0 24 24" fill={accent}><path d="M8 5v14l11-7z"/></svg>
                <span className="text-[10px] font-semibold tracking-wide" style={{ color: accent }}>{title}</span>
              </div>
              <video
                src={src}
                controls
                playsInline
                className="w-full block"
                style={{ maxHeight: '260px', background: '#000' }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Haas ST-10 Panel ──────────────────────────────────────────

/**
 * Collapsible data panel for the Haas TL-1 CNC Lathe.
 * Displays spindle RPM/load, X/Z axis positions, chuck pressure, CSS mode,
 * coolant temperature, active tool, cycle progress, and active alarms.
 * Shows a "SIMULATED" badge when the Haas bridge WebSocket is not live.
 *
 * @param data         - Live or simulated Haas lathe telemetry.
 * @param bridgeStatus - WebSocket bridge connection state.
 */
function LathePanel({ data, bridgeStatus }: { data: HaasLathData; bridgeStatus?: string }) {
  const [open, setOpen] = useState(true);
  const sc = MACHINE_STATUS_COLOR[data.status];

  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}25` }}>
      {/* Machine image banner */}
      <MachineBanner id={data.id} name={data.name} status={data.status} statusColor={sc} bridgeStatus={bridgeStatus} />
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
        style={{ borderBottom: open ? '1px solid oklch(1 0 0 / 8%)' : 'none' }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded flex items-center justify-center"
            style={{ background: `${sc}15`, border: `1px solid ${sc}30` }}>
            <RotateCcw size={14} style={{ color: sc }} />
          </div>
          <div className="text-left">
            <div className="text-sm font-bold text-white">{data.name}</div>
            <div className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              CNC Lathe · Area M
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={data.status} bridgeStatus={bridgeStatus} />
          <span className="font-data text-xs font-semibold" style={{ color: '#60a5fa' }}>
            {data.powerKw.toFixed(1)} kW
          </span>
          {open ? <ChevronDown size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />
                : <ChevronRight size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </button>

      {open && (
        <div className="p-4 flex flex-col gap-4">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <Cpu size={10} style={{ color: '#60a5fa' }} />
            <span className="font-data text-[10px]" style={{ color: '#93c5fd' }}>PROG:</span>
            <span className="font-data text-[10px] font-semibold text-white">{data.program}</span>
            <span className="ml-auto font-data text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              Station {data.toolStation}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Spindle
              </span>
              <DataRow label="Spindle RPM" value={data.spindleRpm.toLocaleString()} color="#22c55e" />
              <DataRow label="Spindle Load" value={data.spindleLoad.toFixed(1)} unit="%" color={data.spindleLoad > 80 ? '#ef4444' : '#22c55e'} />
              <DataRow label="Spindle Override" value={String(data.spindleOverride ?? 100)} unit="%" color={data.spindleOverride < 100 ? '#f59e0b' : '#22c55e'} />
              <DataRow label="Feed Rate" value={data.feedRate.toFixed(3)} unit="mm/rev" />
              <DataRow label="CSS Mode" value={data.cssMode ? `ON · ${data.cssTarget}m/min` : 'OFF'} color={data.cssMode ? '#22c55e' : '#6b7280'} />
              <DataRow label="Chuck Pressure" value={data.chuckPressure.toFixed(2)} unit="bar" color={data.chuckPressure < 2.8 ? '#ef4444' : '#22c55e'} />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="rpm" color="#22c55e" />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Position (mm)
              </span>
              <DataRow label="X Axis" value={data.position.x.toFixed(2)} color="#60a5fa" />
              <DataRow label="Z Axis" value={data.position.z.toFixed(2)} color="#a78bfa" />
              <DataRow label="X Axis Load" value={String(data.xAxisLoad ?? 0)} unit="%" color={(data.xAxisLoad ?? 0) > 80 ? '#ef4444' : '#60a5fa'} />
              <DataRow label="Z Axis Load" value={String(data.zAxisLoad ?? 0)} unit="%" color={(data.zAxisLoad ?? 0) > 80 ? '#ef4444' : '#a78bfa'} />
              <DataRow label="Coolant Temp" value={data.coolantTemp.toFixed(1)} unit="°C" color={data.coolantTemp > 30 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Tool Wear" value={data.toolWear.toFixed(1)} unit="%" color={data.toolWear > 80 ? '#ef4444' : '#22c55e'} />
              <DataRow label="Power Draw" value={data.powerKw.toFixed(2)} unit="kW" color="#60a5fa" />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="load" color="#a78bfa" />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2 px-3 py-2.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#a78bfa" />
            <div className="flex justify-between text-[9px] mt-0.5">
              <span style={{ color: 'oklch(0.50 0.015 230)' }}>Parts Complete</span>
              <span className="font-data font-bold text-white">{data.partsComplete} / {data.partsTarget}</span>
            </div>
          </div>

          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}

// ── UR5e Cobot Panel ──────────────────────────────────────────

/**
 * Collapsible data panel for the Universal Robots UR5e cobot.
 * Displays robot mode, safety status, TCP position and speed, all six
 * joint angles, payload, collaborative mode state, cycle metrics,
 * power draw, and active safety alarms.
 * Shows a "SIMULATED" badge when the UR5e bridge WebSocket is not live.
 *
 * @param data         - Live or simulated UR5e telemetry.
 * @param bridgeStatus - WebSocket bridge connection state.
 */
function CobotPanel({ data, bridgeStatus }: { data: UR5eData; bridgeStatus?: string }) {
  const [open, setOpen] = useState(true);
  const sc = MACHINE_STATUS_COLOR[data.status];
  const safetyColor = data.safetyStatus === 'normal' ? '#22c55e'
    : data.safetyStatus === 'reduced' ? '#f59e0b' : '#ef4444';

  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}25` }}>
      {/* Machine image banner */}
      <MachineBanner id={data.id} name={data.name} status={data.status} statusColor={sc} bridgeStatus={bridgeStatus} />
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
        style={{ borderBottom: open ? '1px solid oklch(1 0 0 / 8%)' : 'none' }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded flex items-center justify-center"
            style={{ background: `${sc}15`, border: `1px solid ${sc}30` }}>
            <Activity size={14} style={{ color: sc }} />
          </div>
          <div className="text-left">
            <div className="text-sm font-bold text-white">{data.name}</div>
            <div className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              Collaborative Robot Arm · Grid 14
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={data.status} bridgeStatus={bridgeStatus} />
          <span
            className="text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded"
            style={{ background: `${safetyColor}15`, color: safetyColor, border: `1px solid ${safetyColor}35` }}
          >
            {String(data.safetyStatus ?? '').replace('_', ' ').toUpperCase()}
          </span>
          {open ? <ChevronDown size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />
                : <ChevronRight size={13} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </button>

      {open && (
        <div className="p-4 flex flex-col gap-4">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <Cpu size={10} style={{ color: '#fb923c' }} />
            <span className="font-data text-[10px]" style={{ color: '#fdba74' }}>PROG:</span>
            <span className="font-data text-[10px] font-semibold text-white">{data.program}</span>
            <span className="ml-auto font-data text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              {String(data.mode ?? '').toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* TCP + Safety */}
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                TCP Position (mm)
              </span>
              <DataRow label="X" value={data.tcpPosition.x.toFixed(1)} color="#60a5fa" />
              <DataRow label="Y" value={data.tcpPosition.y.toFixed(1)} color="#a78bfa" />
              <DataRow label="Z" value={data.tcpPosition.z.toFixed(1)} color="#f472b6" />
              <DataRow label="TCP Speed" value={data.tcpSpeed.toFixed(1)} unit="mm/s" color="#22c55e" />
              <DataRow label="Payload" value={data.payload.toFixed(2)} unit={`/ ${data.payloadMax} kg`} color="#fb923c" />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="tcpSpeed" color="#22c55e" />
              </div>
            </div>

            {/* Safety + System */}
            <div className="flex flex-col gap-2">
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
                Safety & System
              </span>
              <DataRow label="Human Proximity"
                value={data.humanProximity}
                unit="cm"
                color={data.humanProximity < 50 ? '#ef4444' : data.humanProximity < 100 ? '#f59e0b' : '#22c55e'}
              />
              <DataRow label="Collab Mode" value={data.collaborativeMode ? 'ENABLED' : 'DISABLED'} color={data.collaborativeMode ? '#22c55e' : '#6b7280'} />
              <DataRow label="Controller Temp" value={data.temperature.toFixed(1)} unit="°C" color={data.temperature > 50 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Power Draw" value={data.powerKw.toFixed(3)} unit="kW" color="#60a5fa" />
              <DataRow label="Cycles Done" value={data.cyclesComplete} />
              <div className="mt-1">
                <MiniSparkline data={data.history} dataKey="power" color="#fb923c" />
              </div>
            </div>
          </div>

          {/* Joint angles */}
          <div className="flex flex-col gap-2 px-3 py-2.5 rounded"
            style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <span className="text-[9px] tracking-widest uppercase font-semibold mb-1" style={{ color: 'oklch(0.40 0.015 230)' }}>
              Joint Angles & Torque
            </span>
            <div className="grid grid-cols-3 gap-x-4 gap-y-1">
              {data.joints.map(j => (
                <div key={j.id} className="flex flex-col">
                  <span className="text-[8px] tracking-wider" style={{ color: 'oklch(0.45 0.015 230)' }}>{j.label}</span>
                  <div className="flex items-baseline gap-1">
                    <span className="font-data text-[10px] font-semibold" style={{ color: '#fb923c' }}>
                      {j.angle.toFixed(1)}°
                    </span>
                    <span className="font-data text-[8px]" style={{ color: 'oklch(0.45 0.015 230)' }}>
                      {j.torque.toFixed(1)}Nm
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#fb923c" />
          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}


// ── Makino a51nx Panel ───────────────────────────────────────────

/**
 * Collapsible data panel for the Makino a51nx Horizontal Machining Centre.
 * Displays spindle RPM/load, axis positions, overrides, pallet status,
 * coolant, tool wear, cycle progress, parts count, and active alarms.
 *
 * @param data - Live or simulated Makino a51nx telemetry.
 */
function MakinoA51nxPanel({ data }: { data: MakinoA51nxData }) {
  const sc = MACHINE_STATUS_COLOR[data.status];
  const sl = MACHINE_STATUS_LABEL[data.status];
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}30` }}>
      <MachineBanner id="makino-a51nx" name={data.name} status={sl} statusColor={sc} />
      <div className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.12 0.025 240)' }}
        onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-2">
          <Cpu size={11} style={{ color: '#34d399' }} />
          <span className="text-[11px] font-bold text-white tracking-wide">{data.name}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'oklch(0.18 0.025 240)', color: 'oklch(0.55 0.015 230)' }}>{data.type}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-data text-[9px] tracking-wider" style={{ color: 'oklch(0.45 0.015 230)' }}>{data.program}</span>
          {open ? <ChevronDown size={10} style={{ color: 'oklch(0.45 0.015 230)' }} /> : <ChevronRight size={10} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </div>
      {open && (
        <div className="flex flex-col gap-2 p-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Spindle</span>
              <DataRow label="RPM" value={data.spindleRpm.toLocaleString()} color="#34d399" />
              <DataRow label="Load" value={data.spindleLoad.toFixed(1)} unit="%" color={data.spindleLoad > 80 ? '#f59e0b' : '#34d399'} />
              <DataRow label="Feed Rate" value={data.feedRate.toLocaleString()} unit="mm/min" color="#60a5fa" />
              <DataRow label="Tool #" value={`T${String(data.toolNumber).padStart(2,'0')}`} color="#a78bfa" />
              <DataRow label="Tool Wear" value={data.toolWear.toFixed(1)} unit="%" color={data.toolWear > 75 ? '#ef4444' : data.toolWear > 50 ? '#f59e0b' : '#22c55e'} />
            </div>
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Pallet & Axes</span>
              <DataRow label="Pallet" value={`P${data.palletId}`} color={data.palletStatus === 'machining' ? '#34d399' : '#f59e0b'} />
              <DataRow label="Status" value={String(data.palletStatus ?? '').toUpperCase()} color={data.palletStatus === 'machining' ? '#34d399' : '#f59e0b'} />
              <DataRow label="X" value={data.position.x.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Y" value={data.position.y.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Z" value={data.position.z.toFixed(2)} unit="mm" color="#60a5fa" />
            </div>
          </div>
          <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Coolant & Power</span>
            <div className="grid grid-cols-2 gap-x-4">
              <DataRow label="Coolant Temp" value={data.coolantTemp.toFixed(1)} unit="°C" color={data.coolantTemp > 32 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Coolant Level" value={data.coolantLevel.toFixed(0)} unit="%" color={data.coolantLevel < 30 ? '#ef4444' : '#22c55e'} />
              <DataRow label="Power Draw" value={data.powerKw.toFixed(2)} unit="kW" color="#60a5fa" />
              <DataRow label="Parts" value={`${data.partsComplete} / ${data.partsTarget}`} color="#34d399" />
            </div>
            <MiniSparkline data={data.history} dataKey="rpm" color="#34d399" />
          </div>
          <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#34d399" />
          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}

// ── Makino d200Z Panel ───────────────────────────────────────────

/**
 * Collapsible data panel for the Makino d200Z 5-Axis VMC.
 * Displays spindle RPM/load, X/Y/Z/A/C axis positions and tilt/rotary
 * angles, overrides, tool wear, coolant temperature, cycle progress,
 * parts count, and active alarms.
 *
 * @param data - Live or simulated Makino d200Z telemetry.
 */
function MakinoD200ZPanel({ data }: { data: MakinoD200ZData }) {
  const sc = MACHINE_STATUS_COLOR[data.status];
  const sl = MACHINE_STATUS_LABEL[data.status];
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}30` }}>
      <MachineBanner id="makino-d200z" name={data.name} status={sl} statusColor={sc} />
      <div className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.12 0.025 240)' }}
        onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-2">
          <RotateCcw size={11} style={{ color: '#a78bfa' }} />
          <span className="text-[11px] font-bold text-white tracking-wide">{data.name}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'oklch(0.18 0.025 240)', color: 'oklch(0.55 0.015 230)' }}>{data.type}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-data text-[9px] tracking-wider" style={{ color: 'oklch(0.45 0.015 230)' }}>{data.program}</span>
          {open ? <ChevronDown size={10} style={{ color: 'oklch(0.45 0.015 230)' }} /> : <ChevronRight size={10} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </div>
      {open && (
        <div className="flex flex-col gap-2 p-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Spindle</span>
              <DataRow label="RPM" value={data.spindleRpm.toLocaleString()} color="#a78bfa" />
              <DataRow label="Load" value={data.spindleLoad.toFixed(1)} unit="%" color={data.spindleLoad > 80 ? '#f59e0b' : '#a78bfa'} />
              <DataRow label="Feed Rate" value={data.feedRate.toLocaleString()} unit="mm/min" color="#60a5fa" />
              <DataRow label="Tool #" value={`T${String(data.toolNumber).padStart(2,'0')}`} color="#f472b6" />
              <DataRow label="Tool Wear" value={data.toolWear.toFixed(1)} unit="%" color={data.toolWear > 70 ? '#ef4444' : data.toolWear > 45 ? '#f59e0b' : '#22c55e'} />
            </div>
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>5-Axis Position</span>
              <DataRow label="X" value={data.position.x.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Y" value={data.position.y.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Z" value={data.position.z.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="A (Tilt)" value={data.tiltAngle.toFixed(1)} unit="°" color="#a78bfa" />
              <DataRow label="C (Rotary)" value={data.rotaryAngle.toFixed(1)} unit="°" color="#a78bfa" />
            </div>
          </div>
          <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Coolant & Power</span>
            <div className="grid grid-cols-2 gap-x-4">
              <DataRow label="Coolant Temp" value={data.coolantTemp.toFixed(1)} unit="°C" color={data.coolantTemp > 32 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Power Draw" value={data.powerKw.toFixed(2)} unit="kW" color="#60a5fa" />
              <DataRow label="Parts" value={`${data.partsComplete} / ${data.partsTarget}`} color="#a78bfa" />
            </div>
            <MiniSparkline data={data.history} dataKey="rpm" color="#a78bfa" />
          </div>
          <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#a78bfa" />
          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}

// ── Makino PS95 Panel ────────────────────────────────────────────

/**
 * Collapsible data panel for the Makino PS95 Precision VMC.
 * Displays spindle RPM/load, axis positions, overrides, coolant state,
 * tool wear, cycle progress, parts count, and active alarms.
 *
 * @param data - Live or simulated Makino PS95 telemetry.
 */
function MakinoPS95Panel({ data }: { data: MakinoPS95Data }) {
  const sc = MACHINE_STATUS_COLOR[data.status];
  const sl = MACHINE_STATUS_LABEL[data.status];
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: `1px solid ${sc}30` }}>
      <MachineBanner id="makino-ps95" name={data.name} status={sl} statusColor={sc} />
      <div className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.12 0.025 240)' }}
        onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-2">
          <Gauge size={11} style={{ color: '#f59e0b' }} />
          <span className="text-[11px] font-bold text-white tracking-wide">{data.name}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'oklch(0.18 0.025 240)', color: 'oklch(0.55 0.015 230)' }}>{data.type}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-data text-[9px] tracking-wider" style={{ color: 'oklch(0.45 0.015 230)' }}>{data.program}</span>
          {open ? <ChevronDown size={10} style={{ color: 'oklch(0.45 0.015 230)' }} /> : <ChevronRight size={10} style={{ color: 'oklch(0.45 0.015 230)' }} />}
        </div>
      </div>
      {open && (
        <div className="flex flex-col gap-2 p-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Spindle</span>
              <DataRow label="RPM" value={data.spindleRpm.toLocaleString()} color="#f59e0b" />
              <DataRow label="Load" value={data.spindleLoad.toFixed(1)} unit="%" color={data.spindleLoad > 80 ? '#ef4444' : '#f59e0b'} />
              <DataRow label="Feed Rate" value={data.feedRate.toLocaleString()} unit="mm/min" color="#60a5fa" />
              <DataRow label="Tool #" value={`T${String(data.toolNumber).padStart(2,'0')}`} color="#a78bfa" />
              <DataRow label="Tool Wear" value={data.toolWear.toFixed(1)} unit="%" color={data.toolWear > 75 ? '#ef4444' : data.toolWear > 50 ? '#f59e0b' : '#22c55e'} />
            </div>
            <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
              <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Axes & Overrides</span>
              <DataRow label="X" value={data.position.x.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Y" value={data.position.y.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Z" value={data.position.z.toFixed(2)} unit="mm" color="#60a5fa" />
              <DataRow label="Feed Override" value={data.feedOverride} unit="%" color="#f59e0b" />
              <DataRow label="Rapid Override" value={data.rapidOverride} unit="%" color="#f59e0b" />
            </div>
          </div>
          <div className="flex flex-col gap-1 p-2 rounded" style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>Coolant & Power</span>
            <div className="grid grid-cols-2 gap-x-4">
              <DataRow label="Coolant Temp" value={data.coolantTemp.toFixed(1)} unit="°C" color={data.coolantTemp > 32 ? '#f59e0b' : '#60a5fa'} />
              <DataRow label="Coolant Level" value={data.coolantLevel.toFixed(0)} unit="%" color={data.coolantLevel < 30 ? '#ef4444' : '#22c55e'} />
              <DataRow label="Power Draw" value={data.powerKw.toFixed(2)} unit="kW" color="#60a5fa" />
              <DataRow label="Parts" value={`${data.partsComplete} / ${data.partsTarget}`} color="#f59e0b" />
            </div>
            <MiniSparkline data={data.history} dataKey="rpm" color="#f59e0b" />
          </div>
          <CycleProgress current={data.cycleTime} total={data.cycleTimeTotal} color="#f59e0b" />
          <AlarmList alarms={data.alarms} />
        </div>
      )}
    </div>
  );
}

// ── Lab Floor Map (Area M / Grid 14) ─────────────────────────

/**
 * Renders an SVG schematic floor map of the Makino Lab (Area M / Grid 14).
 * Equipment blocks are clickable and highlighted when selected. Two camera
 * icon overlays indicate CAM-01 and CAM-02 positions. Clicking an equipment
 * block scrolls the panel list to that machine.
 *
 * @param selectedEquipment   - ID of the currently selected machine, or null.
 * @param onSelectEquipment   - Callback invoked with the equipment ID on click.
 */
function LabFloorMap({ selectedEquipment, onSelectEquipment }: {
  selectedEquipment: string | null;
  onSelectEquipment: (id: string) => void;
}) {
  const equipment = [
    { id: 'haas-tl1',     label: 'Haas TL-1',  sub: 'Lathe',   x: 18,  y: 55, w: 85, h: 62, color: '#22c55e' },
    { id: 'ur5e',         label: 'UR5e',        sub: 'Cobot',   x: 120, y: 55, w: 60, h: 60, color: '#fb923c' },
    { id: 'makino-a51nx', label: 'a51nx',       sub: 'HMC',     x: 198, y: 50, w: 80, h: 68, color: '#34d399' },
    { id: 'makino-d200z', label: 'd200Z',       sub: '5-Axis',  x: 296, y: 50, w: 80, h: 68, color: '#a78bfa' },
    { id: 'makino-ps95',  label: 'PS95',        sub: 'VMC',     x: 394, y: 50, w: 70, h: 68, color: '#f59e0b' },
  ];
  const cameras = [
    { id: 'cam-01', label: 'CAM-01', sub: 'RealSense', x: 158, y: 22, color: '#a78bfa' },
    { id: 'cam-02', label: 'CAM-02', sub: 'Overhead',  x: 340, y: 22, color: '#f472b6' },
  ];

  return (
    <div className="rounded overflow-hidden" style={{ background: 'oklch(0.10 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}>
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.12 0.025 240)' }}>
        <div className="flex items-center gap-2">
          <Gauge size={12} style={{ color: '#fb923c' }} />
          <span className="text-[11px] font-bold tracking-wider text-white">MAKINO LAB — AREA M · GRID 14</span>
        </div>
        <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.40 0.015 230)' }}>
          Floor Plan · Basement
        </span>
      </div>
      <div className="p-3">
        <svg viewBox="0 0 480 200" className="w-full" style={{ height: 160 }}>
          {/* Room outline */}
          <rect x="10" y="10" width="460" height="180" rx="3"
            fill="rgba(8,20,42,0.80)" stroke="rgba(96,165,250,0.20)" strokeWidth="1.5" />

          {/* Grid lines */}
          {[60, 120, 180, 240, 300, 360, 420].map(x => (
            <line key={x} x1={x} y1="10" x2={x} y2="190"
              stroke="rgba(96,165,250,0.05)" strokeWidth="0.5" strokeDasharray="4 4" />
          ))}
          {[50, 100, 150].map(y => (
            <line key={y} x1="10" y1={y} x2="470" y2={y}
              stroke="rgba(96,165,250,0.05)" strokeWidth="0.5" strokeDasharray="4 4" />
          ))}

          {/* Grid labels */}
          <text x="14" y="8" fill="rgba(96,165,250,0.30)" fontSize="7" fontFamily="'IBM Plex Mono'">M</text>
          <text x="14" y="198" fill="rgba(96,165,250,0.30)" fontSize="7" fontFamily="'IBM Plex Mono'">N</text>
          <text x="458" y="198" fill="rgba(96,165,250,0.30)" fontSize="7" fontFamily="'IBM Plex Mono'">14</text>

          {/* Workbench strip */}
          <rect x="20" y="160" width="440" height="22" rx="2"
            fill="rgba(96,165,250,0.04)" stroke="rgba(96,165,250,0.12)" strokeWidth="0.8" />
          <text x="240" y="175" textAnchor="middle" fill="rgba(96,165,250,0.30)" fontSize="7" fontFamily="'IBM Plex Mono'">
            WORKBENCH / TOOL STORAGE
          </text>

          {/* Equipment boxes */}
          {equipment.map(eq => {
            const isSelected = selectedEquipment === eq.id;
            return (
              <g key={eq.id} style={{ cursor: 'pointer' }} onClick={() => onSelectEquipment(eq.id)}>
                <rect x={eq.x} y={eq.y} width={eq.w} height={eq.h} rx="3"
                  fill={isSelected ? `${eq.color}20` : `${eq.color}0A`}
                  stroke={eq.color}
                  strokeWidth={isSelected ? 2 : 1}
                  style={{ filter: isSelected ? `drop-shadow(0 0 8px ${eq.color}60)` : 'none' }}
                />
                {/* Machine icon lines */}
                <line x1={eq.x + 10} y1={eq.y + eq.h / 2} x2={eq.x + eq.w - 10} y2={eq.y + eq.h / 2}
                  stroke={`${eq.color}40`} strokeWidth="1" />
                <text x={eq.x + eq.w / 2} y={eq.y + eq.h / 2 - 5} textAnchor="middle"
                  fill={eq.color} fontSize="9" fontWeight="700" fontFamily="'IBM Plex Mono'">
                  {eq.label}
                </text>
                <text x={eq.x + eq.w / 2} y={eq.y + eq.h / 2 + 8} textAnchor="middle"
                  fill={`${eq.color}80`} fontSize="7" fontFamily="'IBM Plex Mono'">
                  {eq.sub}
                </text>
                {isSelected && (
                  <rect x={eq.x - 2} y={eq.y - 2} width={eq.w + 4} height={eq.h + 4} rx="4"
                    fill="none" stroke={eq.color} strokeWidth="0.8" strokeDasharray="4 3" opacity="0.6" />
                )}
              </g>
            );
          })}

          {/* Camera positions */}
          {cameras.map(cam => (
            <g key={cam.id}>
              <circle cx={cam.x} cy={cam.y} r="8"
                fill={`${cam.color}15`} stroke={cam.color} strokeWidth="1" />
              <text x={cam.x} y={cam.y + 3} textAnchor="middle"
                fill={cam.color} fontSize="7" fontWeight="700" fontFamily="'IBM Plex Mono'">
                ◉
              </text>
              <text x={cam.x} y={cam.y + 18} textAnchor="middle"
                fill={`${cam.color}80`} fontSize="6.5" fontFamily="'IBM Plex Mono'">
                {cam.id}
              </text>
            </g>
          ))}

          {/* Door */}
          <rect x="220" y="186" width="40" height="4" rx="1"
            fill="rgba(251,146,60,0.30)" stroke="rgba(251,146,60,0.50)" strokeWidth="0.8" />
          <text x="240" y="196" textAnchor="middle" fill="rgba(251,146,60,0.50)" fontSize="6" fontFamily="'IBM Plex Mono'">
            ENTRY
          </text>
        </svg>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────

interface MakinoLabProps {
  onBack: () => void;
}

/**
 * Makino Lab deep-dive page for the Advanced Manufacturing Hub.
 *
 * Subscribes to both `equipmentStore` (lathe, cobot, three Makino machines,
 * bridge status) and `cameraStore` (CAM-01, CAM-02) on mount and mirrors
 * their state into local React state so each child panel re-renders on
 * update. Renders a header summary bar, a lab floor-map SVG with clickable
 * equipment icons, collapsible machine data panels for all six machines,
 * and two `CameraTile` components for the YOLO camera feeds.
 *
 * @param onBack - Callback invoked when the user navigates back to the
 *                 main Building Dashboard.
 */
export function MakinoLab({ onBack }: MakinoLabProps) {
  const [lathe, setLathe] = useState<HaasLathData>(equipmentStore.lathe);
  const [cobot, setCobot] = useState<UR5eData>(equipmentStore.cobot);
  const [makinoA51nx, setMakinoA51nx] = useState<MakinoA51nxData>(equipmentStore.makinoA51nx);
  const [makinoD200Z, setMakinoD200Z] = useState<MakinoD200ZData>(equipmentStore.makinoD200Z);
  const [makinoPS95, setMakinoPS95] = useState<MakinoPS95Data>(equipmentStore.makinoPS95);
  const [cam1, setCam1] = useState<YOLOCameraData>(cameraStore.cam1);
  const [cam2, setCam2] = useState<YOLOCameraData>(cameraStore.cam2);
  const [selectedEquipment, setSelectedEquipment] = useState<string | null>(null);
  const [expandedCam, setExpandedCam] = useState<string | null>(null);
  const [haasBridgeStatus, setHaasBridgeStatus] = useState<BridgeStatus>(equipmentStore.haasBridgeStatus);
  const [ur5eBridgeStatus, setUr5eBridgeStatus] = useState<BridgeStatus>(equipmentStore.ur5eBridgeStatus);

  useEffect(() => {
    const unsub1 = equipmentStore.subscribe(() => {
      setLathe({ ...equipmentStore.lathe });
      setCobot({ ...equipmentStore.cobot });
      setMakinoA51nx({ ...equipmentStore.makinoA51nx });
      setMakinoD200Z({ ...equipmentStore.makinoD200Z });
      setMakinoPS95({ ...equipmentStore.makinoPS95 });
      setHaasBridgeStatus(equipmentStore.haasBridgeStatus);
      setUr5eBridgeStatus(equipmentStore.ur5eBridgeStatus);
    });
    const unsub2 = cameraStore.subscribe(() => {
      setCam1({ ...cameraStore.cam1 });
      setCam2({ ...cameraStore.cam2 });
    });
    return () => { unsub1(); unsub2(); };
  }, []);

  const totalAlarms = lathe.alarms.length + cobot.alarms.length
    + makinoA51nx.alarms.length + makinoD200Z.alarms.length + makinoPS95.alarms.length;
  const camAlarms = (cam1.alarmActive ? 1 : 0) + (cam2.alarmActive ? 1 : 0);
  const totalPower = (lathe.powerKw + cobot.powerKw + makinoA51nx.powerKw + makinoD200Z.powerKw + makinoPS95.powerKw).toFixed(1);

  const scrollToEquipment = useCallback((id: string) => {
    setSelectedEquipment(id);
    const el = document.getElementById(`eq-${id}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return (
    <motion.div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: 'oklch(0.08 0.020 240)', fontFamily: "'Space Grotesk', sans-serif" }}
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      transition={{ duration: 0.30, ease: 'easeOut' }}
    >
      {/* ── Top bar ── */}
      <div
        className="flex items-center justify-between px-5 py-3 flex-shrink-0"
        style={{ borderBottom: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.10 0.025 240)' }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded transition-all hover:scale-[0.97] active:scale-[0.95]"
            style={{ background: 'oklch(0.15 0.025 240)', border: '1px solid oklch(1 0 0 / 12%)', color: '#93c5fd' }}
          >
            <ArrowLeft size={12} />
            <span className="text-[10px] font-semibold tracking-wider">DASHBOARD</span>
          </button>
          <div className="w-px h-5" style={{ background: 'oklch(1 0 0 / 10%)' }} />
          <div className="flex flex-col">
            <span className="text-sm font-bold text-white tracking-wide">Subtractive Mfg Lab — Makino</span>
            <span className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
              Room 1067 · Area M · Grid 14 · Basement Level
            </span>
          </div>
        </div>

        {/* KPIs */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="font-data text-lg font-bold" style={{ color: '#60a5fa' }}>{totalPower} kW</span>
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>Total Power</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="font-data text-lg font-bold" style={{ color: totalAlarms > 0 ? '#ef4444' : '#22c55e' }}>
              {totalAlarms + camAlarms}
            </span>
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.45 0.015 230)' }}>Active Alarms</span>
          </div>
          {/* Bridge status badges */}
          <div className="flex items-center gap-1.5">
            {/* Haas TL-1 bridge */}
            <div className="flex items-center gap-1 px-2 py-1 rounded"
              style={{
                background: haasBridgeStatus === 'live' ? 'rgba(34,197,94,0.10)' : haasBridgeStatus === 'connecting' ? 'rgba(251,191,36,0.10)' : 'rgba(107,114,128,0.10)',
                border: `1px solid ${haasBridgeStatus === 'live' ? 'rgba(34,197,94,0.30)' : haasBridgeStatus === 'connecting' ? 'rgba(251,191,36,0.30)' : 'rgba(107,114,128,0.25)'}`,
              }}>
              {haasBridgeStatus === 'live' ? (
                <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} className="w-1.5 h-1.5 rounded-full bg-green-400" />
              ) : haasBridgeStatus === 'connecting' ? (
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }} className="w-1.5 h-1.5 rounded-full border border-yellow-400 border-t-transparent" />
              ) : (
                <div className="w-1.5 h-1.5 rounded-full bg-gray-500" />
              )}
              <span className="text-[8px] font-bold tracking-widest" style={{ color: haasBridgeStatus === 'live' ? '#22c55e' : haasBridgeStatus === 'connecting' ? '#fbbf24' : '#6b7280' }}>
                TL-1 {haasBridgeStatus === 'live' ? 'LIVE' : haasBridgeStatus === 'connecting' ? 'CONN…' : 'SIM'}
              </span>
            </div>
            {/* UR5e bridge */}
            <div className="flex items-center gap-1 px-2 py-1 rounded"
              style={{
                background: ur5eBridgeStatus === 'live' ? 'rgba(34,197,94,0.10)' : ur5eBridgeStatus === 'connecting' ? 'rgba(251,191,36,0.10)' : 'rgba(107,114,128,0.10)',
                border: `1px solid ${ur5eBridgeStatus === 'live' ? 'rgba(34,197,94,0.30)' : ur5eBridgeStatus === 'connecting' ? 'rgba(251,191,36,0.30)' : 'rgba(107,114,128,0.25)'}`,
              }}>
              {ur5eBridgeStatus === 'live' ? (
                <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} className="w-1.5 h-1.5 rounded-full bg-green-400" />
              ) : ur5eBridgeStatus === 'connecting' ? (
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }} className="w-1.5 h-1.5 rounded-full border border-yellow-400 border-t-transparent" />
              ) : (
                <div className="w-1.5 h-1.5 rounded-full bg-gray-500" />
              )}
              <span className="text-[8px] font-bold tracking-widest" style={{ color: ur5eBridgeStatus === 'live' ? '#22c55e' : ur5eBridgeStatus === 'connecting' ? '#fbbf24' : '#6b7280' }}>
                UR5e {ur5eBridgeStatus === 'live' ? 'LIVE' : ur5eBridgeStatus === 'connecting' ? 'CONN…' : 'SIM'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Scrollable body ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 xl:p-5 flex flex-col gap-4 xl:gap-5 max-w-[1600px] mx-auto">

          {/* Floor map — full width */}
          <LabFloorMap selectedEquipment={selectedEquipment} onSelectEquipment={scrollToEquipment} />

          {/* Section header: Equipment */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Settings size={12} style={{ color: (haasBridgeStatus === 'live' || ur5eBridgeStatus === 'live') ? '#22c55e' : '#fb923c' }} />
              <span className="text-[11px] font-bold tracking-widest uppercase" style={{ color: (haasBridgeStatus === 'live' || ur5eBridgeStatus === 'live') ? '#22c55e' : '#fb923c' }}>
                Equipment — {(haasBridgeStatus === 'live' || ur5eBridgeStatus === 'live') ? 'Live Data' : 'Simulated'}
              </span>
            </div>
            <div className="flex-1 h-px" style={{ background: 'oklch(1 0 0 / 8%)' }} />
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.38 0.015 230)' }}>
              5 machines · updates every 1.5s
            </span>
          </div>

          {/* Haas Equipment panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div id="eq-haas-tl1"><LathePanel data={lathe} bridgeStatus={haasBridgeStatus} /></div>
            <div id="eq-ur5e"><CobotPanel data={cobot} bridgeStatus={ur5eBridgeStatus} /></div>
          </div>

          {/* Section header: Makino Equipment */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Cpu size={12} style={{ color: '#34d399' }} />
              <span className="text-[11px] font-bold tracking-widest uppercase" style={{ color: '#34d399' }}>
                Makino Equipment — Simulated
              </span>
            </div>
            <div className="flex-1 h-px" style={{ background: 'oklch(1 0 0 / 8%)' }} />
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.38 0.015 230)' }}>
              3 machines · updates every 1.5s
            </span>
          </div>

          {/* Makino Equipment panels */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            <div id="eq-makino-a51nx"><MakinoA51nxPanel data={makinoA51nx} /></div>
            <div id="eq-makino-d200z"><MakinoD200ZPanel data={makinoD200Z} /></div>
            <div id="eq-makino-ps95"><MakinoPS95Panel data={makinoPS95} /></div>
          </div>

          {/* ── Training Videos Card ── */}
          <TrainingPanel />

          {/* Section header: Cameras */}
          <div className="flex items-center gap-3 mt-1">
            <div className="flex items-center gap-2">
              <Shield size={12} style={{ color: '#a78bfa' }} />
              <span className="text-[11px] font-bold tracking-widest uppercase" style={{ color: '#a78bfa' }}>
                YOLO Camera Feeds
              </span>
            </div>
            <div className="flex-1 h-px" style={{ background: 'oklch(1 0 0 / 8%)' }} />
            <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.38 0.015 230)' }}>
              2 cameras · simulated · connect live stream to activate
            </span>
          </div>

          {/* Camera tiles — 1 col mobile, 2 col md+ */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <CameraTile
              camera={cam1}
              expanded={expandedCam === 'cam-01'}
              onExpand={() => setExpandedCam(expandedCam === 'cam-01' ? null : 'cam-01')}
            />
            <CameraTile
              camera={cam2}
              expanded={expandedCam === 'cam-02'}
              onExpand={() => setExpandedCam(expandedCam === 'cam-02' ? null : 'cam-02')}
            />
          </div>

          {/* Bottom padding */}
          <div className="h-4" />
        </div>
      </div>
    </motion.div>
  );
}
