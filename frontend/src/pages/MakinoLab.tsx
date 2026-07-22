import React, { useEffect } from 'react';
import { BuildingView } from '../components/BuildingView';
import { ListView } from '../components/ListView';
import { useEquipmentStore } from '../stores/equipmentStore';
import { useUiStore } from '../stores/uiStore';

export const MakinoLab: React.FC = () => {
  const connect = useEquipmentStore(s => s.connect);
  const viewMode = useUiStore(s => s.viewMode);

  useEffect(() => {
    connect();
  }, [connect]);

  return viewMode === 'building' ? <BuildingView /> : <ListView />;
};
