"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn, API_BASE_URL } from "@/lib/utils";
import { Images, RefreshCw, ZoomIn, ZoomOut, Search, Folder, X, Filter, Grid, LayoutGrid } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import * as Slider from "@radix-ui/react-slider";

interface GalleryImage {
  path: string;
  name: string;
  folder?: string;
}

type SortOption = "name" | "folder" | "date";

// Extract folder from path
function getFolder(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  if (parts.length >= 2) {
    return parts[parts.length - 2];
  }
  return "root";
}

// Get folder icon/color based on type
function getFolderStyle(folder: string): { color: string; icon: string } {
  const lower = folder.toLowerCase();
  if (lower.includes("storyboard")) return { color: "text-green-400", icon: "🎬" };
  if (lower.includes("reference")) return { color: "text-blue-400", icon: "📚" };
  if (lower.includes("char")) return { color: "text-purple-400", icon: "👤" };
  if (lower.includes("loc")) return { color: "text-orange-400", icon: "📍" };
  if (lower.includes("prop")) return { color: "text-yellow-400", icon: "🎭" };
  if (lower.includes("asset")) return { color: "text-cyan-400", icon: "📦" };
  return { color: "text-gray-400", icon: "📁" };
}

export function GalleryView() {
  const { currentProject } = useAppStore();
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(50); // 0-100 scale
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<GalleryImage | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  const loadImages = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ images: GalleryImage[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/gallery`
      );
      // Add folder info to each image
      const imagesWithFolders = (data.images || []).map((img) => ({
        ...img,
        folder: getFolder(img.path),
      }));
      setImages(imagesWithFolders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gallery");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadImages();
  }, [currentProject]);

  // Get unique folders
  const folders = useMemo(() => {
    const folderSet = new Set<string>();
    images.forEach((img) => {
      if (img.folder) folderSet.add(img.folder);
    });
    return Array.from(folderSet).sort();
  }, [images]);

  // Filter images
  const filteredImages = useMemo(() => {
    return images.filter((img) => {
      const matchesSearch = !searchQuery ||
        img.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        img.path.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesFolder = !selectedFolder || img.folder === selectedFolder;
      return matchesSearch && matchesFolder;
    });
  }, [images, searchQuery, selectedFolder]);

  // Group by folder for display
  const imagesByFolder = useMemo(() => {
    const groups: Record<string, GalleryImage[]> = {};
    filteredImages.forEach((img) => {
      const folder = img.folder || "root";
      if (!groups[folder]) groups[folder] = [];
      groups[folder].push(img);
    });
    return groups;
  }, [filteredImages]);

  // Calculate grid columns based on zoom
  const gridColumns = useMemo(() => {
    if (zoom < 25) return 8;
    if (zoom < 50) return 6;
    if (zoom < 75) return 4;
    return 3;
  }, [zoom]);

  // Navigate in lightbox
  const navigateImage = useCallback((direction: 1 | -1) => {
    if (!selectedImage) return;
    const idx = filteredImages.findIndex(img => img.path === selectedImage.path);
    const newIdx = Math.max(0, Math.min(filteredImages.length - 1, idx + direction));
    setSelectedImage(filteredImages[newIdx]);
    setCurrentIndex(newIdx);
  }, [selectedImage, filteredImages]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedImage) return;
      if (e.key === "ArrowLeft") navigateImage(-1);
      if (e.key === "ArrowRight") navigateImage(1);
      if (e.key === "Escape") setSelectedImage(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedImage, navigateImage]);

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
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-border bg-card/50 gap-4">
        <div className="flex items-center gap-3">
          <h2 className="font-semibold flex items-center gap-2">
            <Images className="h-5 w-5" />
            Gallery
          </h2>
          <span className="text-sm text-muted-foreground">
            {filteredImages.length} of {images.length} images
          </span>
        </div>

        {/* Search */}
        <div className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search images..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-1.5 bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-secondary-foreground/10 rounded"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Zoom Slider */}
        <div className="flex items-center gap-2 w-40">
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
            <Slider.Thumb className="block w-4 h-4 bg-primary rounded-full hover:bg-primary/90 focus:outline-none" />
          </Slider.Root>
          <ZoomIn className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Folder Sidebar */}
        <div className="w-48 border-r border-border bg-card/30 flex-shrink-0">
          <div className="p-3 border-b border-border">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Folders
            </h3>
          </div>
          <ScrollArea.Root className="h-[calc(100%-49px)]">
            <ScrollArea.Viewport className="h-full p-2">
              <button
                onClick={() => setSelectedFolder(null)}
                className={cn(
                  "w-full text-left px-3 py-2 rounded text-sm transition-colors flex items-center gap-2",
                  !selectedFolder
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                <LayoutGrid className="h-4 w-4" />
                All Images
                <span className="ml-auto text-xs opacity-70">{images.length}</span>
              </button>
              {folders.map((folder) => {
                const style = getFolderStyle(folder);
                const count = images.filter(img => img.folder === folder).length;
                return (
                  <button
                    key={folder}
                    onClick={() => setSelectedFolder(folder)}
                    className={cn(
                      "w-full text-left px-3 py-2 rounded text-sm transition-colors flex items-center gap-2",
                      selectedFolder === folder
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-secondary text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <span>{style.icon}</span>
                    <span className="truncate flex-1">{folder}</span>
                    <span className="text-xs opacity-70">{count}</span>
                  </button>
                );
              })}
            </ScrollArea.Viewport>
          </ScrollArea.Root>
        </div>

        {/* Image Grid */}
        <ScrollArea.Root className="flex-1">
          <ScrollArea.Viewport className="h-full w-full p-4">
            {selectedFolder ? (
              // Single folder view
              <div
                className="grid gap-3"
                style={{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }}
              >
                {filteredImages.map((image, idx) => (
                  <ImageCard
                    key={image.path}
                    image={image}
                    onClick={() => {
                      setSelectedImage(image);
                      setCurrentIndex(idx);
                    }}
                  />
                ))}
              </div>
            ) : (
              // Grouped by folder view
              <div className="space-y-6">
                {Object.entries(imagesByFolder).map(([folder, folderImages]) => {
                  const style = getFolderStyle(folder);
                  return (
                    <div key={folder}>
                      <div className="flex items-center gap-2 mb-3 px-1">
                        <span className={cn("text-lg", style.color)}>{style.icon}</span>
                        <h3 className="font-medium">{folder}</h3>
                        <span className="text-sm text-muted-foreground">({folderImages.length})</span>
                        <button
                          onClick={() => setSelectedFolder(folder)}
                          className="ml-auto text-xs text-primary hover:underline"
                        >
                          View all →
                        </button>
                      </div>
                      <div
                        className="grid gap-3"
                        style={{ gridTemplateColumns: `repeat(${gridColumns}, 1fr)` }}
                      >
                        {folderImages.slice(0, gridColumns * 2).map((image) => (
                          <ImageCard
                            key={image.path}
                            image={image}
                            onClick={() => {
                              setSelectedImage(image);
                              setCurrentIndex(filteredImages.indexOf(image));
                            }}
                          />
                        ))}
                        {folderImages.length > gridColumns * 2 && (
                          <button
                            onClick={() => setSelectedFolder(folder)}
                            className="aspect-video bg-secondary/50 rounded-lg border border-dashed border-border flex items-center justify-center hover:bg-secondary transition-colors"
                          >
                            <span className="text-sm text-muted-foreground">
                              +{folderImages.length - gridColumns * 2} more
                            </span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea.Viewport>
          <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
            <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
          </ScrollArea.Scrollbar>
        </ScrollArea.Root>
      </div>

      {/* Lightbox Modal */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center" onClick={() => setSelectedImage(null)}>
          <button
            className="absolute top-4 right-4 p-2 text-white hover:bg-white/10 rounded-full"
            onClick={() => setSelectedImage(null)}
          >
            <X className="h-6 w-6" />
          </button>

          <button
            className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full text-2xl disabled:opacity-30"
            onClick={(e) => { e.stopPropagation(); navigateImage(-1); }}
            disabled={currentIndex === 0}
          >
            ←
          </button>

          <div className="max-w-5xl max-h-[85vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <img
              src={`${API_BASE_URL}/api/images/${encodeURIComponent(selectedImage.path)}`}
              alt={selectedImage.name}
              className="max-h-[75vh] object-contain rounded-lg"
            />
            <div className="mt-4 text-center text-white">
              <p className="font-medium">{selectedImage.name}</p>
              <p className="text-sm text-white/60 mt-1">{selectedImage.folder}</p>
              <p className="text-xs text-white/40 mt-2">{currentIndex + 1} / {filteredImages.length}</p>
            </div>
          </div>

          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-white hover:bg-white/10 rounded-full text-2xl disabled:opacity-30"
            onClick={(e) => { e.stopPropagation(); navigateImage(1); }}
            disabled={currentIndex === filteredImages.length - 1}
          >
            →
          </button>
        </div>
      )}
    </div>
  );
}

function ImageCard({ image, onClick }: { image: GalleryImage; onClick: () => void }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={cn(
        "bg-card rounded-lg border overflow-hidden cursor-pointer transition-all duration-200",
        isHovered ? "border-primary ring-2 ring-primary/20 scale-[1.02] shadow-lg" : "border-border"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
    >
      <div className="aspect-video bg-secondary relative overflow-hidden">
        <img
          src={`${API_BASE_URL}/api/images/${encodeURIComponent(image.path)}`}
          alt={image.name}
          className={cn(
            "w-full h-full object-contain transition-transform duration-200",
            isHovered && "scale-105"
          )}
        />
        {/* Hover overlay */}
        <div className={cn(
          "absolute inset-0 bg-gradient-to-t from-black/60 to-transparent transition-opacity flex items-end p-2",
          isHovered ? "opacity-100" : "opacity-0"
        )}>
          <span className="text-white text-xs truncate">{image.name}</span>
        </div>
      </div>
    </div>
  );
}

