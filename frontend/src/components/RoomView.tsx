import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  camerasForRoom,
  machinesForRoom,
  ROOM_SCHEMATIC_VIEWBOX,
  ROOM_SCHEMATIC_WALL,
} from '../lib/buildingLayout';
import type { StoreMachineKey } from '../lib/buildingLayout';
import { isActivateKey } from '../lib/keys';
import { svgStatusClass } from '../lib/status';
import { useEquipmentStore } from '../stores/equipmentStore';

interface RoomViewProps {
  roomId: string;
  selectedMachine: StoreMachineKey | null;
  onSelectMachine: (key: StoreMachineKey) => void;
}

export const RoomView: React.FC<RoomViewProps> = ({ roomId, selectedMachine, onSelectMachine }) => {
  const store = useEquipmentStore();
  const navigate = useNavigate();
  const machines = machinesForRoom(roomId);
  const cameras = camerasForRoom(roomId);
  const wall = ROOM_SCHEMATIC_WALL;
  const goToCameras = () => navigate('/cameras');

  return (
    <svg
      className="map-svg"
      viewBox={`0 0 ${ROOM_SCHEMATIC_VIEWBOX.w} ${ROOM_SCHEMATIC_VIEWBOX.h}`}
      aria-label="Room layout — select a machine"
    >
      <rect className="room-wall" x={wall.x} y={wall.y} width={wall.w} height={wall.h} />

      {/* Entry door in the bottom wall — anchors where machines sit relative
          to where the operator walks in. */}
      <rect className="room-door" x={220} y={186} width={40} height={4} />
      <text className="room-door-label" x={240} y={197}>ENTRY</text>

      {machines.map(p => {
        const { x, y, w, h } = p.rect;
        const cx = x + w / 2;
        const cy = y + h / 2;
        const data = store[p.storeKey];
        const selected = selectedMachine === p.storeKey;
        const activate = () => onSelectMachine(p.storeKey);

        return (
          <g
            key={p.storeKey}
            className={`room-machine ${selected ? 'selected' : ''}`}
            role="button"
            tabIndex={0}
            aria-pressed={selected}
            aria-label={`${p.title} — ${data.status}`}
            onClick={activate}
            onKeyDown={e => {
              if (isActivateKey(e)) {
                e.preventDefault();
                activate();
              }
            }}
          >
            <rect className="room-machine-rect" x={x} y={y} width={w} height={h} />
            <rect className={svgStatusClass(data.status)} x={x + 6} y={y + 6} width={8} height={8} />
            <text className="room-machine-label" x={cx} y={cy - 1}>{p.shortLabel}</text>
            <text className="room-machine-kind" x={cx} y={cy + 11}>{p.kind}</text>
          </g>
        );
      })}

      {cameras.map(cam => (
        <g
          key={cam.label}
          className="cam-marker"
          role="link"
          tabIndex={0}
          aria-label={`${cam.label} — open camera feeds`}
          onClick={goToCameras}
          onKeyDown={e => {
            if (isActivateKey(e)) {
              e.preventDefault();
              goToCameras();
            }
          }}
        >
          <circle className="cam-marker-dot" cx={cam.x} cy={cam.y} r={6} />
          <circle className="cam-marker-core" cx={cam.x} cy={cam.y} r={2} />
          <text className="cam-marker-label" x={cam.x} y={cam.y + 16}>{cam.label}</text>
        </g>
      ))}
    </svg>
  );
};
