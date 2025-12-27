"use client";

import { useAppStore, PipelineProcess, PipelineStage } from "@/lib/store";
import { cn, fetchAPI } from "@/lib/utils";
import {
  Activity,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Trash2,
  Clock,
  AlertCircle,
  Info,
  Settings,
  StopCircle,
  Ban,
} from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import { useEffect, useRef, useState } from "react";

// Status emoji/icon mapping
const getStatusIcon = (status: PipelineStage) => {
  switch (status) {
    case "initializing":
      return <Settings className="h-4 w-4 text-blue-400 animate-spin" />;
    case "running":
      return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
    case "complete":
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    case "error":
      return <XCircle className="h-4 w-4 text-red-400" />;
    default:
      return <Activity className="h-4 w-4 text-muted-foreground" />;
  }
};

const getStatusLabel = (status: PipelineStage) => {
  switch (status) {
    case "initializing":
      return "🔧 Initializing";
    case "running":
      return "🚀 Running";
    case "complete":
      return "✓ Complete";
    case "error":
      return "❌ Error";
    case "cancelled":
      return "🛑 Cancelled";
    default:
      return status;
  }
};

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

const formatTime = (date: Date) => {
  return new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const formatDuration = (start: Date, end?: Date) => {
  const endTime = end ? new Date(end).getTime() : Date.now();
  const duration = Math.floor((endTime - new Date(start).getTime()) / 1000);
  if (duration < 60) return `${duration}s`;
  const mins = Math.floor(duration / 60);
  const secs = duration % 60;
  return `${mins}m ${secs}s`;
};

function ProcessCard({ process }: { process: PipelineProcess }) {
  const { toggleProcessExpanded, cancelProcess, addProcessLog, currentProject } = useAppStore();
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (process.expanded && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [process.logs, process.expanded]);

  const isActive = process.status === "running" || process.status === "initializing";

  const handleCancel = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent expanding/collapsing
    if (!currentProject || cancelling) return;

    setCancelling(true);
    try {
      // Use backendId if available, otherwise try with local id
      const cancelId = process.backendId || process.id;
      // Try unified cancel endpoint first, fall back to legacy
      await fetchAPI(
        `/api/projects/${encodeURIComponent(currentProject.path)}/image-generation/cancel/${cancelId}`,
        { method: 'POST' }
      );
      addProcessLog(process.id, "Cancellation requested...", "warning");
    } catch {
      // Even if backend cancel fails, update UI state
      addProcessLog(process.id, "Cancellation requested (local)", "warning");
    }
    cancelProcess(process.id);
    setCancelling(false);
  };

  return (
    <div className={cn(
      "border rounded-lg overflow-hidden transition-all",
      isActive ? "border-primary/50 bg-primary/5" : "border-border bg-card/50",
      process.status === "cancelled" && "border-yellow-500/30 bg-yellow-500/5"
    )}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 hover:bg-secondary/30 transition-colors">
        <button
          onClick={() => toggleProcessExpanded(process.id)}
          className="flex items-center gap-3 flex-1"
        >
          {getStatusIcon(process.status)}
          <div className="text-left">
            <div className="font-medium text-sm">{process.name}</div>
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <Clock className="h-3 w-3" />
              {formatTime(process.startTime)}
              {process.endTime && ` - ${formatTime(process.endTime)}`}
              <span className="text-primary">({formatDuration(process.startTime, process.endTime)})</span>
            </div>
          </div>
        </button>
        <div className="flex items-center gap-2">
          {/* Cancel Button - only show for active processes */}
          {isActive && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded transition-colors"
              title="Cancel process"
            >
              {cancelling ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <StopCircle className="h-3 w-3" />
              )}
              Cancel
            </button>
          )}
          <span className={cn(
            "text-xs px-2 py-0.5 rounded",
            process.status === "complete" && "bg-green-500/20 text-green-400",
            process.status === "error" && "bg-red-500/20 text-red-400",
            process.status === "running" && "bg-primary/20 text-primary",
            process.status === "initializing" && "bg-blue-500/20 text-blue-400",
            process.status === "cancelled" && "bg-yellow-500/20 text-yellow-400"
          )}>
            {getStatusLabel(process.status)}
          </span>
          <button onClick={() => toggleProcessExpanded(process.id)}>
            {process.expanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
        </div>
      </div>

      {/* Progress Bar with enhanced status */}
      {isActive && (
        <div className="px-3 pb-2">
          {/* Current stage/item info */}
          {(process.currentStage || process.currentItem) && (
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
              <span className="flex items-center gap-1.5">
                {process.currentStage && (
                  <span className="text-primary font-medium">{process.currentStage}</span>
                )}
                {process.currentItem && (
                  <span className="text-muted-foreground truncate max-w-[200px]">
                    {process.currentStage ? "→ " : ""}{process.currentItem}
                  </span>
                )}
              </span>
              {process.totalItems !== undefined && process.completedItems !== undefined && (
                <span className="text-xs">
                  {process.completedItems}/{process.totalItems} items
                </span>
              )}
            </div>
          )}
          <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${process.progress * 100}%` }}
            />
          </div>
          <div className="text-xs text-muted-foreground text-right mt-1">
            {Math.round(process.progress * 100)}%
          </div>
        </div>
      )}

      {/* Expanded Content */}
      {process.expanded && (
        <div className="border-t border-border">
          {/* Stages */}
          {process.stages.length > 0 && (
            <div className="p-3 border-b border-border">
              <div className="text-xs font-medium text-muted-foreground mb-2">Pipeline Stages</div>
              <div className="space-y-1.5">
                {process.stages.map((stage, idx) => {
                  // Map backend status strings to our PipelineStage type
                  const status = stage.status === "pending" ? "initializing" :
                                stage.status as PipelineStage;
                  return (
                    <div key={`stage-${stage.name}-${idx}`} className={cn(
                      "flex items-center gap-2 text-xs py-1 px-2 rounded",
                      status === "running" && "bg-primary/10",
                      status === "complete" && "bg-green-500/10",
                      status === "error" && "bg-red-500/10"
                    )}>
                      {getStatusIcon(status)}
                      <span className={cn(
                        "flex-1 font-medium",
                        status === "running" && "text-primary",
                        status === "complete" && "text-green-400",
                        status === "error" && "text-red-400"
                      )}>{stage.name}</span>
                      {stage.message && (
                        <span className="text-muted-foreground truncate max-w-[200px]">{stage.message}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Logs */}
          <ScrollArea.Root className="max-h-[200px] overflow-hidden">
            <ScrollArea.Viewport className="h-full w-full p-3">
              <div className="text-xs font-medium text-muted-foreground mb-2">Logs</div>
              {process.logs.length === 0 ? (
                <div className="text-xs text-muted-foreground italic">No logs yet...</div>
              ) : (
                <div className="space-y-1 font-mono text-xs">
                  {process.logs.map((log, idx) => (
                    <div key={`log-${idx}-${log.timestamp.getTime()}`} className="flex items-start gap-2">
                      {getLogIcon(log.type)}
                      <span className="text-muted-foreground shrink-0">
                        [{formatTime(log.timestamp)}]
                      </span>
                      <span className={cn(
                        log.type === "error" && "text-red-400",
                        log.type === "success" && "text-green-400",
                        log.type === "warning" && "text-yellow-400"
                      )}>
                        {log.message}
                      </span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </ScrollArea.Viewport>
            <ScrollArea.Scrollbar
              className="flex select-none touch-none p-0.5 bg-secondary/30 transition-colors duration-150 ease-out data-[orientation=vertical]:w-2"
              orientation="vertical"
            >
              <ScrollArea.Thumb className="flex-1 bg-border rounded-full relative" />
            </ScrollArea.Scrollbar>
          </ScrollArea.Root>

          {/* Error Display */}
          {process.error && (
            <div className="p-3 bg-red-500/10 border-t border-red-500/30">
              <div className="flex items-start gap-2 text-xs text-red-400">
                <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{process.error}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ProgressView() {
  const { pipelineProcesses, clearCompletedProcesses } = useAppStore();

  const activeProcesses = pipelineProcesses.filter(
    (p) => p.status === "running" || p.status === "initializing"
  );
  const completedProcesses = pipelineProcesses.filter(
    (p) => p.status === "complete" || p.status === "error" || p.status === "cancelled"
  );

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Pipeline Progress</h2>
          {activeProcesses.length > 0 && (
            <span className="bg-primary/20 text-primary text-xs px-2 py-0.5 rounded-full">
              {activeProcesses.length} running
            </span>
          )}
        </div>
        {completedProcesses.length > 0 && (
          <button
            onClick={clearCompletedProcesses}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Trash2 className="h-3 w-3" />
            Clear completed
          </button>
        )}
      </div>

      {/* Content */}
      <ScrollArea.Root className="flex-1 overflow-hidden">
        <ScrollArea.Viewport className="h-full w-full p-4">
          {pipelineProcesses.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Activity className="h-12 w-12 text-muted-foreground/30 mb-4" />
              <h3 className="text-lg font-medium text-muted-foreground">No Active Pipelines</h3>
              <p className="text-sm text-muted-foreground/70 mt-1">
                Run a pipeline from the Writer or Director to see progress here.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Active Processes */}
              {activeProcesses.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Active
                  </h3>
                  {activeProcesses.map((process) => (
                    <ProcessCard key={process.id} process={process} />
                  ))}
                </div>
              )}

              {/* Completed Processes */}
              {completedProcesses.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Completed
                  </h3>
                  {completedProcesses.map((process) => (
                    <ProcessCard key={process.id} process={process} />
                  ))}
                </div>
              )}
            </div>
          )}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar
          className="flex select-none touch-none p-0.5 bg-secondary/30 transition-colors duration-150 ease-out data-[orientation=vertical]:w-2.5"
          orientation="vertical"
        >
          <ScrollArea.Thumb className="flex-1 bg-border rounded-full relative" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </div>
  );
}

