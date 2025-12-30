"use client";

import { useAppStore } from "@/lib/store";
import { cn, fetchAPI } from "@/lib/utils";
import {
  CheckCircle,
  Clock,
  Loader2,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Play,
  RotateCcw,
  HardDrive,
  FastForward,
} from "lucide-react";
import { useEffect, useState } from "react";

interface Checkpoint {
  level: number;
  level_name: string;
  timestamp: string;
  artifacts_count: number;
  size_bytes: number;
  status: string;
}

interface CheckpointListResponse {
  project_path: string;
  checkpoints: Checkpoint[];
  highest_level: number | null;
  can_resume: boolean;
}

interface ResumeInfo {
  project_path: string;
  resume_level: number;
  description: string;
  passes_to_run: number[];
  estimated_time_saved: string;
}

const LEVEL_DESCRIPTIONS: Record<number, { title: string; description: string }> = {
  1: {
    title: "Story Structure",
    description: "World building, characters, locations, visual script",
  },
  2: {
    title: "References Ready",
    description: "Character and location reference images generated",
  },
  3: {
    title: "Key Frames Validated",
    description: "Key frames generated and validated for continuity",
  },
  4: {
    title: "Prompts Written",
    description: "All frame prompts written and ready for generation",
  },
  5: {
    title: "Complete",
    description: "All storyboard frames generated",
  },
};

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatTimestamp = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timestamp;
  }
};

