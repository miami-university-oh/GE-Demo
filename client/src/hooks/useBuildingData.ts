import { useCallback, useEffect, useState } from 'react';
import {
  getAllAlerts,
  getBuildingSummary,
  getZoneById,
  getZones,
  getZonesByWingAndFloor,
  subscribeToZones,
  type Alert,
  type Floor,
  type Wing,
  type Zone,
} from '@/lib/buildingData';

export function useBuildingData() {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const unsub = subscribeToZones(() => setTick(t => t + 1));
    return unsub;
  }, []);

  return {
    zones: getZones(),
    summary: getBuildingSummary(),
    alerts: getAllAlerts(),
    getZonesByWingAndFloor: useCallback(
      (wing: Wing, floor: Floor) => getZonesByWingAndFloor(wing, floor),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [tick]
    ),
    getZoneById: useCallback(
      (id: string) => getZoneById(id),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [tick]
    ),
  };
}

export function useZone(id: string | null): Zone | undefined {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const unsub = subscribeToZones(() => setTick(t => t + 1));
    return unsub;
  }, []);
  if (!id) return undefined;
  return getZoneById(id);
}

export function useAlerts(): Alert[] {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const unsub = subscribeToZones(() => setTick(t => t + 1));
    return unsub;
  }, []);
  return getAllAlerts();
}
