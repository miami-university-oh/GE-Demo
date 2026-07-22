import React from 'react';
import { useUiStore } from '../stores/uiStore';
import type { LabViewMode } from '../stores/uiStore';

const MODES: { mode: LabViewMode; label: string }[] = [
  { mode: 'building', label: 'BUILDING' },
  { mode: 'list', label: 'LIST' },
];

export const ViewToggle: React.FC = () => {
  const viewMode = useUiStore(s => s.viewMode);
  const setViewMode = useUiStore(s => s.setViewMode);

  return (
    <div>
      <div className="view-toggle-label">VIEW</div>
      <div className="view-toggle" role="group" aria-label="Lab view mode">
        {MODES.map(({ mode, label }) => (
          <button
            key={mode}
            type="button"
            className={`view-toggle-btn ${viewMode === mode ? 'active' : ''}`}
            aria-pressed={viewMode === mode}
            onClick={() => setViewMode(mode)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
};
