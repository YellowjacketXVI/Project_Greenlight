"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI } from "@/lib/utils";
import { Images, RefreshCw, ZoomIn, ZoomOut } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";

interface GalleryImage {
  path: string;
  name: string;
  scene?: number;
  frame?: number;
}

export function GalleryView() {
  const { currentProject } = useAppStore();
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  const loadImages = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ images: GalleryImage[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/gallery`
      );
      setImages(data.images || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gallery");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadImages();
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
          <button onClick={loadImages} className="text-sm text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <Images className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Images</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Generated images will appear here
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-3 border-b border-border">
        <h2 className="font-semibold">Gallery ({images.length} images)</h2>
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

      <ScrollArea.Root className="flex-1">
        <ScrollArea.Viewport className="h-full w-full p-4">
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: `repeat(auto-fill, minmax(${200 * zoom}px, 1fr))`,
            }}
          >
            {images.map((image) => (
              <div
                key={image.path}
                className="bg-card rounded-lg border border-border overflow-hidden group cursor-pointer"
              >
                <div className="aspect-video bg-secondary">
                  <img
                    src={`/api/images/${encodeURIComponent(image.path)}`}
                    alt={image.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-2">
                  <p className="text-xs text-muted-foreground truncate">{image.name}</p>
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

