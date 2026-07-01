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

/**
 * Subscribes to live zone updates and exposes building data utilities.
 *
 * Re-renders the consumer on every simulation tick. The `getZonesByWingAndFloor` and
 * `getZoneById` callbacks are recreated each tick so they always reflect the latest
 * zone state while remaining referentially stable within a single render.
 *
 * @returns An object with:
 * - `zones` — current Zone array snapshot.
 * - `summary` — aggregate building statistics.
 * - `alerts` — all active alerts sorted newest-first.
 * - `getZonesByWingAndFloor(wing, floor)` — filtered zone lookup.
 * - `getZoneById(id)` — single-zone lookup by ID.
 */
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

/**
 * Returns a single {@link Zone} by ID, or `undefined` if the ID is null or not found.
 * Re-renders the consumer on every simulation tick.
 *
 * @param id - Zone identifier, or `null` to opt out.
 * @returns The matching Zone, or `undefined`.
 */
export function useZone(id: string | null): Zone | undefined {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const unsub = subscribeToZones(() => setTick(t => t + 1));
    return unsub;
  }, []);
  if (!id) return undefined;
  return getZoneById(id);
}

/**
 * Returns all active alerts across the building, sorted newest-first by timestamp.
 * Re-renders the consumer on every simulation tick.
 *
 * @returns Flat array of all {@link Alert} objects.
 */
export function useAlerts(): Alert[] {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const unsub = subscribeToZones(() => setTick(t => t + 1));
    return unsub;
  }, []);
  return getAllAlerts();
}
