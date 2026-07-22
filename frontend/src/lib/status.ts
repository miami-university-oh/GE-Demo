import type { MachineStatus } from '../types/equipment';

// Same rule as StatusSquare: running and alarm are live states, so they pulse.
export function svgStatusClass(status: MachineStatus): string {
  const pulse = status === 'running' || status === 'alarm' ? ' live-indicator' : '';
  return `svg-status status-${status}${pulse}`;
}
