import React from 'react';
import type { MachineStatus } from '../types/equipment';

interface StatusSquareProps {
  status: MachineStatus;
  className?: string;
}

export const StatusSquare: React.FC<StatusSquareProps> = ({ status, className = '' }) => {
  const statusClass = `status-${status}`;
  const pulseClass = status === 'running' || status === 'alarm' ? 'live-indicator' : '';
  
  return (
    <span className={`status-square ${statusClass} ${pulseClass} ${className}`} title={status.toUpperCase()} />
  );
};
