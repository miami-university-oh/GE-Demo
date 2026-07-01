/* ============================================================
   BuildingHeader.tsx — Top status bar with global KPIs
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, Building2, LogOut, Thermometer, Users, Zap, Wifi, WifiOff, Bot } from 'lucide-react';
import { useLocation } from 'wouter';
import type { Alert } from '@/lib/buildingData';
import { equipmentStore } from '@/lib/equipmentData';
import type { BridgeStatus } from '@/lib/equipmentData';
import { useAuth } from '@/contexts/AuthContext';

interface BuildingSummary {
  total: number;
  ok: number;
  warn: number;
  critical: number;
  offline: number;
  totalEnergy: number;
  totalOccupancy: number;
  avgTemp: number;
}

interface BuildingHeaderProps {
  summary: BuildingSummary;
  alerts: Alert[];
  currentTime: Date;
}

function KpiChip({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded"
      style={{ background: 'oklch(0.13 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}
    >
      <Icon size={13} style={{ color }} />
      <div className="flex flex-col">
        <span className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.50 0.015 230)' }}>
          {label}
        </span>
        <span className="font-data text-sm font-semibold" style={{ color }}>
          {value}
        </span>
      </div>
    </div>
  );
}

function StatusDot({ count, color, label }: { count: number; color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color, boxShadow: `0 0 6px ${color}80` }} />
      <span className="font-data text-xs font-semibold" style={{ color }}>
        {count}
      </span>
      <span className="text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
        {label}
      </span>
    </div>
  );
}

function ConnectionBadge({ label, status }: { label: string; status: BridgeStatus }) {
  const color = status === 'live' ? '#22c55e' : status === 'connecting' ? '#fbbf24' : '#6b7280';
  const bg = status === 'live' ? 'rgba(34,197,94,0.10)' : status === 'connecting' ? 'rgba(251,191,36,0.10)' : 'rgba(107,114,128,0.08)';
  const border = status === 'live' ? 'rgba(34,197,94,0.30)' : status === 'connecting' ? 'rgba(251,191,36,0.30)' : 'rgba(107,114,128,0.20)';
  const text = status === 'live' ? 'LIVE' : status === 'connecting' ? 'CONN' : 'SIM';
  const Icon = status === 'live' ? Wifi : WifiOff;

  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded"
      style={{ background: bg, border: `1px solid ${border}` }}
    >
      <Icon size={10} style={{ color }} />
      <span className="font-data text-[9px] font-bold tracking-wider" style={{ color }}>
        {label} {text}
      </span>
      {status === 'live' && (
        <span className="w-1.5 h-1.5 rounded-full pulse-live" style={{ background: color, boxShadow: `0 0 4px ${color}` }} />
      )}
    </div>
  );
}

function MachineConnectionStatus() {
  const [haasStatus, setHaasStatus] = useState<BridgeStatus>(equipmentStore.haasBridgeStatus);
  const [ur5eStatus, setUr5eStatus] = useState<BridgeStatus>(equipmentStore.ur5eBridgeStatus);

  useEffect(() => {
    const unsub = equipmentStore.subscribe(() => {
      setHaasStatus(equipmentStore.haasBridgeStatus);
      setUr5eStatus(equipmentStore.ur5eBridgeStatus);
    });
    return unsub;
  }, []);

  return (
    <div className="flex items-center gap-1.5">
      <ConnectionBadge label="TL-1" status={haasStatus} />
      <ConnectionBadge label="UR5e" status={ur5eStatus} />
    </div>
  );
}

export function BuildingHeader({ summary, alerts, currentTime }: BuildingHeaderProps) {
  const { username, logout } = useAuth();
  const [, navigate] = useLocation();
  const criticalAlerts = alerts.filter(a => a.severity === 'critical').length;

  return (
    <header
      className="flex items-center justify-between px-4 py-2.5 gap-3 flex-shrink-0 flex-wrap"
      style={{
        background: 'oklch(0.09 0.025 240)',
        borderBottom: '1px solid oklch(1 0 0 / 8%)',
        minHeight: '52px',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div
          className="w-8 h-8 rounded flex items-center justify-center"
          style={{ background: 'oklch(0.65 0.18 220 / 20%)', border: '1px solid oklch(0.65 0.18 220 / 40%)' }}
        >
          <Building2 size={16} style={{ color: '#60a5fa' }} />
        </div>
        <div>
          <div className="text-sm font-bold text-white leading-tight tracking-tight">
            IIoT Building Dashboard
          </div>
          <div className="text-[9px] tracking-widest uppercase" style={{ color: 'oklch(0.50 0.015 230)' }}>
            Advanced Manufacturing Hub · SCADA Monitor
          </div>
        </div>
      </div>

      {/* Zone status summary */}
      <div
        className="flex items-center gap-4 px-4 py-2 rounded"
        style={{ background: 'oklch(0.12 0.025 240)', border: '1px solid oklch(1 0 0 / 8%)' }}
      >
        <div className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.45 0.015 230)' }}>
          Zone Status
        </div>
        <StatusDot count={summary.ok} color="#22c55e" label="OK" />
        <StatusDot count={summary.warn} color="#f59e0b" label="WARN" />
        <StatusDot count={summary.critical} color="#ef4444" label="CRIT" />
        <StatusDot count={summary.offline} color="#64748b" label="OFFLINE" />
      </div>

      {/* KPI chips */}
      <div className="flex items-center gap-2">
        <KpiChip
          icon={Zap}
          label="Total Power"
          value={`${summary.totalEnergy.toFixed(1)} kW`}
          color="#60a5fa"
        />
        <KpiChip
          icon={Thermometer}
          label="Avg Temp"
          value={`${summary.avgTemp.toFixed(1)} °C`}
          color={summary.avgTemp > 26 ? '#f59e0b' : '#22c55e'}
        />
        <KpiChip
          icon={Users}
          label="Occupancy"
          value={`${summary.totalOccupancy}`}
          color="#a78bfa"
        />
      </div>

      {/* Machine connection status */}
      <MachineConnectionStatus />

      {/* UR5e Dashboard link */}
      <button
        onClick={() => navigate('/ur5e')}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors"
        style={{
          background: 'oklch(0.65 0.18 280 / 10%)',
          border: '1px solid oklch(0.65 0.18 280 / 25%)',
          color: 'oklch(0.75 0.12 280)',
        }}
        title="Open UR5e RTDE Dashboard"
      >
        <Bot size={12} />
        <span className="font-data text-[10px] font-bold tracking-wider">UR5e DASH</span>
      </button>

      {/* Alerts + time */}
      <div className="flex items-center gap-3 flex-shrink-0">
        {criticalAlerts > 0 && (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded alert-pulse"
            style={{
              background: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.40)',
            }}
          >
            <AlertTriangle size={12} style={{ color: '#ef4444' }} />
            <span className="font-data text-xs font-semibold" style={{ color: '#ef4444' }}>
              {criticalAlerts} CRITICAL
            </span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <Activity size={11} className="pulse-live" style={{ color: '#22c55e' }} />
          <span className="font-data text-[10px]" style={{ color: 'oklch(0.50 0.015 230)' }}>
            LIVE
          </span>
        </div>
        <div
          className="font-data text-xs"
          style={{ color: 'oklch(0.55 0.015 230)', minWidth: '64px', textAlign: 'right' }}
        >
          {currentTime.toLocaleTimeString('en-US', { hour12: false })}
        </div>
        <button
          onClick={logout}
          title={`Signed in as ${username} — click to sign out`}
          className="flex items-center gap-1.5 px-2 py-1 rounded transition-colors hover:bg-[oklch(1_0_0/8%)]"
          style={{ color: 'oklch(0.50 0.015 230)' }}
        >
          <LogOut size={12} />
          <span className="text-[10px] uppercase tracking-wider hidden xl:inline">{username}</span>
        </button>
      </div>
    </header>
  );
}
