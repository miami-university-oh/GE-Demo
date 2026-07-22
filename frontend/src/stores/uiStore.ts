import { create } from 'zustand';

export type LabViewMode = 'building' | 'list';

const STORAGE_KEY = 'labView';

// Read synchronously at store creation so the persisted choice renders on
// first paint with no flash of the wrong view.
function loadViewMode(): LabViewMode {
  return localStorage.getItem(STORAGE_KEY) === 'list' ? 'list' : 'building';
}

interface UiState {
  viewMode: LabViewMode;
  setViewMode: (mode: LabViewMode) => void;
}

export const useUiStore = create<UiState>(set => ({
  viewMode: loadViewMode(),
  setViewMode: mode => {
    localStorage.setItem(STORAGE_KEY, mode);
    set({ viewMode: mode });
  },
}));
