import React from 'react';
import {
  FLOOR_PLAN_VIEWBOX,
  FLOOR_WINGS,
  machinesForRoom,
  roomsForFloor,
} from '../lib/buildingLayout';
import type { FloorId } from '../lib/buildingLayout';
import { isActivateKey } from '../lib/keys';
import { svgStatusClass } from '../lib/status';
import { useEquipmentStore } from '../stores/equipmentStore';

interface FloorPlanViewProps {
  floorId: FloorId;
  onSelectRoom: (roomId: string) => void;
}

export const FloorPlanView: React.FC<FloorPlanViewProps> = ({ floorId, onSelectRoom }) => {
  const store = useEquipmentStore();
  const rooms = roomsForFloor(floorId);

  return (
    <svg
      className="map-svg"
      viewBox={`0 0 ${FLOOR_PLAN_VIEWBOX.w} ${FLOOR_PLAN_VIEWBOX.h}`}
      aria-label="Floor plan"
    >
      {FLOOR_WINGS.map((wing, i) => (
        <rect key={i} className="plan-wing" x={wing.x} y={wing.y} width={wing.w} height={wing.h} />
      ))}

      {rooms.map(room => {
        const { x, y, w, h } = room.rect;
        const cx = x + w / 2;
        const cy = y + h / 2;
        const machines = machinesForRoom(room.id);

        // Rooms without monitored equipment are structure only: drawn muted,
        // not clickable, so the drill-down never dead-ends.
        if (machines.length === 0) {
          return (
            <g key={room.id}>
              <rect className="plan-room" x={x} y={y} width={w} height={h} />
              <text className="plan-room-label-muted" x={cx} y={room.roomNumber ? cy - 2 : cy + 3}>
                {room.label}
              </text>
              {room.roomNumber && (
                <text className="plan-room-number" x={cx} y={cy + 12}>ROOM {room.roomNumber}</text>
              )}
            </g>
          );
        }

        const activate = () => onSelectRoom(room.id);
        return (
          <g
            key={room.id}
            className="plan-room-active"
            role="button"
            tabIndex={0}
            aria-label={`${room.label}${room.roomNumber ? ` ${room.roomNumber}` : ''} — ${machines.length} machines`}
            onClick={activate}
            onKeyDown={e => {
              if (isActivateKey(e)) {
                e.preventDefault();
                activate();
              }
            }}
          >
            <rect className="plan-room-rect" x={x} y={y} width={w} height={h} />
            {machines.map((p, i) => (
              <rect
                key={p.storeKey}
                className={svgStatusClass(store[p.storeKey].status)}
                x={x + 10 + i * 14}
                y={y + 12}
                width={8}
                height={8}
              />
            ))}
            <text className="plan-room-label" x={cx} y={cy - 2}>{room.label}</text>
            {room.roomNumber && (
              <text className="plan-room-number" x={cx} y={cy + 14}>ROOM {room.roomNumber}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
};
