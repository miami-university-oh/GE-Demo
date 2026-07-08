import React, { useEffect } from 'react';
import { useEquipmentStore } from '../stores/equipmentStore';
import { MachinePanel } from '../components/MachinePanel';
import { FloorMap } from '../components/FloorMap';

export const MakinoLab: React.FC = () => {
  const store = useEquipmentStore();

  useEffect(() => {
    store.connect();
  }, []);

  return (
    <div className="dashboard-layout">
      <div>
        <FloorMap />
      </div>
      <div>
        <MachinePanel data={store.haas} title="HAAS TL-1" />
        <MachinePanel data={store.ur5e} title="UR5E COBOT" />
        <MachinePanel data={store.makinoA51nx} title="MAKINO A51NX" />
        <MachinePanel data={store.makinoD200Z} title="MAKINO D200Z" />
        <MachinePanel data={store.makinoPS95} title="MAKINO PS95" />
      </div>
    </div>
  );
};
