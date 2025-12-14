import { create } from "zustand";

export interface Project {
  name: string;
  path: string;
  lastModified?: string;
}

export interface PipelineStatus {
  name: string;
  status: "idle" | "running" | "completed" | "error";
  progress: number;
  message?: string;
}

export interface WorkspaceMode {
  mode: "script" | "storyboard" | "world" | "gallery" | "references";
}

interface AppState {
  // Project state
  currentProject: Project | null;
  projectPath: string;
  projects: Project[];
  setCurrentProject: (project: Project | null) => void;
  setProjectPath: (path: string) => void;
  setProjects: (projects: Project[]) => void;

  // Workspace state
  workspaceMode: WorkspaceMode["mode"];
  setWorkspaceMode: (mode: WorkspaceMode["mode"]) => void;

  // Pipeline state
  pipelineStatus: PipelineStatus | null;
  setPipelineStatus: (status: PipelineStatus | null) => void;

  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  assistantOpen: boolean;
  setAssistantOpen: (open: boolean) => void;

  // Modal state
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;

  // Connection state
  isConnected: boolean;
  setIsConnected: (connected: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Project state
  currentProject: null,
  projectPath: "",
  projects: [],
  setCurrentProject: (project) => set({
    currentProject: project,
    projectPath: project?.path || ""
  }),
  setProjectPath: (path) => set({ projectPath: path }),
  setProjects: (projects) => set({ projects }),

  // Workspace state
  workspaceMode: "script",
  setWorkspaceMode: (mode) => set({ workspaceMode: mode }),

  // Pipeline state
  pipelineStatus: null,
  setPipelineStatus: (status) => set({ pipelineStatus: status }),

  // UI state
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  assistantOpen: false,
  setAssistantOpen: (open) => set({ assistantOpen: open }),

  // Modal state
  settingsOpen: false,
  setSettingsOpen: (open) => set({ settingsOpen: open }),

  // Connection state
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
}));

// Alias for compatibility with modals
export const useStore = useAppStore;

