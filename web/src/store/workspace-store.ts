import { create } from "zustand";
import type { C4Level } from "../types";

interface WorkspaceState {
  designId: string;
  activeLevel: C4Level;
  selectedElementId: string | null;
  inspectionPanelOpen: boolean;

  setDesignId: (id: string) => void;
  setActiveLevel: (level: C4Level) => void;
  selectElement: (id: string) => void;
  clearSelection: () => void;
  togglePanel: (open: boolean) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  designId: "",
  activeLevel: "container",
  selectedElementId: null,
  inspectionPanelOpen: false,

  setDesignId: (id) => set({ designId: id }),
  setActiveLevel: (level) => set({ activeLevel: level, selectedElementId: null, inspectionPanelOpen: false }),
  selectElement: (id) => set({ selectedElementId: id, inspectionPanelOpen: true }),
  clearSelection: () => set({ selectedElementId: null, inspectionPanelOpen: false }),
  togglePanel: (open) => set({ inspectionPanelOpen: open }),
}));
