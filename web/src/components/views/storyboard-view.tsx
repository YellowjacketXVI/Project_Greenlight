"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn, API_BASE_URL } from "@/lib/utils";
import {
  Image as ImageIcon, RefreshCw, ZoomIn, ZoomOut, Grid, LayoutList, Camera, X,
  User, MapPin, Package, Sparkles, Calendar, Cloud, ChevronDown, ChevronRight,
  Edit3, RotateCcw, Plus, Trash2, Save, Eye, Lightbulb, Move, History,
  GitBranch, Clock, Archive, HardDrive, CheckCircle
} from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import * as Slider from "@radix-ui/react-slider";

interface Frame {
  id: string;
  scene: number;
  frame: number;
  camera: string;
  prompt: string;
  imagePath?: string;
  tags?: string[];
  // Extended metadata from visual_script.json
  camera_notation?: string;
  position_notation?: string;
  lighting_notation?: string;
  location_direction?: string;
  // Video motion prompt for AI video generation
  motion_prompt?: string;
  // Archived versions (previous iterations that were healed)
  archivedVersions?: string[];
}

interface VisualScriptData {
  total_frames: number;
  total_scenes: number;
  scenes: SceneData[];
}

interface SceneData {
  scene_number: number;
  frame_count: number;
  frames: FrameData[];
}

interface FrameData {
  frame_id: string;
  scene_number: number;
  frame_number: number;
  cameras?: string[];
  camera_notation?: string;
  position_notation?: string;
  lighting_notation?: string;
  location_direction?: string;
  motion_prompt?: string;
  prompt?: string;
  tags?: { characters?: string[]; locations?: string[]; props?: string[] };
}

interface FrameVersion {
  version_id: string;
  frame_id: string;
  image_path: string;
  created_at: string;
  iteration: number;
  is_compressed: boolean;
  compressed_path?: string;
  healing_notes: string;
  continuity_score: number;
  file_size_bytes: number;
}

interface Checkpoint {
  checkpoint_id: string;
  name: string;
  created_at: string;
  description: string;
  frame_versions: Record<string, string>;
  total_frames: number;
}

interface StorageStats {
  total_frames_tracked: number;
  total_versions: number;
  compressed_versions: number;
  uncompressed_versions: number;
  total_checkpoints: number;
  storage: {
    archive_mb: number;
    compressed_mb: number;
    thumbnails_mb: number;
    total_mb: number;
  };
}

type ViewMode = "grid" | "scenes";

// Calculate grid columns based on zoom level
function getGridColumns(zoom: number): number {
  if (zoom < 50) {
    const normalized = zoom / 49;
    return Math.max(3, Math.round(10 - normalized * 7));
  } else {
    const normalized = (zoom - 50) / 50;
    return Math.max(1, Math.round(3 - normalized * 2));
  }
}

// Get icon and color for a tag based on its prefix
function getTagStyle(tag: string): { icon: typeof User; color: string; bgColor: string } {
  const prefix = tag.split('_')[0];
  switch (prefix) {
    case 'CHAR':
      return { icon: User, color: 'text-blue-400', bgColor: 'bg-blue-500/20' };
    case 'LOC':
      return { icon: MapPin, color: 'text-green-400', bgColor: 'bg-green-500/20' };
    case 'PROP':
      return { icon: Package, color: 'text-orange-400', bgColor: 'bg-orange-500/20' };
    case 'CONCEPT':
      return { icon: Sparkles, color: 'text-purple-400', bgColor: 'bg-purple-500/20' };
    case 'EVENT':
      return { icon: Calendar, color: 'text-red-400', bgColor: 'bg-red-500/20' };
    case 'ENV':
      return { icon: Cloud, color: 'text-cyan-400', bgColor: 'bg-cyan-500/20' };
    default:
      return { icon: Sparkles, color: 'text-gray-400', bgColor: 'bg-gray-500/20' };
  }
}

// Get short display name from tag (e.g., CHAR_MEI -> MEI)
function getTagDisplayName(tag: string): string {
  const parts = tag.split('_');
  return parts.slice(1).join('_');
}

