"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI } from "@/lib/utils";
import { Image as ImageIcon, RefreshCw, ZoomIn, ZoomOut } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";

interface Frame {
  id: string;
  scene: number;
  frame: number;
  camera: string;
  prompt: string;
  imagePath?: string;
}

export function StoryboardView() {
  const { currentProject } = useAppStore();
  const [frames, setFrames] = useState<Frame[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

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
          <p className="text-error">{error}</p>
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
      <div className="flex items-center justify-between p-3 border-b border-border">
        <h2 className="font-semibold">Storyboard</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
            className="p-1.5 hover:bg-secondary rounded"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="text-sm text-muted-foreground w-12 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom(Math.min(2, zoom + 0.25))}
            className="p-1.5 hover:bg-secondary rounded"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Frames Grid */}
      <ScrollArea.Root className="flex-1">
        <ScrollArea.Viewport className="h-full w-full p-4">
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(auto-fill, minmax(${280 * zoom}px, 1fr))`,
            }}
          >
            {frames.map((frame) => (
              <div
                key={frame.id}
                className="bg-card rounded-lg border border-border overflow-hidden"
              >
                <div className="aspect-video bg-secondary flex items-center justify-center">
                  {frame.imagePath ? (
                    <img
                      src={`/api/images/${encodeURIComponent(frame.imagePath)}`}
                      alt={`Frame ${frame.id}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <ImageIcon className="h-8 w-8 text-muted-foreground" />
                  )}
                </div>
                <div className="p-3 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded">
                      {frame.id}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Camera {frame.camera}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {frame.prompt}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar
          className="flex select-none touch-none p-0.5 bg-secondary w-2"
          orientation="vertical"
        >
          <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </div>
  );
}

