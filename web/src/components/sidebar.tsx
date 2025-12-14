"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import {
  FileText,
  Image,
  Globe,
  Images,
  BookOpen,
  FolderOpen,
  FolderPlus,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { NewProjectModal, OpenProjectModal } from "@/components/modals";

const navItems = [
  { id: "script" as const, label: "Script", icon: FileText },
  { id: "storyboard" as const, label: "Storyboard", icon: Image },
  { id: "world" as const, label: "World Bible", icon: Globe },
  { id: "gallery" as const, label: "Gallery", icon: Images },
  { id: "references" as const, label: "References", icon: BookOpen },
];

export function Sidebar() {
  const {
    workspaceMode,
    setWorkspaceMode,
    sidebarOpen,
    setSidebarOpen,
    currentProject
  } = useAppStore();

  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [openProjectOpen, setOpenProjectOpen] = useState(false);

  return (
    <aside
      className={cn(
        "flex flex-col bg-card border-r border-border transition-all duration-300",
        sidebarOpen ? "w-56" : "w-14"
      )}
    >
      {/* Project Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        {sidebarOpen && (
          <div className="flex items-center gap-2 overflow-hidden">
            <FolderOpen className="h-4 w-4 text-primary shrink-0" />
            <span className="text-sm font-medium truncate">
              {currentProject?.name || "No Project"}
            </span>
          </div>
        )}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-1 hover:bg-secondary rounded"
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = workspaceMode === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setWorkspaceMode(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && (
                <span className="text-sm font-medium">{item.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Project Actions */}
      <div className="p-2 border-t border-border space-y-1">
        <button
          onClick={() => setNewProjectOpen(true)}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
            "hover:bg-secondary text-muted-foreground hover:text-foreground"
          )}
        >
          <FolderPlus className="h-4 w-4 shrink-0" />
          {sidebarOpen && <span className="text-sm">New Project</span>}
        </button>
        <button
          onClick={() => setOpenProjectOpen(true)}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
            "hover:bg-secondary text-muted-foreground hover:text-foreground"
          )}
        >
          <FolderOpen className="h-4 w-4 shrink-0" />
          {sidebarOpen && <span className="text-sm">Open Project</span>}
        </button>
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        {sidebarOpen && (
          <div className="text-xs text-muted-foreground">
            Project Greenlight
          </div>
        )}
      </div>

      {/* Project Modals */}
      <NewProjectModal open={newProjectOpen} onOpenChange={setNewProjectOpen} />
      <OpenProjectModal open={openProjectOpen} onOpenChange={setOpenProjectOpen} />
    </aside>
  );
}

