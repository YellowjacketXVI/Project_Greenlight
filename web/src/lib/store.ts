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

export interface PipelineLogEntry {
  timestamp: Date;
  message: string;
  type: "info" | "success" | "error" | "warning";
}

export interface WorkspaceMode {
  mode: "script" | "storyboard" | "world" | "gallery" | "progress";
}

// Enhanced pipeline process tracking
export type PipelineStage = "initializing" | "pending" | "running" | "complete" | "error" | "cancelled";

export interface PipelineStageInfo {
  name: string;
  status: PipelineStage;
  startTime?: Date;
  endTime?: Date;
  message?: string;
  started_at?: string;  // ISO string from backend
  completed_at?: string;  // ISO string from backend
}

export interface PipelineProcess {
  id: string;
  backendId?: string;  // Backend process ID for cancellation
  name: string;  // Writer, Director, World Bible, References, Storyboard
  status: PipelineStage;
  progress: number;
  startTime: Date;
  endTime?: Date;
  stages: PipelineStageInfo[];
  logs: PipelineLogEntry[];
  error?: string;
  expanded?: boolean;  // For UI expansion state
  currentStage?: string;  // Name of currently running stage
  currentItem?: string;  // Description of current item being processed
  totalItems?: number;  // Total items to process
  completedItems?: number;  // Number of items completed
  lastLogIndex?: number;  // Track which logs we've already processed
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

  // Pipeline state (legacy - for backward compatibility)
  pipelineStatus: PipelineStatus | null;
  setPipelineStatus: (status: PipelineStatus | null) => void;
  pipelineLogs: PipelineLogEntry[];
  addPipelineLog: (message: string, type?: PipelineLogEntry["type"]) => void;
  clearPipelineLogs: () => void;

  // Enhanced pipeline process tracking
  pipelineProcesses: PipelineProcess[];
  addPipelineProcess: (process: Omit<PipelineProcess, "logs" | "stages">) => void;
  updatePipelineProcess: (id: string, updates: Partial<PipelineProcess>) => void;
  addProcessLog: (processId: string, message: string, type?: PipelineLogEntry["type"]) => void;
  addProcessStage: (processId: string, stage: PipelineStageInfo) => void;
  updateProcessStage: (processId: string, stageName: string, updates: Partial<PipelineStageInfo>) => void;
  toggleProcessExpanded: (processId: string) => void;
  clearCompletedProcesses: () => void;
  cancelProcess: (processId: string) => void;

  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  assistantOpen: boolean;
  setAssistantOpen: (open: boolean) => void;
  progressPanelOpen: boolean;
  setProgressPanelOpen: (open: boolean) => void;

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

  // Pipeline state (legacy)
  pipelineStatus: null,
  setPipelineStatus: (status) => set({ pipelineStatus: status }),
  pipelineLogs: [],
  addPipelineLog: (message, type = "info") => set((state) => ({
    pipelineLogs: [...state.pipelineLogs, { timestamp: new Date(), message, type }]
  })),
  clearPipelineLogs: () => set({ pipelineLogs: [] }),

  // Enhanced pipeline process tracking
  pipelineProcesses: [],
  addPipelineProcess: (process) => set((state) => ({
    pipelineProcesses: [...state.pipelineProcesses, { ...process, logs: [], stages: [], expanded: true, lastLogIndex: 0 }]
  })),
  updatePipelineProcess: (id, updates) => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === id ? { ...p, ...updates } : p
    )
  })),
  addProcessLog: (processId, message, type = "info") => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === processId
        ? { ...p, logs: [...p.logs, { timestamp: new Date(), message, type }] }
        : p
    )
  })),
  addProcessStage: (processId, stage) => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === processId
        ? { ...p, stages: [...p.stages, stage] }
        : p
    )
  })),
  updateProcessStage: (processId, stageName, updates) => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === processId
        ? {
            ...p,
            stages: p.stages.map(s =>
              s.name === stageName ? { ...s, ...updates } : s
            )
          }
        : p
    )
  })),
  toggleProcessExpanded: (processId) => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === processId ? { ...p, expanded: !p.expanded } : p
    )
  })),
  clearCompletedProcesses: () => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.filter(
      p => p.status === "running" || p.status === "initializing"
    )
  })),
  cancelProcess: (processId) => set((state) => ({
    pipelineProcesses: state.pipelineProcesses.map(p =>
      p.id === processId
        ? { ...p, status: "cancelled" as PipelineStage, endTime: new Date() }
        : p
    )
  })),

  // UI state
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  assistantOpen: false,
  setAssistantOpen: (open) => set({ assistantOpen: open }),
  progressPanelOpen: true,
  setProgressPanelOpen: (open) => set({ progressPanelOpen: open }),

  // Modal state
  settingsOpen: false,
  setSettingsOpen: (open) => set({ settingsOpen: open }),

  // Connection state
  isConnected: false,
  setIsConnected: (connected) => set({ isConnected: connected }),
}));

// Alias for compatibility with modals
export const useStore = useAppStore;

