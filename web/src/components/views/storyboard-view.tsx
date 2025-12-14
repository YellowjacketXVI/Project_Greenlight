"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn, API_BASE_URL } from "@/lib/utils";
import { Image as ImageIcon, RefreshCw, ZoomIn, ZoomOut, Grid, LayoutList, Camera, X, User, MapPin, Package, Sparkles, Calendar, Cloud } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import * as Slider from "@radix-ui/react-slider";

interface Frame {
  id: string;
  scene: number;
  frame: number;
  camera: string;
  prompt: string;
  imagePath?: string;
  tags?: string[];  // Extracted tags from prompt (CHAR_, LOC_, PROP_, etc.)
}

type ViewMode = "grid" | "timeline";

// Calculate grid columns based on zoom level (similar to desktop UI)
function getGridColumns(zoom: number): number {
  // Zoom 0-49: Grid mode (10 cols at 0% → 3 cols at 49%)
  // Zoom 50-100: Row mode (fewer columns, larger images)
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(25); // 0-100 scale
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [hoveredFrame, setHoveredFrame] = useState<string | null>(null);
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  const loadFrames = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ frames: Frame[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/storyboard`
      );
      setFrames(data.frames || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load storyboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFrames();
  }, [currentProject]);

  // Group frames by scene
  const framesByScene = useMemo(() => {
    const groups: Record<number, Frame[]> = {};
    frames.forEach((frame) => {
      if (!groups[frame.scene]) groups[frame.scene] = [];
      groups[frame.scene].push(frame);
    });
    return groups;
  }, [frames]);

  const gridColumns = getGridColumns(zoom);
  const isRowMode = zoom >= 50;

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
              onClick={() => setViewMode("timeline")}
              className={cn(
                "p-1.5 rounded transition-colors",
                viewMode === "timeline" ? "bg-primary text-primary-foreground" : "hover:bg-secondary-foreground/10"
              )}
              title="Timeline View"
            >
              <LayoutList className="h-4 w-4" />
            </button>
          </div>

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
        </div>
      </div>

      {/* Frames Display */}
      <ScrollArea.Root className="flex-1">
        <ScrollArea.Viewport className="h-full w-full p-4">
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
            <div className="space-y-6">
              {Object.entries(framesByScene).map(([sceneNum, sceneFrames]) => (
                <div key={sceneNum} className="space-y-3">
                  <div className="flex items-center gap-2 px-2">
                    <span className="px-2 py-1 bg-primary/10 text-primary text-sm font-medium rounded">
                      Scene {sceneNum}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {sceneFrames.length} frames
                    </span>
                  </div>
                  <div className="flex gap-3 overflow-x-auto pb-2">
                    {sceneFrames.map((frame) => (
                      <FrameCard
                        key={frame.id}
                        frame={frame}
                        isHovered={hoveredFrame === frame.id}
                        isRowMode={true}
                        onHover={() => setHoveredFrame(frame.id)}
                        onLeave={() => setHoveredFrame(null)}
                        onClick={() => {
                          setSelectedFrame(frame);
                          setCurrentIndex(frames.indexOf(frame));
                        }}
                        className="flex-shrink-0 w-72"
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
          <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>

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

      {/* Lightbox Modal */}
      {selectedFrame && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center" onClick={() => setSelectedFrame(null)}>
          <button
            className="absolute top-4 right-4 p-2 text-white hover:bg-white/10 rounded-full"
            onClick={() => setSelectedFrame(null)}
          >
            <X className="h-6 w-6" />
          </button>

          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full disabled:opacity-30"
            onClick={(e) => { e.stopPropagation(); navigateFrame(-1); }}
            disabled={currentIndex === 0}
          >
            ←
          </button>

          <div className="max-w-5xl max-h-[80vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            {selectedFrame.imagePath ? (
              <img
                src={`${API_BASE_URL}/api/images/${encodeURIComponent(selectedFrame.imagePath)}`}
                alt={selectedFrame.id}
                className="max-h-[70vh] object-contain rounded-lg"
              />
            ) : (
              <div className="w-96 h-64 bg-secondary rounded-lg flex items-center justify-center">
                <ImageIcon className="h-12 w-12 text-muted-foreground" />
              </div>
            )}
            <div className="mt-4 text-center text-white">
              <div className="flex items-center justify-center gap-3 mb-2">
                <span className="px-2 py-1 bg-primary rounded text-sm font-mono">[{selectedFrame.id}]</span>
                <span className="flex items-center gap-1 text-sm">
                  <Camera className="h-4 w-4" />
                  {selectedFrame.camera || "cA"}
                </span>
              </div>
              <p className="text-sm text-white/70 max-w-2xl">{selectedFrame.prompt}</p>
              <p className="text-xs text-white/50 mt-2">{currentIndex + 1} / {frames.length}</p>
            </div>
          </div>

          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full disabled:opacity-30"
            onClick={(e) => { e.stopPropagation(); navigateFrame(1); }}
            disabled={currentIndex === frames.length - 1}
          >
            →
          </button>
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

  return (
    <div
      className={cn(
        "bg-card rounded-lg border overflow-hidden cursor-pointer transition-all duration-200",
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
  );
}

