import { create } from 'zustand';
import type { 
  HaasData, 
  UR5eData, 
  MakinoData, 
} from '../types/equipment';
import {
  HAAS_DEFAULTS, 
  UR5E_DEFAULTS, 
  MAKINO_A51NX_DEFAULTS, 
  MAKINO_D200Z_DEFAULTS, 
  MAKINO_PS95_DEFAULTS 
} from '../types/equipment';

interface EquipmentState {
  haas: HaasData;
  ur5e: UR5eData;
  makinoA51nx: MakinoData;
  makinoD200Z: MakinoData;
  makinoPS95: MakinoData;
  haasBridgeStatus: 'live' | 'sim' | 'offline';
  ur5eBridgeStatus: 'live' | 'sim' | 'offline';
  wsConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  sendCommand: (cmd: object) => void;
}

let ws: WebSocket | null = null;
let reconnectTimer: number | null = null;

export const useEquipmentStore = create<EquipmentState>((set, get) => ({
  haas: HAAS_DEFAULTS,
  ur5e: UR5E_DEFAULTS,
  makinoA51nx: MAKINO_A51NX_DEFAULTS,
  makinoD200Z: MAKINO_D200Z_DEFAULTS,
  makinoPS95: MAKINO_PS95_DEFAULTS,
  haasBridgeStatus: 'offline',
  ur5eBridgeStatus: 'offline',
  wsConnected: false,

  connect: () => {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsUrl = `ws://${window.location.host}/ws/telemetry`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      set({ wsConnected: true });
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const snapshot = JSON.parse(event.data);
        const updates: Partial<EquipmentState> = {};
        
        if (snapshot.haas) updates.haas = snapshot.haas;
        if (snapshot.ur5e) updates.ur5e = snapshot.ur5e;
        if (snapshot.makinoA51nx) updates.makinoA51nx = snapshot.makinoA51nx;
        if (snapshot.makinoD200Z) updates.makinoD200Z = snapshot.makinoD200Z;
        if (snapshot.makinoPS95) updates.makinoPS95 = snapshot.makinoPS95;
        
        if (snapshot.bridgeStatus) {
          updates.haasBridgeStatus = snapshot.bridgeStatus.haas;
          updates.ur5eBridgeStatus = snapshot.bridgeStatus.ur5e;
        }

        set(updates);
      } catch (e) {
        console.error("Failed to parse WebSocket message", e);
      }
    };

    ws.onclose = () => {
      set({ wsConnected: false });
      ws = null;
      // Auto-reconnect after 5 seconds
      if (!reconnectTimer) {
        reconnectTimer = window.setTimeout(() => {
          get().connect();
        }, 5000);
      }
    };
    
    ws.onerror = (error) => {
      console.error("WebSocket error", error);
    };
  },

  disconnect: () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    set({ wsConnected: false });
  },

  sendCommand: (cmd: object) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(cmd));
    } else {
      console.warn("Cannot send command, WebSocket is not open");
    }
  }
}));
