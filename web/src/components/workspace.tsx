"use client";

import { useAppStore } from "@/lib/store";
import { ScriptView } from "./views/script-view";
import { StoryboardView } from "./views/storyboard-view";
import { WorldView } from "./views/world-view";
import { GalleryView } from "./views/gallery-view";
import { ProgressView } from "./views/progress-view";

export function Workspace() {
  const { workspaceMode, currentProject } = useAppStore();

  // Progress view doesn't require a project to be loaded
  if (workspaceMode === "progress") {
    return (
      <main className="flex-1 overflow-hidden bg-background">
        <ProgressView />
      </main>
    );
  }

  if (!currentProject) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-secondary rounded-full flex items-center justify-center mx-auto">
            <span className="text-2xl">📁</span>
          </div>
          <div>
            <h2 className="text-lg font-semibold">No Project Loaded</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Select a project from the sidebar or create a new one
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className="flex-1 overflow-hidden bg-background">
      {workspaceMode === "script" && <ScriptView />}
      {workspaceMode === "storyboard" && <StoryboardView />}
      {workspaceMode === "world" && <WorldView />}
      {workspaceMode === "gallery" && <GalleryView />}
    </main>
  );
}

