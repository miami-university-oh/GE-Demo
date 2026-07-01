/* ============================================================
   AlertTicker.tsx — Bottom scrolling alert strip
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { AlertTriangle, CheckCircle, Info } from 'lucide-react';
import type { Alert } from '@/lib/buildingData';

interface AlertTickerProps {
  alerts: Alert[];
}

export function AlertTicker({ alerts }: AlertTickerProps) {
  const hasAlerts = alerts.length > 0;

  const items = hasAlerts
    ? alerts.slice(0, 12)
    : [
        { id: 'sys1', severity: 'ok' as const, message: 'All systems nominal', zoneName: 'Building', timestamp: Date.now() },
        { id: 'sys2', severity: 'ok' as const, message: 'Data acquisition active', zoneName: 'System', timestamp: Date.now() },
        { id: 'sys3', severity: 'ok' as const, message: 'Network connectivity stable', zoneName: 'Network', timestamp: Date.now() },
      ];

  const tickerItems = [...items, ...items]; // duplicate for seamless loop

  return (
    <div
      className="flex items-center gap-0 flex-shrink-0 overflow-hidden"
      style={{
        height: '28px',
        background: 'oklch(0.08 0.025 240)',
        borderTop: '1px solid oklch(1 0 0 / 8%)',
      }}
    >
      {/* Label */}
      <div
        className="flex items-center gap-1.5 px-3 h-full flex-shrink-0"
        style={{
          background: hasAlerts ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.10)',
          borderRight: `1px solid ${hasAlerts ? 'rgba(239,68,68,0.30)' : 'rgba(34,197,94,0.25)'}`,
        }}
      >
        {hasAlerts ? (
          <AlertTriangle size={10} style={{ color: '#ef4444' }} />
        ) : (
          <CheckCircle size={10} style={{ color: '#22c55e' }} />
        )}
        <span
          className="font-data text-[9px] font-semibold tracking-widest"
          style={{ color: hasAlerts ? '#ef4444' : '#22c55e' }}
        >
          {hasAlerts ? 'ALERTS' : 'STATUS'}
        </span>
      </div>

      {/* Scrolling ticker */}
      <div className="flex-1 overflow-hidden relative">
        <div className="ticker-scroll flex items-center gap-0 whitespace-nowrap" style={{ width: 'max-content' }}>
          {tickerItems.map((item, i) => {
            const isAlert = 'type' in item;
            const severity = item.severity;
            const color = severity === 'critical' ? '#ef4444' : severity === 'warn' ? '#f59e0b' : '#22c55e';
            return (
              <span
                key={`${item.id}-${i}`}
                className="inline-flex items-center gap-1.5 px-4 font-data text-[10px]"
                style={{ color: 'oklch(0.65 0.015 230)' }}
              >
                <span style={{ color }} className="text-[8px]">●</span>
                <span style={{ color: 'oklch(0.55 0.015 230)' }}>{item.zoneName}</span>
                <span>·</span>
                <span style={{ color: 'oklch(0.75 0.01 220)' }}>{item.message}</span>
                <span style={{ color: 'oklch(0.40 0.015 230)' }}>
                  {new Date(item.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                </span>
                <span style={{ color: 'oklch(0.25 0.015 230)' }} className="mx-2">|</span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
