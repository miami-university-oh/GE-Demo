import React, { useEffect, useRef, useState } from 'react';
import {
  floorById,
  machinesForFloor,
  machinesForRoom,
  PLACEMENTS,
  roomById,
} from '../lib/buildingLayout';
import type { FloorId, StoreMachineKey } from '../lib/buildingLayout';
import { useEquipmentStore } from '../stores/equipmentStore';
import { Breadcrumb } from './Breadcrumb';
import type { Crumb } from './Breadcrumb';
import { BuildingElevation } from './BuildingElevation';
import { FloorPlanView } from './FloorPlanView';
import { MachinePanel } from './MachinePanel';
import { RoomView } from './RoomView';

type Drill =
  | { level: 'building' }
  | { level: 'floor'; floorId: FloorId }
  | { level: 'room'; floorId: FloorId; roomId: string };

export const BuildingView: React.FC = () => {
  const store = useEquipmentStore();
  const [drill, setDrill] = useState<Drill>({ level: 'building' });
  const [selectedMachine, setSelectedMachine] = useState<StoreMachineKey | null>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const slotRefs = useRef(new Map<StoreMachineKey, HTMLDivElement | null>());
  const mounted = useRef(false);

  // Move focus to the map after drilling so Escape works immediately and
  // screen readers announce the new level. Skipped on mount so page load
  // does not steal focus.
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    mapRef.current?.focus({ preventScroll: true });
  }, [drill]);

  const goBuilding = () => {
    setDrill({ level: 'building' });
    setSelectedMachine(null);
  };

  const goFloor = (floorId: FloorId) => {
    setDrill({ level: 'floor', floorId });
    setSelectedMachine(null);
  };

  const goRoom = (floorId: FloorId, roomId: string) => {
    setDrill({ level: 'room', floorId, roomId });
    setSelectedMachine(null);
  };

  const goUp = () => {
    if (drill.level === 'room') goFloor(drill.floorId);
    else if (drill.level === 'floor') goBuilding();
  };

  const selectMachine = (key: StoreMachineKey) => {
    setSelectedMachine(key);
    slotRefs.current.get(key)?.scrollIntoView({ block: 'nearest' });
  };

  const scoped =
    drill.level === 'building' ? PLACEMENTS
    : drill.level === 'floor' ? machinesForFloor(drill.floorId)
    : machinesForRoom(drill.roomId);

  const crumbs: Crumb[] = [{ label: 'BUILDING', onClick: drill.level === 'building' ? undefined : goBuilding }];
  if (drill.level !== 'building') {
    const floor = floorById(drill.floorId);
    crumbs.push({
      label: floor.label,
      onClick: drill.level === 'room' ? () => goFloor(floor.id) : undefined,
    });
  }
  if (drill.level === 'room') {
    const room = roomById(drill.roomId);
    if (room) {
      crumbs.push({ label: room.roomNumber ? `${room.label} ${room.roomNumber}` : room.label });
    }
  }

  return (
    <div
      className="dashboard-layout"
      onKeyDown={e => {
        if (e.key === 'Escape') goUp();
      }}
    >
      <div className="map-panel" ref={mapRef} tabIndex={-1}>
        <Breadcrumb crumbs={crumbs} />
        {drill.level === 'building' && <BuildingElevation onSelectFloor={goFloor} />}
        {drill.level === 'floor' && (
          <FloorPlanView floorId={drill.floorId} onSelectRoom={id => goRoom(drill.floorId, id)} />
        )}
        {drill.level === 'room' && (
          <RoomView
            roomId={drill.roomId}
            selectedMachine={selectedMachine}
            onSelectMachine={selectMachine}
          />
        )}
      </div>

      <div>
        {scoped.length === 0 ? (
          <div className="panel-empty">NO CONNECTED EQUIPMENT ON THIS FLOOR</div>
        ) : (
          scoped.map(p => (
            <div
              key={p.storeKey}
              className={`panel-slot ${selectedMachine === p.storeKey ? 'selected' : ''}`}
              ref={el => {
                slotRefs.current.set(p.storeKey, el);
              }}
            >
              <MachinePanel data={store[p.storeKey]} title={p.title} />
            </div>
          ))
        )}
      </div>
    </div>
  );
};
