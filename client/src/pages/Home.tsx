/* ============================================================
   Home.tsx — Main IIoT Dashboard Page (V3.2)
   Design: Aerospace HMI / SCADA Control Room
   Layout:
     [Header: global KPIs + status bar]
     [Sidebar: wing/zone nav] [FloorPlanViewer: elevation → zoom] [Zone panel: live data]
     [Wing overview] [Alert ticker]
   Special: Clicking the Makino Lab zone opens the MakinoLab deep-dive view
   ============================================================ */

import { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { AlertTicker } from '@/components/AlertTicker';
import { BuildingHeader } from '@/components/BuildingHeader';
import { FloorPlanViewer } from '@/components/FloorPlanViewer';
import { WingSidebar } from '@/components/WingSidebar';
import { ZonePanel } from '@/components/ZonePanel';
import { BuildingOverview } from '@/components/BuildingOverview';
import { MakinoLab } from '@/pages/MakinoLab';
import { useBuildingData, useZone } from '@/hooks/useBuildingData';
import type { Floor, Wing } from '@/lib/buildingData';
import { Maximize2, Minimize2 } from 'lucide-react';

// Zone IDs that trigger the Makino deep-dive view
const MAKINO_ZONE_ID = 'B0-MAK';

function isMakinoZone(id: string | null): boolean {
  return id === MAKINO_ZONE_ID;
}

export default function Home() {
  const { zones, summary, alerts } = useBuildingData();
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [activeWing, setActiveWing] = useState<Wing>('east');
  const [activeFloor, setActiveFloor] = useState<Floor>(1);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [panelExpanded, setPanelExpanded] = useState(false);
  const [showMakinoLab, setShowMakinoLab] = useState(false);

  const selectedZone = useZone(selectedZoneId);

  // Clock tick
  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectZone = (id: string) => {
    const zone = zones.find(z => z.id === id);
    if (zone) {
      setActiveWing(zone.wing);
      setActiveFloor(zone.floor);
    }

    // If Makino zone clicked → open deep-dive
    if (isMakinoZone(id)) {
      setShowMakinoLab(true);
      setSelectedZoneId(null);
      return;
    }

    setSelectedZoneId(prev => (prev === id ? null : id));
  };

  const handleSelectWing = (wing: Wing) => {
    setActiveWing(wing);
    setSelectedZoneId(null);
  };

  // If Makino deep-dive is open, render it full-screen inside the dashboard frame
  if (showMakinoLab) {
    return (
      <div
        className="flex flex-col h-screen overflow-hidden"
        style={{ background: 'oklch(0.09 0.025 240)', fontFamily: "'Space Grotesk', sans-serif" }}
      >
        <BuildingHeader summary={summary} alerts={alerts} currentTime={currentTime} />
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <MakinoLab key="makino-lab" onBack={() => setShowMakinoLab(false)} />
          </AnimatePresence>
        </div>
        <AlertTicker alerts={alerts} />
      </div>
    );
  }

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: 'oklch(0.09 0.025 240)', fontFamily: "'Space Grotesk', sans-serif" }}
    >
      {/* ── TOP HEADER ── */}
      <BuildingHeader summary={summary} alerts={alerts} currentTime={currentTime} />

      {/* ── MAIN CONTENT ── */}
      <div className="flex flex-1 overflow-hidden w-full">

        {/* ── LEFT SIDEBAR ── */}
        <WingSidebar
          zones={zones}
          selectedZoneId={selectedZoneId}
          onSelectZone={handleSelectZone}
          activeWing={activeWing}
          onSelectWing={handleSelectWing}
        />

        {/* ── CENTER: FLOOR PLAN VIEWER ── */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          <FloorPlanViewer
            zones={zones}
            selectedZoneId={selectedZoneId}
            onSelectZone={handleSelectZone}
          />

          {/* Legend strip */}
          <div
            className="flex items-center gap-5 px-4 py-2 flex-shrink-0 absolute bottom-0 left-0 right-0 z-10"
            style={{ borderTop: '1px solid oklch(1 0 0 / 8%)', background: 'oklch(0.10 0.025 240 / 95%)' }}
          >
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.40 0.015 230)' }}>
              Legend
            </span>
            {[
              { color: '#22c55e', label: 'Operational' },
              { color: '#f59e0b', label: 'Warning' },
              { color: '#ef4444', label: 'Critical' },
              { color: '#64748b', label: 'Offline' },
              { color: '#60a5fa', label: 'Selected' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: color, opacity: 0.8 }} />
                <span className="text-[10px]" style={{ color: 'oklch(0.55 0.015 230)' }}>{label}</span>
              </div>
            ))}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm" style={{ background: '#fb923c', opacity: 0.8 }} />
              <span className="text-[10px]" style={{ color: '#fb923c' }}>
                Click Makino Lab (Basement) for deep-dive view
              </span>
            </div>
          </div>
        </main>

        {/* ── RIGHT PANEL: ZONE DETAIL ── */}
        <div
          className="flex flex-col overflow-hidden transition-all duration-200"
          style={{
            width: selectedZone ? (panelExpanded ? 'clamp(320px, 28vw, 480px)' : 'clamp(280px, 22vw, 380px)') : '0px',
            borderLeft: selectedZone ? '1px solid oklch(1 0 0 / 8%)' : 'none',
            flexShrink: 0,
          }}
        >
          {selectedZone && (
            <>
              <div
                className="flex justify-end px-2 py-1 flex-shrink-0"
                style={{ borderBottom: '1px solid oklch(1 0 0 / 6%)', background: 'oklch(0.10 0.025 240)' }}
              >
                <button
                  onClick={() => setPanelExpanded(e => !e)}
                  className="p-1 rounded hover:bg-white/10 transition-colors"
                  style={{ color: 'oklch(0.45 0.015 230)' }}
                  title={panelExpanded ? 'Collapse panel' : 'Expand panel'}
                >
                  {panelExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <ZonePanel zone={selectedZone} onClose={() => setSelectedZoneId(null)} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── WING OVERVIEW ── */}
      <BuildingOverview zones={zones} />

      {/* ── BOTTOM ALERT TICKER ── */}
      <AlertTicker alerts={alerts} />
    </div>
  );
}
