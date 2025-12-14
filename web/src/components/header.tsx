"use client";

import { useState, useEffect } from "react";
import { cn, fetchAPI } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { MessageSquare, Settings, Wifi, WifiOff, FolderPlus, ChevronDown } from "lucide-react";
import { NewProjectModal } from "@/components/modals";

interface Project {
  name: string;
  path: string;
}

export function Header() {
  const {
    isConnected,
    assistantOpen,
    setAssistantOpen,
    settingsOpen,
    setSettingsOpen,
    currentProject,
    setCurrentProject,
    setProjectPath
  } = useAppStore();

  const [projects, setProjects] = useState<Project[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [newProjectOpen, setNewProjectOpen] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const data = await fetchAPI<Project[]>('/api/projects');
      setProjects(data || []);
    } catch (e) {
      console.error('Failed to load projects:', e);
      setProjects([]);
    }
  };

  const handleSelectProject = (project: Project) => {
    setCurrentProject({ name: project.name, path: project.path });
    setProjectPath(project.path);
    setDropdownOpen(false);
  };

  return (
    <header className="h-12 bg-card border-b border-border flex items-center justify-between px-4">
      {/* Left: Logo + Project Selector */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-xs">G</span>
          </div>
          <span className="font-semibold text-sm">Greenlight</span>
        </div>

        <span className="text-muted-foreground">/</span>

        {/* Project Dropdown */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded hover:bg-secondary text-sm"
          >
            <span className={currentProject ? "text-foreground" : "text-muted-foreground"}>
              {currentProject?.name || "Select Project"}
            </span>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </button>

          {dropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-64 bg-card border border-border rounded-md shadow-lg z-50">
              <div className="p-2">
                <button
                  onClick={() => {
                    setNewProjectOpen(true);
                    setDropdownOpen(false);
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded hover:bg-secondary text-sm text-primary"
                >
                  <FolderPlus className="h-4 w-4" />
                  New Project
                </button>
              </div>
              {projects.length > 0 && (
                <>
                  <div className="border-t border-border" />
                  <div className="p-2 max-h-60 overflow-y-auto">
                    {projects.map((project) => (
                      <button
                        key={project.path}
                        onClick={() => handleSelectProject(project)}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded text-sm hover:bg-secondary",
                          currentProject?.path === project.path && "bg-secondary"
                        )}
                      >
                        {project.name}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {projects.length === 0 && (
                <div className="p-3 text-sm text-muted-foreground text-center">
                  No projects found
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* New Project Modal */}
      <NewProjectModal open={newProjectOpen} onOpenChange={setNewProjectOpen} />

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        {/* Connection Status */}
        <div
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded text-xs",
            isConnected
              ? "bg-success/10 text-success"
              : "bg-error/10 text-error"
          )}
        >
          {isConnected ? (
            <>
              <Wifi className="h-3 w-3" />
              <span>Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3" />
              <span>Disconnected</span>
            </>
          )}
        </div>

        {/* Settings */}
        <button
          onClick={() => setSettingsOpen(true)}
          className="p-2 hover:bg-secondary rounded"
        >
          <Settings className="h-4 w-4 text-muted-foreground" />
        </button>

        {/* Assistant Toggle */}
        <button
          onClick={() => setAssistantOpen(!assistantOpen)}
          className={cn(
            "p-2 rounded transition-colors",
            assistantOpen
              ? "bg-primary text-primary-foreground"
              : "hover:bg-secondary text-muted-foreground"
          )}
        >
          <MessageSquare className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}

