"use client";

import { useAppStore } from "@/lib/store";
import { ScriptView } from "./views/script-view";
import { StoryboardView } from "./views/storyboard-view";
import { WorldView } from "./views/world-view";
import { GalleryView } from "./views/gallery-view";
import { ProgressView } from "./views/progress-view";
import { ChronographView } from "./views/chronograph-view";

export function Workspace() {
  const { activeTab, workspaceMode, currentProject } = useAppStore();

  // Progress view doesn't require a project to be loaded
  if (workspaceMode === "progress") {
    return (
      <main className="flex-1 overflow-hidden bg-black">
        <ProgressView />
      </main>
    );
  }

  // LucidLines tab-based navigation
  // Chronograph view doesn't require a project
  if (activeTab === "chrono") {
    return (
      <main className="flex-1 overflow-hidden bg-black">
        <ChronographView />
      </main>
    );
  }

  if (!currentProject) {
    return (
      <div className="flex-1 flex items-center justify-center bg-black">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-slate-900 rounded-full flex items-center justify-center mx-auto border border-slate-800">
            <span className="text-2xl">📁</span>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-200">No Project Loaded</h2>
            <p className="text-sm text-slate-500 mt-1">
              Select a project from the header or create a new one
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className="flex-1 overflow-hidden bg-black">
      {/* Tab-based views */}
      {activeTab === "bible" && <WorldView />}
      {activeTab === "boards" && <StoryboardView />}

      {/* Legacy workspace mode views (for backward compatibility) */}
      {workspaceMode === "script" && activeTab !== "bible" && activeTab !== "boards" && <ScriptView />}
      {workspaceMode === "gallery" && activeTab !== "bible" && activeTab !== "boards" && <GalleryView />}
    </main>
  );
}

