/* ============================================================
   FloorPlanViewer.tsx — Animated Floor Plan Viewer
   V3.1: Supports Basement (0) + Floor 1 + Floor 2
   Design: Aerospace HMI / SCADA Control Room
   ============================================================ */

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Floor, Zone } from '@/lib/buildingData';
import { BuildingElevation } from './BuildingElevation';
import { FloorPlan } from './FloorPlan';
import { ChevronLeft, Layers, Building2 } from 'lucide-react';

interface FloorPlanViewerProps {
  zones: Zone[];
  selectedZoneId: string | null;
  onSelectZone: (id: string) => void;
}

type ViewMode = 'elevation' | 'floor';

const FLOOR_LABELS: Record<Floor, string> = {
  0: 'Basement',
  1: 'Floor 1',
  2: 'Floor 2',
};

const FLOOR_SHORT: Record<Floor, string> = {
  0: 'B',
  1: 'FL 1',
  2: 'FL 2',
};

// Basement uses amber; floors use blue
function floorAccentColor(floor: Floor): string {
  return floor === 0 ? '#fb923c' : '#93c5fd';
}
function floorAccentBg(floor: Floor): string {
  return floor === 0 ? 'oklch(0.65 0.18 50 / 20%)' : 'oklch(0.65 0.18 220 / 20%)';
}
function floorAccentBorder(floor: Floor): string {
  return floor === 0 ? 'oklch(0.65 0.18 50 / 40%)' : 'oklch(0.65 0.18 220 / 40%)';
}
function floorDotColor(floor: Floor): string {
  return floor === 0 ? '#fb923c' : '#60a5fa';
}

export function FloorPlanViewer({ zones, selectedZoneId, onSelectZone }: FloorPlanViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('elevation');
  const [activeFloor, setActiveFloor] = useState<Floor>(1);
  const [transitioning, setTransitioning] = useState(false);

  const handleSelectFloor = useCallback((floor: Floor) => {
    if (transitioning) return;
    setTransitioning(true);
    setActiveFloor(floor);
    setTimeout(() => {
      setViewMode('floor');
      setTransitioning(false);
    }, 80);
  }, [transitioning]);

  const handleBackToElevation = useCallback(() => {
    if (transitioning) return;
    setTransitioning(true);
    setTimeout(() => {
      setViewMode('elevation');
      setTransitioning(false);
    }, 80);
  }, [transitioning]);

  const floorZones = zones.filter(z => z.floor === activeFloor);
  const totalZones = zones.length;
  const floorZoneCount = floorZones.length;
  const accent = floorAccentColor(activeFloor);

  return (
    <div className="relative w-full h-full overflow-hidden">

      {/* ── Top toolbar ── */}
      <div
        className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-4 py-2"
        style={{
          background: 'oklch(0.10 0.025 240)',
          borderBottom: '1px solid oklch(1 0 0 / 8%)',
        }}
      >
        <div className="flex items-center gap-3">
          {viewMode === 'floor' ? (
            <button
              onClick={handleBackToElevation}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded transition-all duration-150 hover:scale-[0.97] active:scale-[0.95]"
              style={{
                background: 'oklch(0.16 0.025 240)',
                border: '1px solid oklch(1 0 0 / 12%)',
                color: '#93c5fd',
              }}
            >
              <ChevronLeft size={12} />
              <span className="text-[10px] font-semibold tracking-wider">BUILDING VIEW</span>
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <Building2 size={13} style={{ color: '#60a5fa' }} />
              <span className="text-[11px] font-semibold tracking-wider uppercase" style={{ color: 'oklch(0.65 0.015 230)' }}>
                Building Overview
              </span>
            </div>
          )}

          {viewMode === 'floor' && (
            <div className="flex items-center gap-2">
              <Layers size={13} style={{ color: accent }} />
              <span className="text-[11px] font-semibold tracking-wider uppercase" style={{ color: 'oklch(0.65 0.015 230)' }}>
                {FLOOR_LABELS[activeFloor]} — Architectural Plan
              </span>
              <span className="text-[10px]" style={{ color: 'oklch(0.40 0.015 230)' }}>
                {floorZoneCount} zone{floorZoneCount !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {viewMode === 'elevation' && (
            <span className="text-[9px] tracking-widest uppercase font-semibold" style={{ color: 'oklch(0.38 0.015 230)' }}>
              {totalZones} zones · Click a floor to inspect
            </span>
          )}

          {viewMode === 'floor' && (
            <div className="flex items-center gap-1">
              {([0, 1, 2] as Floor[]).map(f => (
                <button
                  key={f}
                  onClick={() => handleSelectFloor(f)}
                  className="px-2.5 py-1 rounded text-[10px] font-semibold transition-all duration-150"
                  style={{
                    background: activeFloor === f ? floorAccentBg(f) : 'transparent',
                    color: activeFloor === f ? floorAccentColor(f) : 'oklch(0.50 0.015 230)',
                    border: activeFloor === f ? `1px solid ${floorAccentBorder(f)}` : '1px solid transparent',
                  }}
                >
                  {FLOOR_SHORT[f]}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── View area (below toolbar) ── */}
      <div className="absolute inset-0 top-[40px]">
        <AnimatePresence mode="wait">
          {viewMode === 'elevation' ? (
            <motion.div
              key="elevation"
              className="w-full h-full"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.04 }}
              transition={{ duration: 0.32, ease: 'easeOut' }}
            >
              <BuildingElevation
                zones={zones}
                onSelectFloor={handleSelectFloor}
              />
            </motion.div>
          ) : (
            <motion.div
              key={`floor-${activeFloor}`}
              className="w-full h-full"
              initial={{ opacity: 0, scale: 0.88, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 1.06, y: -16 }}
              transition={{ duration: 0.38, ease: 'easeOut' }}
            >
              <FloorPlan
                zones={zones}
                selectedZoneId={selectedZoneId}
                onSelectZone={onSelectZone}
                floor={activeFloor}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Floor indicator breadcrumb (bottom-left) ── */}
      {viewMode === 'floor' && (
        <motion.div
          className="absolute bottom-3 left-4 z-20 flex items-center gap-2"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.25 }}
        >
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded"
            style={{
              background: activeFloor === 0 ? 'rgba(30,15,5,0.90)' : 'rgba(13,31,60,0.90)',
              border: `1px solid ${activeFloor === 0 ? 'rgba(251,146,60,0.35)' : 'rgba(96,165,250,0.30)'}`,
            }}
          >
            <div
              className="w-2 h-2 rounded-full"
              style={{
                background: floorDotColor(activeFloor),
                boxShadow: `0 0 6px ${floorDotColor(activeFloor)}80`,
              }}
            />
            <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: accent }}>
              {activeFloor === 0 ? '▼ Basement Level' : `Floor ${activeFloor} of 2`}
            </span>
          </div>
        </motion.div>
      )}
    </div>
  );
}
