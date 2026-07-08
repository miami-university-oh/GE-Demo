import React from 'react';

export const FloorMap: React.FC = () => {
  return (
    <div className="floor-map">
      <div className="floor-map-title">Facility Layout</div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px dashed var(--border)' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>MAP PLACEHOLDER</span>
      </div>
    </div>
  );
};
