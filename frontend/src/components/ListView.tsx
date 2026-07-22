import React, { useState } from 'react';
import { FLOORS, floorSummary, machinesForFloor, summaryLine } from '../lib/buildingLayout';
import type { FloorId } from '../lib/buildingLayout';
import { useEquipmentStore } from '../stores/equipmentStore';
import { MachinePanel } from './MachinePanel';

export const ListView: React.FC = () => {
  const store = useEquipmentStore();
  // Floors with machines start expanded; empty floors have nothing to expand.
  const [open, setOpen] = useState<Record<FloorId, boolean>>(() =>
    Object.fromEntries(
      FLOORS.map(f => [f.id, machinesForFloor(f.id).length > 0]),
    ) as Record<FloorId, boolean>,
  );

  const toggle = (floorId: FloorId) => {
    setOpen(prev => ({ ...prev, [floorId]: !prev[floorId] }));
  };

  return (
    <div className="list-view">
      {FLOORS.map(floor => {
        const placements = machinesForFloor(floor.id);
        const summary = summaryLine(floorSummary(placements.map(p => store[p.storeKey])));

        if (placements.length === 0) {
          return (
            <div key={floor.id} className="floor-section">
              <div className="floor-section-static">
                <span className="floor-section-title">{floor.label}</span>
                <span className="floor-section-summary">{summary}</span>
              </div>
            </div>
          );
        }

        const isOpen = open[floor.id];
        return (
          <div key={floor.id} className="floor-section">
            <button
              type="button"
              className="floor-section-header"
              aria-expanded={isOpen}
              onClick={() => toggle(floor.id)}
            >
              <span className="floor-section-title">
                <span className="floor-section-glyph" aria-hidden="true">{isOpen ? '−' : '+'}</span>
                {floor.label}
              </span>
              <span className="floor-section-summary">{summary}</span>
            </button>
            {isOpen && (
              <div className="floor-section-body">
                {placements.map(p => (
                  <MachinePanel key={p.storeKey} data={store[p.storeKey]} title={p.title} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
