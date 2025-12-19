"use client";

import { useState, useEffect } from "react";
import { cn, fetchAPI } from "@/lib/utils";
import { useAppStore, type ActiveTab } from "@/lib/store";
import { Book, Clock, Layout, User, FolderPlus, ChevronDown, Settings } from "lucide-react";
import { NewProjectModal, WriterModal, DirectorModal, StoryboardModal, SettingsModal } from "@/components/modals";

interface Project {
  name: string;
  path: string;
}

const tabs: { id: ActiveTab; label: string; icon: typeof Book }[] = [
  { id: 'bible', label: 'World Bible', icon: Book },
  { id: 'chrono', label: 'Chronograph', icon: Clock },
  { id: 'boards', label: 'Storyboards', icon: Layout },
];

export function Header() {
  const {
    activeTab,
    setActiveTab,
    currentProject,
    setCurrentProject,
    setProjectPath,
    setSettingsOpen,
    settingsOpen,
  } = useAppStore();

  const [projects, setProjects] = useState<Project[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [writerOpen, setWriterOpen] = useState(false);
  const [directorOpen, setDirectorOpen] = useState(false);
  const [storyboardOpen, setStoryboardOpen] = useState(false);

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
    <header className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 shrink-0 z-10">
      {/* Left: Tab Navigation */}
      <div className="flex items-center gap-1 bg-slate-800/50 p-1 rounded-lg">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200",
                activeTab === tab.id
                  ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-900/50'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              )}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Center: Project Selector */}
      <div className="relative">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg hover:bg-slate-800 text-sm border border-slate-700"
        >
          <span className={currentProject ? "text-slate-200" : "text-slate-500"}>
            {currentProject?.name || "Select Project"}
          </span>
          <ChevronDown className="h-4 w-4 text-slate-500" />
        </button>

        {dropdownOpen && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50">
            <div className="p-2">
              <button
                onClick={() => {
                  setNewProjectOpen(true);
                  setDropdownOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded hover:bg-slate-800 text-sm text-cyan-400"
              >
                <FolderPlus className="h-4 w-4" />
                New Project
              </button>
            </div>
            {projects.length > 0 && (
              <>
                <div className="border-t border-slate-700" />
                <div className="p-2 max-h-60 overflow-y-auto custom-scrollbar">
                  {projects.map((project) => (
                    <button
                      key={project.path}
                      onClick={() => handleSelectProject(project)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded text-sm hover:bg-slate-800 text-slate-300",
                        currentProject?.path === project.path && "bg-slate-800 text-cyan-400"
                      )}
                    >
                      {project.name}
                    </button>
                  ))}
                </div>
              </>
            )}
            {projects.length === 0 && (
              <div className="p-3 text-sm text-slate-500 text-center">
                No projects found
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right: Quen Status + User */}
      <div className="flex items-center gap-4">
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-full border border-slate-700">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs text-slate-300 font-mono">Quen: Idle</span>
        </div>
        <button
          onClick={() => setSettingsOpen(true)}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
        >
          <Settings className="h-4 w-4 text-slate-400" />
        </button>
        <button className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 border border-slate-700">
          <User size={16} />
        </button>
      </div>

      {/* Modals */}
      <NewProjectModal open={newProjectOpen} onOpenChange={setNewProjectOpen} />
      <WriterModal open={writerOpen} onOpenChange={setWriterOpen} />
      <DirectorModal open={directorOpen} onOpenChange={setDirectorOpen} />
      <StoryboardModal open={storyboardOpen} onOpenChange={setStoryboardOpen} />
      <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} />
    </header>
  );
}

