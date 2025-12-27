"use client";

import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Activity, ChevronDown, ChevronUp, CheckCircle, XCircle, AlertCircle, Info, Trash2 } from "lucide-react";
import { useEffect, useRef, useMemo } from "react";

export function ProgressPanel() {
  const {
    pipelineProcesses,
    progressPanelOpen,
    setProgressPanelOpen,
    sidebarOpen,
    setWorkspaceMode,
  } = useAppStore();

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Find the most recent active process or most recent completed
  const activeProcess = useMemo(() => {
    const active = pipelineProcesses.find(p => p.status === "running" || p.status === "initializing");
    if (active) return active;
    // Return most recent if no active
    return pipelineProcesses.length > 0 ? pipelineProcesses[pipelineProcesses.length - 1] : null;
  }, [pipelineProcesses]);

  const recentLogs = useMemo(() => {
    if (!activeProcess) return [];
    return activeProcess.logs.slice(-10); // Show last 10 logs
  }, [activeProcess]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logsEndRef.current && progressPanelOpen) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [recentLogs, progressPanelOpen]);

  const getLogIcon = (type: string) => {
    switch (type) {
      case "success":
        return <CheckCircle className="h-3 w-3 text-green-400 shrink-0" />;
      case "error":
        return <XCircle className="h-3 w-3 text-red-400 shrink-0" />;
      case "warning":
        return <AlertCircle className="h-3 w-3 text-yellow-400 shrink-0" />;
      default:
        return <Info className="h-3 w-3 text-blue-400 shrink-0" />;
    }
  };

  const isRunning = activeProcess?.status === "running" || activeProcess?.status === "initializing";

  const handleClick = () => {
    if (activeProcess) {
      setWorkspaceMode('progress');
    }
  };

  return (
    <div className="border-t border-border bg-card/50">
      {/* Header */}
      <button
        onClick={() => setProgressPanelOpen(!progressPanelOpen)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-secondary/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Activity
            className={cn(
              "h-4 w-4",
              isRunning ? "text-primary animate-pulse" : "text-muted-foreground"
            )}
          />
          {sidebarOpen && (
            <div className="flex flex-col items-start">
              <span className="text-sm font-medium">
                {isRunning ? activeProcess?.name || "Running..." : "Progress"}
              </span>
              {isRunning && activeProcess?.currentStage && (
                <span className="text-xs text-primary">{activeProcess.currentStage}</span>
              )}
            </div>
          )}
        </div>
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            {isRunning && activeProcess?.progress !== undefined && (
              <div className="flex flex-col items-end">
                <span className="text-xs text-muted-foreground">
                  {Math.round(activeProcess.progress * 100)}%
                </span>
                {activeProcess.totalItems !== undefined && activeProcess.completedItems !== undefined && (
                  <span className="text-xs text-muted-foreground">
                    {activeProcess.completedItems}/{activeProcess.totalItems}
                  </span>
                )}
              </div>
            )}
            {progressPanelOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        )}
      </button>

      {/* Progress Bar */}
      {isRunning && activeProcess?.progress !== undefined && (
        <div className="px-3 pb-2">
          {activeProcess.currentItem && (
            <div className="text-xs text-muted-foreground mb-1 truncate">
              {activeProcess.currentItem}
            </div>
          )}
          <div className="h-1 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${activeProcess.progress * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Logs Panel */}
      {progressPanelOpen && sidebarOpen && (
        <div className="border-t border-border">
          {/* Logs Header */}
          <div className="flex items-center justify-between px-3 py-1 bg-secondary/30">
            <span className="text-xs text-muted-foreground">
              {activeProcess ? `${recentLogs.length} recent logs` : "No activity"}
            </span>
            {activeProcess && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClick();
                }}
                className="text-xs text-primary hover:underline"
              >
                View all
              </button>
            )}
          </div>

          {/* Logs List */}
          <div className="max-h-48 overflow-y-auto">
            {recentLogs.length === 0 ? (
              <div className="px-3 py-4 text-xs text-muted-foreground text-center">
                No pipeline activity yet
              </div>
            ) : (
              <div className="px-2 py-1 space-y-1">
                {recentLogs.map((log, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-2 text-xs py-1 px-1 rounded hover:bg-secondary/30"
                  >
                    {getLogIcon(log.type)}
                    <span className="text-muted-foreground break-all">
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

