import React from 'react';
import type { MachineData } from '../types/equipment';
import { StatusSquare } from './StatusSquare';
import { DataRow } from './DataRow';
import { useEquipmentStore } from '../stores/equipmentStore';

interface MachinePanelProps {
  data: MachineData;
  title: string;
}

export const MachinePanel: React.FC<MachinePanelProps> = ({ data, title }) => {
  const { sendCommand } = useEquipmentStore();
  const [activeCommand, setActiveCommand] = React.useState<string | null>(null);

  const handleCommand = (action: string) => {
    setActiveCommand(action);
    sendCommand({ action });
    setTimeout(() => setActiveCommand(null), 1000); // UI feedback delay
  };

  const renderHaas = () => {
    if (data.machine !== 'haas-tl1') return null;
    return (
      <>
        <DataRow label="PROGRAM" value={data.program} />
        <DataRow label="SPINDLE" value={data.spindleRpm} unit="RPM" />
        <DataRow label="LOAD" value={data.spindleLoad} unit="%" />
        <DataRow label="FEED" value={data.feedRate} unit="MM/M" />
        <DataRow label="POWER" value={data.powerKw} unit="KW" />
      </>
    );
  };

  const renderMakino = () => {
    if (!data.machine.startsWith('makino')) return null;
    if (data.machine === 'haas-tl1' || data.machine === 'ur5e') return null; // Type guard

    return (
      <>
        <DataRow label="PROGRAM" value={data.program} />
        <DataRow label="SPINDLE" value={data.spindleRpm} unit="RPM" />
        <DataRow label="LOAD" value={data.spindleLoad} unit="%" />
        <DataRow label="FEED" value={data.feedRate} unit="MM/M" />
        <DataRow label="POWER" value={data.powerKw} unit="KW" />
      </>
    );
  };

  const renderUR5e = () => {
    if (data.machine !== 'ur5e') return null;
    return (
      <>
        <DataRow label="ROBOT MODE" value={data.robotMode} />
        <DataRow label="SAFETY MODE" value={data.safetyMode} />
        <DataRow label="TCP SPEED" value={data.tcpSpeed} unit="MM/S" />
        <DataRow label="POWER" value={data.powerKw} unit="KW" />
        
        <div className="control-buttons">
          <button className="control-btn" disabled={activeCommand === 'play'} onClick={() => handleCommand('play')}>
            {activeCommand === 'play' ? 'WAIT...' : 'PLAY'}
          </button>
          <button className="control-btn" disabled={activeCommand === 'pause'} onClick={() => handleCommand('pause')}>
            {activeCommand === 'pause' ? 'WAIT...' : 'PAUSE'}
          </button>
          <button className="control-btn" disabled={activeCommand === 'stop'} onClick={() => handleCommand('stop')}>
            {activeCommand === 'stop' ? 'WAIT...' : 'STOP'}
          </button>
          <button className="control-btn" disabled={activeCommand === 'home'} onClick={() => handleCommand('home')}>
            {activeCommand === 'home' ? 'WAIT...' : 'HOME'}
          </button>
        </div>
      </>
    );
  };

  return (
    <div className="machine-panel">
      <div className="panel-header">
        <StatusSquare status={data.status} />
        <span className="machine-name">{title}</span>
        {data.machine === 'ur5e' || data.machine === 'haas-tl1' ? (
           <span className="bridge-badge">TCP BRIDGE</span>
        ) : (
           <span className="bridge-badge">SIMULATED</span>
        )}
      </div>
      
      {renderHaas()}
      {renderMakino()}
      {renderUR5e()}

      {data.alarms && data.alarms.length > 0 && (
        <div className="alarm-row">
          {data.alarms.join(', ')}
        </div>
      )}
    </div>
  );
};
