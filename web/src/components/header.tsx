"use client";

import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { MessageSquare, Settings, Wifi, WifiOff } from "lucide-react";

export function Header() {
  const {
    isConnected,
    assistantOpen,
    setAssistantOpen,
    settingsOpen,
    setSettingsOpen,
    currentProject
  } = useAppStore();

  return (
    <header className="h-12 bg-card border-b border-border flex items-center justify-between px-4">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-xs">G</span>
          </div>
          <span className="font-semibold text-sm">Greenlight</span>
        </div>
        {currentProject && (
          <>
            <span className="text-muted-foreground">/</span>
            <span className="text-sm text-muted-foreground">
              {currentProject.name}
            </span>
          </>
        )}
      </div>

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

