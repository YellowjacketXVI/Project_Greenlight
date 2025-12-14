"use client";

import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Activity, ChevronDown, ChevronUp, CheckCircle, XCircle, AlertCircle, Info, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";

export function ProgressPanel() {
  const {
    pipelineStatus,
    pipelineLogs,
    clearPipelineLogs,
    progressPanelOpen,
    setProgressPanelOpen,
    sidebarOpen,
  } = useAppStore();

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logsEndRef.current && progressPanelOpen) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [pipelineLogs, progressPanelOpen]);

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

  const isRunning = pipelineStatus?.status === "running";

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
            <span className="text-sm font-medium">
              {isRunning ? pipelineStatus?.name || "Running..." : "Progress"}
            </span>
          )}
        </div>
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            {isRunning && pipelineStatus?.progress !== undefined && (
              <span className="text-xs text-muted-foreground">
                {Math.round(pipelineStatus.progress * 100)}%
              </span>
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
      {isRunning && pipelineStatus?.progress !== undefined && (
        <div className="px-3 pb-2">
          <div className="h-1 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${pipelineStatus.progress * 100}%` }}
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
              {pipelineLogs.length} log entries
            </span>
            {pipelineLogs.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  clearPipelineLogs();
                }}
                className="p-1 hover:bg-secondary rounded text-muted-foreground hover:text-foreground"
                title="Clear logs"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            )}
          </div>

          {/* Logs List */}
          <div className="max-h-48 overflow-y-auto">
            {pipelineLogs.length === 0 ? (
              <div className="px-3 py-4 text-xs text-muted-foreground text-center">
                No pipeline activity yet
              </div>
            ) : (
              <div className="px-2 py-1 space-y-1">
                {pipelineLogs.map((log, index) => (
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