export function CheckpointPanel() {
  const { currentProject, projectPath, addPipelineProcess } = useAppStore();
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [resumeInfo, setResumeInfo] = useState<ResumeInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRevertLevel, setSelectedRevertLevel] = useState<number | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);

  const loadCheckpoints = async () => {
    if (!projectPath) return;

    setLoading(true);
    setError(null);

    try {
      const [checkpointData, resumeData] = await Promise.all([
        fetchAPI<CheckpointListResponse>(`/api/pipelines/checkpoints/${encodeURIComponent(projectPath)}`),
        fetchAPI<ResumeInfo>(`/api/pipelines/checkpoints/${encodeURIComponent(projectPath)}/resume-info`),
      ]);

      setCheckpoints(checkpointData.checkpoints);
      setResumeInfo(resumeData);
    } catch (err) {
      console.error("Failed to load checkpoints:", err);
      setError("Failed to load checkpoints");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectPath) {
      loadCheckpoints();
    }
  }, [projectPath]);

  const handleClearCheckpoints = async () => {
    if (!projectPath) return;
    if (!confirm("Clear all checkpoints? This will force a fresh run.")) return;

    try {
      await fetchAPI(`/api/pipelines/checkpoints/${encodeURIComponent(projectPath)}`, {
        method: "DELETE",
      });
      await loadCheckpoints();
    } catch (err) {
      console.error("Failed to clear checkpoints:", err);
      setError("Failed to clear checkpoints");
    }
  };

  const handleInvalidateCheckpoint = async (level: number) => {
    if (!projectPath) return;
    if (!confirm(`Invalidate checkpoint level ${level} and higher? This will force re-execution from pass ${level}.`)) return;

    try {
      await fetchAPI(`/api/pipelines/checkpoints/${encodeURIComponent(projectPath)}/invalidate/${level}`, {
        method: "POST",
      });
      await loadCheckpoints();
    } catch (err) {
      console.error("Failed to invalidate checkpoint:", err);
      setError("Failed to invalidate checkpoint");
    }
  };

  const handleResumeFromCheckpoint = async () => {
    if (!projectPath || isExecuting) return;

    setIsExecuting(true);
    setError(null);

    try {
      const response = await fetchAPI<{ success: boolean; pipeline_id: string }>(`/api/pipelines/story`, {
        method: "POST",
        body: JSON.stringify({
          project_path: projectPath,
          resume_from_checkpoint: true,
          force_from_level: null,
        }),
      });

      if (response.success && response.pipeline_id) {
        // Add to pipeline processes for tracking
        addPipelineProcess({
          id: response.pipeline_id,
          name: "Story Phase (Resume)",
          status: "running",
          progress: 0,
          startTime: new Date(),
        });
      }
    } catch (err) {
      console.error("Failed to resume pipeline:", err);
      setError("Failed to resume pipeline");
    } finally {
      setIsExecuting(false);
    }
  };

  const handleRevertAndRun = async (level: number) => {
    if (!projectPath || isExecuting) return;

    const levelInfo = LEVEL_DESCRIPTIONS[level];
    if (!confirm(`Revert to level ${level} (${levelInfo.title}) and regenerate from there?\n\nThis will invalidate all checkpoints from level ${level} onwards and restart the pipeline.`)) {
      setSelectedRevertLevel(null);
      return;
    }

    setIsExecuting(true);
    setError(null);

    try {
      const response = await fetchAPI<{ success: boolean; pipeline_id: string }>(`/api/pipelines/story`, {
        method: "POST",
        body: JSON.stringify({
          project_path: projectPath,
          resume_from_checkpoint: true,
          force_from_level: level,
        }),
      });

      if (response.success && response.pipeline_id) {
        // Add to pipeline processes for tracking
        addPipelineProcess({
          id: response.pipeline_id,
          name: `Story Phase (Revert to L${level})`,
          status: "running",
          progress: 0,
          startTime: new Date(),
        });
        // Reload checkpoints after starting
        await loadCheckpoints();
      }
    } catch (err) {
      console.error("Failed to revert and run pipeline:", err);
      setError("Failed to revert and run pipeline");
    } finally {
      setIsExecuting(false);
      setSelectedRevertLevel(null);
    }
  };

  if (!currentProject) {
    return null;
  }

  const highestLevel = checkpoints.reduce((max, cp) =>
    cp.status === "valid" ? Math.max(max, cp.level) : max, 0
  );

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors">
        <button
          className="flex items-center gap-2 flex-1"
          onClick={() => setExpanded(!expanded)}
        >
          <HardDrive className="h-4 w-4 text-primary" />
          <span className="font-medium text-sm">Pipeline Checkpoints</span>
          {highestLevel > 0 && (
            <span className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-full">
              Level {highestLevel}
            </span>
          )}
        </button>
        <div className="flex items-center gap-2">
          <button
            className="p-1 hover:bg-muted rounded transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              loadCheckpoints();
            }}
            title="Refresh"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          </button>
          <button
            className="p-1"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* Resume Info with Action Buttons */}
          {resumeInfo && resumeInfo.resume_level > 0 && (
            <div className="p-3 bg-primary/5 border border-primary/20 rounded-lg space-y-3">
              <div className="flex items-start gap-2">
                <FastForward className="h-4 w-4 text-primary mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-primary">Resume Available</p>
                  <p className="text-xs text-muted-foreground mt-1">{resumeInfo.description}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Estimated time saved: <span className="text-foreground">{resumeInfo.estimated_time_saved}</span>
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                    isExecuting
                      ? "bg-primary/50 text-primary-foreground cursor-not-allowed"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  )}
                  onClick={handleResumeFromCheckpoint}
                  disabled={isExecuting}
                >
                  {isExecuting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Continue from Checkpoint
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="p-2 bg-destructive/10 border border-destructive/20 rounded text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          {/* Loading State */}
          {loading && checkpoints.length === 0 && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* No Checkpoints */}
          {!loading && checkpoints.length === 0 && (
            <div className="text-center py-4">
              <p className="text-sm text-muted-foreground">No checkpoints yet</p>
              <p className="text-xs text-muted-foreground mt-1">
                Run the pipeline to create checkpoints
              </p>
            </div>
          )}

          {/* Checkpoint List */}
          {checkpoints.length > 0 && (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((level) => {
                const checkpoint = checkpoints.find((cp) => cp.level === level);
                const levelInfo = LEVEL_DESCRIPTIONS[level];
                const isValid = checkpoint?.status === "valid";
                const canRevert = isValid && level < highestLevel;

                return (
                  <div
                    key={level}
                    className={cn(
                      "group flex items-start gap-3 p-2 rounded-lg border transition-colors",
                      isValid
                        ? "border-green-500/30 bg-green-500/5 hover:bg-green-500/10"
                        : "border-border bg-muted/30 opacity-60"
                    )}
                  >
                    {/* Status Icon */}
                    <div className="mt-0.5">
                      {isValid ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30" />
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium">
                          Pass {level}: {levelInfo.title}
                        </span>
                        {/* Revert Button - show for valid checkpoints that aren't the highest */}
                        {canRevert && (
                          <button
                            className={cn(
                              "opacity-0 group-hover:opacity-100 flex items-center gap-1 px-2 py-0.5 text-xs rounded transition-all",
                              "text-amber-500 hover:bg-amber-500/10 hover:text-amber-400"
                            )}
                            onClick={() => handleRevertAndRun(level)}
                            disabled={isExecuting}
                            title={`Revert to this checkpoint and regenerate from Pass ${level}`}
                          >
                            <RotateCcw className="h-3 w-3" />
                            Revert
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{levelInfo.description}</p>
                      {checkpoint && isValid && (
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTimestamp(checkpoint.timestamp)}
                          </span>
                          {checkpoint.size_bytes > 0 && (
                            <span>{formatBytes(checkpoint.size_bytes)}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Actions */}
          {checkpoints.some((cp) => cp.status === "valid") && (
            <div className="flex justify-end pt-2 border-t border-border">
              <button
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors"
                onClick={handleClearCheckpoints}
              >
                <Trash2 className="h-3 w-3" />
                Clear All Checkpoints
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
