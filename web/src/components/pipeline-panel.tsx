"use client";

import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { Play, Loader2, CheckCircle, XCircle } from "lucide-react";
import * as Progress from "@radix-ui/react-progress";

const pipelines = [
  { id: "writer", label: "Writer", description: "Generate script from pitch" },
  { id: "director", label: "Director", description: "Create visual script" },
  { id: "references", label: "References", description: "Generate reference images" },
  { id: "storyboard", label: "Storyboard", description: "Generate storyboard frames" },
];

export function PipelinePanel() {
  const { pipelineStatus, currentProject } = useAppStore();

  const handleRunPipeline = async (pipelineId: string) => {
    // TODO: Implement pipeline execution via API
    console.log(`Running pipeline: ${pipelineId}`);
  };

  return (
    <aside className="w-64 bg-card border-l border-border flex flex-col">
      <div className="p-3 border-b border-border">
        <h2 className="font-semibold text-sm">Pipelines</h2>
      </div>

      <div className="flex-1 p-3 space-y-3 overflow-y-auto">
        {pipelines.map((pipeline) => {
          const isRunning = pipelineStatus?.name === pipeline.id && pipelineStatus.status === "running";
          const isCompleted = pipelineStatus?.name === pipeline.id && pipelineStatus.status === "completed";
          const isError = pipelineStatus?.name === pipeline.id && pipelineStatus.status === "error";

          return (
            <div
              key={pipeline.id}
              className="p-3 bg-secondary rounded-lg space-y-2"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-sm">{pipeline.label}</h3>
                  <p className="text-xs text-muted-foreground">
                    {pipeline.description}
                  </p>
                </div>
                <button
                  onClick={() => handleRunPipeline(pipeline.id)}
                  disabled={!currentProject || isRunning}
                  className={cn(
                    "p-2 rounded transition-colors",
                    !currentProject || isRunning
                      ? "bg-muted text-muted-foreground cursor-not-allowed"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  )}
                >
                  {isRunning ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : isCompleted ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : isError ? (
                    <XCircle className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </button>
              </div>

              {isRunning && pipelineStatus && (
                <div className="space-y-1">
                  <Progress.Root
                    className="h-1.5 bg-muted rounded-full overflow-hidden"
                    value={pipelineStatus.progress}
                  >
                    <Progress.Indicator
                      className="h-full bg-primary transition-all"
                      style={{ width: `${pipelineStatus.progress}%` }}
                    />
                  </Progress.Root>
                  {pipelineStatus.message && (
                    <p className="text-xs text-muted-foreground">
                      {pipelineStatus.message}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!currentProject && (
        <div className="p-3 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            Load a project to run pipelines
          </p>
        </div>
      )}
    </aside>
  );
}