export function StoryboardView() {
  const { currentProject } = useAppStore();
  const [frames, setFrames] = useState<Frame[]>([]);
  const [visualScript, setVisualScript] = useState<VisualScriptData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(25);
  const [viewMode, setViewMode] = useState<ViewMode>("scenes");
  const [hoveredFrame, setHoveredFrame] = useState<string | null>(null);
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Scene/Frame expansion state
  const [expandedScenes, setExpandedScenes] = useState<Set<number>>(new Set());
  const [expandedFrameGroups, setExpandedFrameGroups] = useState<Set<string>>(new Set());

  // Editing state
  const [editingPrompt, setEditingPrompt] = useState<string | null>(null);
  const [editPromptText, setEditPromptText] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Version control state
  const [showVersionPanel, setShowVersionPanel] = useState(false);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  const [frameVersions, setFrameVersions] = useState<Record<string, FrameVersion[]>>({});
  const [selectedVersionFrame, setSelectedVersionFrame] = useState<string | null>(null);
  const [versionLoading, setVersionLoading] = useState(false);

  // API action handlers
  const handleUpdatePrompt = async (frameId: string, newPrompt: string) => {
    if (!currentProject) return;
    setActionLoading(frameId);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/frame/update-prompt`,
        { method: 'POST', body: JSON.stringify({ frame_id: frameId, prompt: newPrompt }) }
      );
      if (result.success) {
        // Update local state
        setFrames(prev => prev.map(f => f.id === frameId ? { ...f, prompt: newPrompt } : f));
        if (selectedFrame?.id === frameId) {
          setSelectedFrame({ ...selectedFrame, prompt: newPrompt });
        }
        setEditingPrompt(null);
      } else {
        alert(result.error || 'Failed to update prompt');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update prompt');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRegenerateFrame = async (frameId: string) => {
    if (!currentProject) return;
    setActionLoading(frameId);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string; message?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/frame/regenerate`,
        { method: 'POST', body: JSON.stringify({ frame_id: frameId }) }
      );
      if (result.success) {
        alert(result.message || 'Frame regeneration queued');
        // Reload frames to get updated image
        await loadFrames();
      } else {
        alert(result.error || 'Failed to regenerate frame');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to regenerate frame');
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddCameraAngle = async (frameId: string) => {
    if (!currentProject) return;
    const prompt = window.prompt('Enter prompt for new camera angle:');
    if (!prompt) return;

    setActionLoading(frameId);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string; frame_id?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/frame/add-camera`,
        { method: 'POST', body: JSON.stringify({ frame_id: frameId, prompt }) }
      );
      if (result.success) {
        alert(`Added camera angle: ${result.frame_id}`);
        await loadFrames();
      } else {
        alert(result.error || 'Failed to add camera angle');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to add camera angle');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteFrame = async (frameId: string) => {
    if (!currentProject) return;
    if (!window.confirm(`Delete frame ${frameId}? This cannot be undone.`)) return;

    setActionLoading(frameId);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/frame/${encodeURIComponent(frameId)}`,
        { method: 'DELETE' }
      );
      if (result.success) {
        setFrames(prev => prev.filter(f => f.id !== frameId));
        if (selectedFrame?.id === frameId) {
          setSelectedFrame(null);
        }
      } else {
        alert(result.error || 'Failed to delete frame');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete frame');
    } finally {
      setActionLoading(null);
    }
  };

  // Version control functions
  const loadVersionData = async () => {
    if (!currentProject) return;
    setVersionLoading(true);
    try {
      const [checkpointData, versionData] = await Promise.all([
        fetchAPI<{ checkpoints: Checkpoint[]; storage: StorageStats }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/checkpoints`
        ),
        fetchAPI<{ frames: Record<string, FrameVersion[]> }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/versions`
        )
      ]);
      setCheckpoints(checkpointData.checkpoints || []);
      setStorageStats(checkpointData.storage || null);
      setFrameVersions(versionData.frames || {});
    } catch (err) {
      console.error('Failed to load version data:', err);
    } finally {
      setVersionLoading(false);
    }
  };

  const handleCreateCheckpoint = async () => {
    if (!currentProject) return;
    const name = window.prompt('Enter checkpoint name:');
    if (!name) return;

    const description = window.prompt('Enter description (optional):') || '';
    setVersionLoading(true);
    try {
      const result = await fetchAPI<{ success: boolean; checkpoint: Checkpoint }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/checkpoints/create`,
        { method: 'POST', body: JSON.stringify({ name, description }) }
      );
      if (result.success) {
        await loadVersionData();
        alert(`Checkpoint "${name}" created successfully!`);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to create checkpoint');
    } finally {
      setVersionLoading(false);
    }
  };

  const handleRestoreCheckpoint = async (checkpointId: string, checkpointName: string) => {
    if (!currentProject) return;
    if (!window.confirm(`Restore all frames to checkpoint "${checkpointName}"? Current frames will be archived first.`)) return;

    setVersionLoading(true);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/checkpoints/restore`,
        { method: 'POST', body: JSON.stringify({ checkpoint_id: checkpointId }) }
      );
      if (result.success) {
        await loadFrames();
        await loadVersionData();
        alert('Checkpoint restored successfully!');
      } else {
        alert(result.error || 'Failed to restore checkpoint');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to restore checkpoint');
    } finally {
      setVersionLoading(false);
    }
  };

  const handleRestoreVersion = async (frameId: string, versionId: string, iteration: number) => {
    if (!currentProject) return;
    if (!window.confirm(`Restore frame ${frameId} to version ${iteration}? Current version will be archived.`)) return;

    setVersionLoading(true);
    try {
      const result = await fetchAPI<{ success: boolean; error?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/versions/restore`,
        { method: 'POST', body: JSON.stringify({ frame_id: frameId, version_id: versionId }) }
      );
      if (result.success) {
        await loadFrames();
        await loadVersionData();
        alert(`Frame restored to version ${iteration}!`);
      } else {
        alert(result.error || 'Failed to restore version');
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to restore version');
    } finally {
      setVersionLoading(false);
    }
  };

  const handleDeleteCheckpoint = async (checkpointId: string) => {
    if (!currentProject) return;
    if (!window.confirm('Delete this checkpoint? The archived files will remain.')) return;

    try {
      const result = await fetchAPI<{ success: boolean }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard/checkpoints/${encodeURIComponent(checkpointId)}`,
        { method: 'DELETE' }
      );
      if (result.success) {
        await loadVersionData();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete checkpoint');
    }
  };

  const loadFrames = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ frames: Frame[]; visual_script?: VisualScriptData }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard`
      );

      // Merge frame data with visual_script metadata
      const enrichedFrames = (data.frames || []).map(frame => {
        if (data.visual_script?.scenes) {
          const scene = data.visual_script.scenes.find(s => s.scene_number === frame.scene);
          if (scene) {
            const frameData = scene.frames.find(f => f.frame_id === frame.id);
            if (frameData) {
              return {
                ...frame,
                camera_notation: frameData.camera_notation,
                position_notation: frameData.position_notation,
                lighting_notation: frameData.lighting_notation,
                location_direction: frameData.location_direction,
                motion_prompt: frameData.motion_prompt,
              };
            }
          }
        }
        return frame;
      });

      setFrames(enrichedFrames);
      setVisualScript(data.visual_script || null);

      // Auto-expand first scene
      if (data.visual_script?.scenes?.length) {
        setExpandedScenes(new Set([data.visual_script.scenes[0].scene_number]));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load storyboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFrames();
  }, [currentProject]);

  // Group frames by scene, then by frame number (for camera grouping)
  const framesByScene = useMemo(() => {
    const groups: Record<number, Record<number, Frame[]>> = {};
    frames.forEach((frame) => {
      if (!groups[frame.scene]) groups[frame.scene] = {};
      if (!groups[frame.scene][frame.frame]) groups[frame.scene][frame.frame] = [];
      groups[frame.scene][frame.frame].push(frame);
    });
    return groups;
  }, [frames]);

  const gridColumns = getGridColumns(zoom);
  const isRowMode = zoom >= 50;

  // Toggle functions
  const toggleScene = (sceneNum: number) => {
    setExpandedScenes(prev => {
      const next = new Set(prev);
      if (next.has(sceneNum)) next.delete(sceneNum);
      else next.add(sceneNum);
      return next;
    });
  };

  const toggleFrameGroup = (key: string) => {
    setExpandedFrameGroups(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => {
    const allScenes = new Set(Object.keys(framesByScene).map(Number));
    const allFrameKeys = new Set<string>();
    Object.entries(framesByScene).forEach(([sceneNum, frameGroups]) => {
      Object.keys(frameGroups).forEach(frameNum => {
        allFrameKeys.add(`${sceneNum}.${frameNum}`);
      });
    });
    setExpandedScenes(allScenes);
    setExpandedFrameGroups(allFrameKeys);
  };

  const collapseAll = () => {
    setExpandedScenes(new Set());
    setExpandedFrameGroups(new Set());
  };

  // Navigate in lightbox
  const navigateFrame = useCallback((direction: 1 | -1) => {
    if (!selectedFrame) return;
    const idx = frames.findIndex(f => f.id === selectedFrame.id);
    const newIdx = Math.max(0, Math.min(frames.length - 1, idx + direction));
    setSelectedFrame(frames[newIdx]);
    setCurrentIndex(newIdx);
  }, [selectedFrame, frames]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedFrame) return;
      if (e.key === "ArrowLeft") navigateFrame(-1);
      if (e.key === "ArrowRight") navigateFrame(1);
      if (e.key === "Escape") setSelectedFrame(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedFrame, navigateFrame]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-destructive">{error}</p>
          <button onClick={loadFrames} className="text-sm text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (frames.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Storyboard Frames</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Director and Storyboard pipelines to generate frames
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-border bg-card/50">
        <div className="flex items-center gap-4">
          <h2 className="font-semibold flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Storyboard
          </h2>
          <span className="text-sm text-muted-foreground">
            {frames.length} frames • {Object.keys(framesByScene).length} scenes
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-secondary rounded-lg p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "p-1.5 rounded transition-colors",
                viewMode === "grid" ? "bg-primary text-primary-foreground" : "hover:bg-secondary-foreground/10"
              )}
              title="Grid View"
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("scenes")}
              className={cn(
                "p-1.5 rounded transition-colors",
                viewMode === "scenes" ? "bg-primary text-primary-foreground" : "hover:bg-secondary-foreground/10"
              )}
              title="Scene View"
            >
              <LayoutList className="h-4 w-4" />
            </button>
          </div>

          {/* Expand/Collapse for Scene View */}
          {viewMode === "scenes" && (
            <button
              onClick={expandedScenes.size > 0 ? collapseAll : expandAll}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {expandedScenes.size > 0 ? "Collapse All" : "Expand All"}
            </button>
          )}

          {/* Zoom Slider */}
          <div className="flex items-center gap-2 w-48">
            <ZoomOut className="h-4 w-4 text-muted-foreground" />
            <Slider.Root
              className="relative flex items-center select-none touch-none w-full h-5"
              value={[zoom]}
              onValueChange={([v]) => setZoom(v)}
              max={100}
              step={1}
            >
              <Slider.Track className="bg-secondary relative grow rounded-full h-1.5">
                <Slider.Range className="absolute bg-primary rounded-full h-full" />
              </Slider.Track>
              <Slider.Thumb className="block w-4 h-4 bg-primary rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/50" />
            </Slider.Root>
            <ZoomIn className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground w-8">{zoom}%</span>
          </div>

          {/* Version Control Button */}
          <button
            onClick={() => {
              setShowVersionPanel(!showVersionPanel);
              if (!showVersionPanel) loadVersionData();
            }}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors",
              showVersionPanel
                ? "bg-primary text-primary-foreground"
                : "bg-secondary hover:bg-secondary/80"
            )}
            title="Version History"
          >
            <History className="h-4 w-4" />
            <span className="text-sm">History</span>
          </button>
        </div>
      </div>

      {/* Version Control Panel */}
      {showVersionPanel && (
        <div className="border-b border-border bg-card/80 backdrop-blur-sm">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <GitBranch className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">Version Control</h3>
                {storageStats && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <HardDrive className="h-3 w-3" />
                    {storageStats.storage.total_mb.toFixed(1)}MB used
                  </span>
                )}
              </div>
              <button
                onClick={handleCreateCheckpoint}
                disabled={versionLoading}
                className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                Create Checkpoint
              </button>
            </div>

            {versionLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-4">
                {/* Checkpoints */}
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    Checkpoints ({checkpoints.length})
                  </h4>
                  {checkpoints.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">
                      No checkpoints yet. Create one to save the current state.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                      {checkpoints.slice(0, 6).map((cp) => (
                        <div
                          key={cp.checkpoint_id}
                          className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg border border-border"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm truncate">{cp.name}</div>
                            <div className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(cp.created_at).toLocaleDateString()}
                              <span className="mx-1">•</span>
                              {cp.total_frames} frames
                            </div>
                            {cp.description && (
                              <div className="text-xs text-muted-foreground truncate mt-0.5">
                                {cp.description}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-1 ml-2">
                            <button
                              onClick={() => handleRestoreCheckpoint(cp.checkpoint_id, cp.name)}
                              className="p-1.5 hover:bg-primary/20 rounded transition-colors"
                              title="Restore this checkpoint"
                            >
                              <RotateCcw className="h-4 w-4 text-primary" />
                            </button>
                            <button
                              onClick={() => handleDeleteCheckpoint(cp.checkpoint_id)}
                              className="p-1.5 hover:bg-destructive/20 rounded transition-colors"
                              title="Delete checkpoint"
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Frame Versions Summary */}
                {Object.keys(frameVersions).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                      <Archive className="h-4 w-4" />
                      Healed Frames ({Object.keys(frameVersions).length})
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(frameVersions).slice(0, 10).map(([frameId, versions]) => (
                        <button
                          key={frameId}
                          onClick={() => setSelectedVersionFrame(selectedVersionFrame === frameId ? null : frameId)}
                          className={cn(
                            "px-2 py-1 text-xs rounded-full border transition-colors",
                            selectedVersionFrame === frameId
                              ? "bg-primary text-primary-foreground border-primary"
                              : "bg-secondary/50 border-border hover:border-primary"
                          )}
                        >
                          {frameId} ({versions.length}v)
                        </button>
                      ))}
                      {Object.keys(frameVersions).length > 10 && (
                        <span className="px-2 py-1 text-xs text-muted-foreground">
                          +{Object.keys(frameVersions).length - 10} more
                        </span>
                      )}
                    </div>

                    {/* Selected Frame Version History */}
                    {selectedVersionFrame && frameVersions[selectedVersionFrame] && (
                      <div className="mt-3 p-3 bg-secondary/30 rounded-lg border border-border">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">Version history for {selectedVersionFrame}</span>
                          <button
                            onClick={() => setSelectedVersionFrame(null)}
                            className="p-1 hover:bg-secondary rounded"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="flex gap-2 overflow-x-auto pb-2">
                          {frameVersions[selectedVersionFrame].map((version) => (
                            <div
                              key={version.version_id}
                              className="flex-shrink-0 w-32 bg-card rounded border border-border overflow-hidden"
                            >
                              <div className="aspect-video bg-black relative">
                                <img
                                  src={`${API_BASE_URL}/api/projects/${encodeURIComponent(currentProject?.path || '')}/storyboard/versions/image/${encodeURIComponent(version.version_id)}?thumbnail=true`}
                                  alt={`Version ${version.iteration}`}
                                  className="w-full h-full object-contain"
                                />
                                {version.is_compressed && (
                                  <div className="absolute top-1 right-1 px-1 py-0.5 bg-amber-500/80 text-white text-[10px] rounded">
                                    Compressed
                                  </div>
                                )}
                              </div>
                              <div className="p-1.5">
                                <div className="text-xs font-medium">v{version.iteration}</div>
                                <div className="text-[10px] text-muted-foreground">
                                  {new Date(version.created_at).toLocaleDateString()}
                                </div>
                                {version.continuity_score > 0 && (
                                  <div className="text-[10px] text-muted-foreground">
                                    Score: {version.continuity_score.toFixed(1)}
                                  </div>
                                )}
                                <button
                                  onClick={() => handleRestoreVersion(version.frame_id, version.version_id, version.iteration)}
                                  className="w-full mt-1 px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded transition-colors"
                                >
                                  Restore
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Storage Stats */}
                {storageStats && storageStats.total_versions > 0 && (
                  <div className="text-xs text-muted-foreground flex items-center gap-4">
                    <span>{storageStats.total_versions} total versions</span>
                    <span>{storageStats.compressed_versions} compressed</span>
                    <span>{storageStats.storage.archive_mb.toFixed(1)}MB archives</span>
                    <span>{storageStats.storage.thumbnails_mb.toFixed(1)}MB thumbnails</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Frames Display - Fixed height container for proper scrolling */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea.Root className="h-full">
          <ScrollArea.Viewport className="h-full w-full">
            <div className="p-4">
              {viewMode === "grid" ? (
                <div
                  className="grid gap-3 transition-all duration-200"
                  style={{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }}
                >
                  {frames.map((frame) => (
                    <FrameCard
                      key={frame.id}
                      frame={frame}
                      isHovered={hoveredFrame === frame.id}
                      isRowMode={isRowMode}
                      onHover={() => setHoveredFrame(frame.id)}
                      onLeave={() => setHoveredFrame(null)}
                      onClick={() => {
                        setSelectedFrame(frame);
                        setCurrentIndex(frames.indexOf(frame));
                      }}
                    />
                  ))}
                </div>
              ) : (
                /* Scene-based hierarchical view */
                <div className="space-y-3 max-w-5xl mx-auto">
                  {Object.entries(framesByScene).map(([sceneNumStr, frameGroups]) => {
                    const sceneNum = Number(sceneNumStr);
                    const isSceneExpanded = expandedScenes.has(sceneNum);
                    const totalCameras = Object.values(frameGroups).flat().length;
                    const totalFrameGroups = Object.keys(frameGroups).length;

                    // Collect all tags in this scene
                    const sceneTags = new Set<string>();
                    Object.values(frameGroups).flat().forEach(f => {
                      f.tags?.forEach(t => sceneTags.add(t));
                    });

                    return (
                      <div key={sceneNum} className="border border-border rounded-lg overflow-hidden bg-card">
                        {/* Scene Header */}
                        <button
                          onClick={() => toggleScene(sceneNum)}
                          className="w-full flex items-center gap-3 p-3 hover:bg-secondary/50 transition-colors"
                        >
                          {isSceneExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                          <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-sm font-medium rounded">
                            Scene {sceneNum}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            {totalFrameGroups} frames • {totalCameras} cameras
                          </span>

                          {/* Tag preview when collapsed */}
                          {!isSceneExpanded && sceneTags.size > 0 && (
                            <div className="flex gap-1 ml-auto">
                              {Array.from(sceneTags).slice(0, 4).map(tag => {
                                const { icon: TagIcon, color, bgColor } = getTagStyle(tag);
                                return (
                                  <div key={tag} className={cn("p-1 rounded", bgColor)} title={tag}>
                                    <TagIcon className={cn("h-3 w-3", color)} />
                                  </div>
                                );
                              })}
                              {sceneTags.size > 4 && (
                                <span className="text-xs text-muted-foreground">+{sceneTags.size - 4}</span>
                              )}
                            </div>
                          )}
                        </button>

                        {/* Scene Content - Frame Groups */}
                        {isSceneExpanded && (
                          <div className="border-t border-border">
                            {Object.entries(frameGroups).map(([frameNumStr, cameras]) => {
                              const frameNum = Number(frameNumStr);
                              const frameKey = `${sceneNum}.${frameNum}`;
                              const isFrameExpanded = expandedFrameGroups.has(frameKey);

                              return (
                                <div key={frameKey} className="border-b border-border last:border-b-0">
                                  {/* Frame Group Header */}
                                  <button
                                    onClick={() => toggleFrameGroup(frameKey)}
                                    className="w-full flex items-center gap-3 p-2 pl-8 hover:bg-secondary/30 transition-colors"
                                  >
                                    {isFrameExpanded ? (
                                      <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                    ) : (
                                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                                    )}
                                    <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs font-mono rounded">
                                      {sceneNum}.{frameNum}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                      {cameras.length} camera{cameras.length > 1 ? 's' : ''}
                                    </span>

                                    {/* Camera labels preview */}
                                    {!isFrameExpanded && (
                                      <div className="flex gap-1 ml-auto">
                                        {cameras.map(cam => (
                                          <span key={cam.id} className="px-1 py-0.5 bg-secondary text-xs rounded">
                                            {cam.camera}
                                          </span>
                                        ))}
                                      </div>
                                    )}
                                  </button>

                                  {/* Camera Cards */}
                                  {isFrameExpanded && (
                                    <div className="p-3 pl-12 space-y-3 bg-secondary/20">
                                      {cameras.map((camera) => (
                                        <CameraCard
                                          key={camera.id}
                                          frame={camera}
                                          isHovered={hoveredFrame === camera.id}
                                          onHover={() => setHoveredFrame(camera.id)}
                                          onLeave={() => setHoveredFrame(null)}
                                          onClick={() => {
                                            setSelectedFrame(camera);
                                            setCurrentIndex(frames.indexOf(camera));
                                          }}
                                        />
                                      ))}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </ScrollArea.Viewport>
          <ScrollArea.Scrollbar
            className="flex select-none touch-none p-0.5 bg-secondary transition-colors hover:bg-secondary/80 data-[orientation=vertical]:w-2.5 data-[orientation=horizontal]:flex-col data-[orientation=horizontal]:h-2.5"
            orientation="vertical"
          >
            <ScrollArea.Thumb className="flex-1 bg-muted-foreground/50 rounded-full relative before:content-[''] before:absolute before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:w-full before:h-full before:min-w-[44px] before:min-h-[44px]" />
          </ScrollArea.Scrollbar>
        </ScrollArea.Root>
      </div>

      {/* Timeline Navigator */}
      <div className="h-16 border-t border-border bg-card/50 p-2">
        <div className="h-full flex gap-1 overflow-x-auto">
          {frames.map((frame, idx) => (
            <button
              key={frame.id}
              onClick={() => {
                setSelectedFrame(frame);
                setCurrentIndex(idx);
              }}
              className={cn(
                "h-full aspect-video rounded overflow-hidden border-2 transition-all flex-shrink-0",
                selectedFrame?.id === frame.id
                  ? "border-primary scale-105"
                  : "border-transparent hover:border-primary/50"
              )}
            >
              {frame.imagePath ? (
                <img
                  src={`${API_BASE_URL}/api/images/${encodeURIComponent(frame.imagePath)}`}
                  alt={frame.id}
                  className="w-full h-full object-contain bg-black"
                />
              ) : (
                <div className="w-full h-full bg-secondary flex items-center justify-center">
                  <ImageIcon className="h-3 w-3 text-muted-foreground" />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Enhanced Lightbox Modal with Metadata Panel */}
      {selectedFrame && (
        <div className="fixed inset-0 z-50 bg-black/95 flex" onClick={() => setSelectedFrame(null)}>
          {/* Close button */}
          <button
            className="absolute top-4 right-4 p-2 text-white hover:bg-white/10 rounded-full z-10"
            onClick={() => setSelectedFrame(null)}
          >
            <X className="h-6 w-6" />
          </button>

          {/* Navigation buttons */}
          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full disabled:opacity-30 z-10"
            onClick={(e) => { e.stopPropagation(); navigateFrame(-1); }}
            disabled={currentIndex === 0}
          >
            ←
          </button>
          <button
            className="absolute right-80 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full disabled:opacity-30 z-10"
            onClick={(e) => { e.stopPropagation(); navigateFrame(1); }}
            disabled={currentIndex === frames.length - 1}
          >
            →
          </button>

          {/* Main Image Area */}
          <div className="flex-1 flex items-center justify-center p-8" onClick={(e) => e.stopPropagation()}>
            {selectedFrame.imagePath ? (
              <img
                src={`${API_BASE_URL}/api/images/${encodeURIComponent(selectedFrame.imagePath)}`}
                alt={selectedFrame.id}
                className="max-h-full max-w-full object-contain rounded-lg"
              />
            ) : (
              <div className="w-96 h-64 bg-secondary rounded-lg flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
            )}
          </div>

          {/* Metadata Panel */}
          <div
            className="w-80 bg-card/95 border-l border-border p-4 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Frame ID Header */}
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="px-2 py-1 bg-primary rounded text-sm font-mono">[{selectedFrame.id}]</span>
                <span className="flex items-center gap-1 text-sm text-muted-foreground">
                  <Camera className="h-4 w-4" />
                  {selectedFrame.camera || "cA"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{currentIndex + 1} / {frames.length}</p>
            </div>

            {/* Camera Notation */}
            {selectedFrame.camera_notation && (
              <div className="mb-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <Camera className="h-3 w-3" />
                  Camera
                </div>
                <p className="text-sm bg-secondary/50 p-2 rounded">{selectedFrame.camera_notation}</p>
              </div>
            )}

            {/* Position Notation */}
            {selectedFrame.position_notation && (
              <div className="mb-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <Move className="h-3 w-3" />
                  Position
                </div>
                <p className="text-sm bg-secondary/50 p-2 rounded">{selectedFrame.position_notation}</p>
              </div>
            )}

            {/* Lighting Notation */}
            {selectedFrame.lighting_notation && (
              <div className="mb-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <Lightbulb className="h-3 w-3" />
                  Lighting
                </div>
                <p className="text-sm bg-secondary/50 p-2 rounded">{selectedFrame.lighting_notation}</p>
              </div>
            )}

            {/* Motion Prompt */}
            {selectedFrame.motion_prompt && (
              <div className="mb-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <RefreshCw className="h-3 w-3" />
                  Video Motion
                </div>
                <p className="text-sm bg-purple-500/20 text-purple-300 p-2 rounded border border-purple-500/30">
                  {selectedFrame.motion_prompt}
                </p>
              </div>
            )}

            {/* Tags */}
            {selectedFrame.tags && selectedFrame.tags.length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-muted-foreground mb-1">Tags</div>
                <div className="flex flex-wrap gap-1">
                  {selectedFrame.tags.map(tag => {
                    const { icon: TagIcon, color, bgColor } = getTagStyle(tag);
                    return (
                      <div key={tag} className={cn("flex items-center gap-1 px-1.5 py-0.5 rounded text-xs", bgColor, color)}>
                        <TagIcon className="h-3 w-3" />
                        <span>{getTagDisplayName(tag)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Prompt - Editable */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground">Prompt</span>
                {editingPrompt === selectedFrame.id ? (
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleUpdatePrompt(selectedFrame.id, editPromptText)}
                      disabled={actionLoading === selectedFrame.id}
                      className="text-xs text-green-400 hover:underline flex items-center gap-1"
                    >
                      <Save className="h-3 w-3" />
                      Save
                    </button>
                    <button
                      onClick={() => setEditingPrompt(null)}
                      className="text-xs text-muted-foreground hover:underline"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setEditingPrompt(selectedFrame.id);
                      setEditPromptText(selectedFrame.prompt);
                    }}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    <Edit3 className="h-3 w-3" />
                    Edit
                  </button>
                )}
              </div>
              {editingPrompt === selectedFrame.id ? (
                <textarea
                  value={editPromptText}
                  onChange={(e) => setEditPromptText(e.target.value)}
                  className="w-full text-sm bg-secondary/50 p-2 rounded max-h-40 min-h-[80px] resize-y border border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary"
                />
              ) : (
                <p className="text-sm bg-secondary/50 p-2 rounded max-h-40 overflow-y-auto">
                  {selectedFrame.prompt}
                </p>
              )}
            </div>

            {/* Action Buttons */}
            <div className="space-y-2 pt-3 border-t border-border">
              <button
                onClick={() => handleRegenerateFrame(selectedFrame.id)}
                disabled={actionLoading === selectedFrame.id}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors text-sm disabled:opacity-50"
              >
                {actionLoading === selectedFrame.id ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <RotateCcw className="h-4 w-4" />
                )}
                Regenerate Frame
              </button>
              <button
                onClick={() => handleAddCameraAngle(selectedFrame.id)}
                disabled={actionLoading === selectedFrame.id}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded hover:bg-secondary/80 transition-colors text-sm disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                Add Camera Angle
              </button>
              <button
                onClick={() => handleDeleteFrame(selectedFrame.id)}
                disabled={actionLoading === selectedFrame.id}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-destructive hover:bg-destructive/10 rounded transition-colors text-sm disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                Delete Frame
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FrameCard({
  frame,
  isHovered,
  isRowMode,
  onHover,
  onLeave,
  onClick,
  className,
}: {
  frame: Frame;
  isHovered: boolean;
  isRowMode: boolean;
  onHover: () => void;
  onLeave: () => void;
  onClick: () => void;
  className?: string;
}) {
  const tags = frame.tags || [];
  const hasArchivedVersions = frame.archivedVersions && frame.archivedVersions.length > 0;

  return (
    <div className="relative">
      {/* Archived version thumbnails stacked behind - only show on hover */}
      {hasArchivedVersions && isHovered && (
        <div className="absolute inset-0 pointer-events-none">
          {frame.archivedVersions!.slice(0, 3).map((archivePath, index) => (
            <div
              key={archivePath}
              className="absolute rounded-lg border border-border/50 overflow-hidden bg-card/80 backdrop-blur-sm"
              style={{
                top: -8 - (index * 4),
                left: -8 - (index * 4),
                right: 8 + (index * 4),
                bottom: 8 + (index * 4),
                zIndex: -1 - index,
                opacity: 0.6 - (index * 0.15),
                transform: `rotate(${-2 - index}deg)`,
              }}
            >
              <div className="aspect-video bg-black/50">
                <img
                  src={`${API_BASE_URL}/api/images/${encodeURIComponent(archivePath)}`}
                  alt={`Archived version ${index + 1}`}
                  className="w-full h-full object-contain opacity-70"
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Archived indicator badge */}
      {hasArchivedVersions && (
        <div className="absolute -top-1 -left-1 z-20 px-1.5 py-0.5 bg-amber-500/90 text-white text-xs font-medium rounded-full shadow-sm">
          {frame.archivedVersions!.length} healed
        </div>
      )}

      <div
        className={cn(
          "bg-card rounded-lg border overflow-hidden cursor-pointer transition-all duration-200 relative",
          isHovered ? "border-primary ring-2 ring-primary/20 scale-[1.02] shadow-lg z-10" : "border-border",
          className
        )}
        onMouseEnter={onHover}
        onMouseLeave={onLeave}
        onClick={onClick}
      >
        <div className="aspect-video bg-black flex items-center justify-center relative overflow-hidden">
        {frame.imagePath ? (
          <img
            src={`${API_BASE_URL}/api/images/${encodeURIComponent(frame.imagePath)}`}
            alt={`Frame ${frame.id}`}
            className={cn(
              "w-full h-full object-contain transition-transform duration-200",
              isHovered && "scale-105"
            )}
          />
        ) : (
          <ImageIcon className="h-8 w-8 text-muted-foreground" />
        )}

        {/* Tag icons overlay - always visible in top-right */}
        {tags.length > 0 && (
          <div className="absolute top-1.5 right-1.5 flex flex-wrap gap-1 justify-end max-w-[70%]">
            {tags.slice(0, 5).map((tag) => {
              const { icon: TagIcon, color, bgColor } = getTagStyle(tag);
              return (
                <div
                  key={tag}
                  className={cn("p-1 rounded", bgColor)}
                  title={tag}
                >
                  <TagIcon className={cn("h-3 w-3", color)} />
                </div>
              );
            })}
            {tags.length > 5 && (
              <div className="px-1.5 py-0.5 bg-gray-500/30 rounded text-xs text-gray-300">
                +{tags.length - 5}
              </div>
            )}
          </div>
        )}

        {/* Hover overlay */}
        <div className={cn(
          "absolute inset-0 bg-gradient-to-t from-black/60 to-transparent transition-opacity",
          isHovered ? "opacity-100" : "opacity-0"
        )}>
          <div className="absolute bottom-2 left-2 right-2">
            <span className="px-2 py-1 bg-primary text-primary-foreground text-xs font-mono rounded">
              [{frame.id}]
            </span>
          </div>
        </div>
      </div>

      {/* Row mode: show frame info and tags */}
      {isRowMode && (
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs font-mono rounded">
              [{frame.scene}.{frame.frame}.{frame.camera || "cA"}]
            </span>
          </div>

          {/* Tag badges in row mode */}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => {
                const { icon: TagIcon, color, bgColor } = getTagStyle(tag);
                return (
                  <div
                    key={tag}
                    className={cn("flex items-center gap-1 px-1.5 py-0.5 rounded text-xs", bgColor, color)}
                    title={tag}
                  >
                    <TagIcon className="h-3 w-3" />
                    <span>{getTagDisplayName(tag)}</span>
                  </div>
                );
              })}
            </div>
          )}

          <p className="text-xs text-muted-foreground line-clamp-2">{frame.prompt}</p>
        </div>
      )}
      </div>
    </div>
  );
}

// Camera Card for Scene View - shows detailed camera info
function CameraCard({
  frame,
  isHovered,
  onHover,
  onLeave,
  onClick,
}: {
  frame: Frame;
  isHovered: boolean;
  onHover: () => void;
  onLeave: () => void;
  onClick: () => void;
}) {
  const tags = frame.tags || [];

  return (
    <div
      className={cn(
        "flex gap-4 p-3 bg-card rounded-lg border cursor-pointer transition-all duration-200",
        isHovered ? "border-primary ring-2 ring-primary/20 shadow-lg" : "border-border"
      )}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div className="w-40 aspect-video bg-black rounded overflow-hidden flex-shrink-0">
        {frame.imagePath ? (
          <img
            src={`${API_BASE_URL}/api/images/${encodeURIComponent(frame.imagePath)}`}
            alt={`Frame ${frame.id}`}
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon className="h-6 w-6 text-muted-foreground" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 bg-primary/20 text-primary text-xs font-mono rounded flex items-center gap-1">
            <Camera className="h-3 w-3" />
            [{frame.id}]
          </span>
          {frame.location_direction && (
            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">
              {frame.location_direction}
            </span>
          )}
        </div>

        {/* Notations */}
        <div className="space-y-1 text-xs">
          {frame.position_notation && (
            <div className="flex items-start gap-2">
              <Move className="h-3 w-3 text-muted-foreground mt-0.5 flex-shrink-0" />
              <span className="text-muted-foreground line-clamp-1">{frame.position_notation}</span>
            </div>
          )}
          {frame.lighting_notation && (
            <div className="flex items-start gap-2">
              <Lightbulb className="h-3 w-3 text-muted-foreground mt-0.5 flex-shrink-0" />
              <span className="text-muted-foreground line-clamp-1">{frame.lighting_notation}</span>
            </div>
          )}
          {frame.motion_prompt && (
            <div className="flex items-start gap-2">
              <RefreshCw className="h-3 w-3 text-purple-400 mt-0.5 flex-shrink-0" />
              <span className="text-purple-300 line-clamp-1">{frame.motion_prompt}</span>
            </div>
          )}
        </div>

        {/* Tags */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {tags.slice(0, 6).map((tag) => {
              const { icon: TagIcon, color, bgColor } = getTagStyle(tag);
              return (
                <div
                  key={tag}
                  className={cn("flex items-center gap-1 px-1.5 py-0.5 rounded text-xs", bgColor, color)}
                  title={tag}
                >
                  <TagIcon className="h-3 w-3" />
                  <span>{getTagDisplayName(tag)}</span>
                </div>
              );
            })}
            {tags.length > 6 && (
              <span className="text-xs text-muted-foreground">+{tags.length - 6}</span>
            )}
          </div>
        )}

        {/* Prompt preview */}
        <p className="text-xs text-muted-foreground line-clamp-2">{frame.prompt}</p>
      </div>

      {/* Action buttons on hover */}
      {isHovered && (
        <div className="flex flex-col gap-1 flex-shrink-0">
          <button
            className="p-1.5 bg-secondary hover:bg-secondary/80 rounded transition-colors"
            title="View Full"
            onClick={(e) => { e.stopPropagation(); onClick(); }}
          >
            <Eye className="h-3 w-3" />
          </button>
          <button
            className="p-1.5 bg-secondary hover:bg-secondary/80 rounded transition-colors"
            title="Edit Prompt"
            onClick={(e) => e.stopPropagation()}
          >
            <Edit3 className="h-3 w-3" />
          </button>
          <button
            className="p-1.5 bg-secondary hover:bg-secondary/80 rounded transition-colors"
            title="Regenerate"
            onClick={(e) => e.stopPropagation()}
          >
            <RotateCcw className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
