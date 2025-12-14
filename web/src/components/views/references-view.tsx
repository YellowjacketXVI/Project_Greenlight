"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn } from "@/lib/utils";
import { BookOpen, RefreshCw, Star } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";

interface ReferenceImage {
  path: string;
  name: string;
  isKey: boolean;
}

interface ReferenceTag {
  tag: string;
  name: string;
  images: ReferenceImage[];
}

export function ReferencesView() {
  const { currentProject } = useAppStore();
  const [references, setReferences] = useState<ReferenceTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  const loadReferences = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ references: ReferenceTag[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/references`
      );
      setReferences(data.references || []);
      if (data.references?.length > 0 && !selectedTag) {
        setSelectedTag(data.references[0].tag);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load references");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReferences();
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
          <button onClick={loadReferences} className="text-sm text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (references.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <BookOpen className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No References</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the References pipeline to generate reference images
            </p>
          </div>
        </div>
      </div>
    );
  }

  const selectedRef = references.find((r) => r.tag === selectedTag);

  return (
    <div className="h-full flex">
      {/* Tag List */}
      <div className="w-56 border-r border-border">
        <div className="p-3 border-b border-border">
          <h2 className="font-semibold text-sm">Tags</h2>
        </div>
        <ScrollArea.Root className="h-[calc(100%-49px)]">
          <ScrollArea.Viewport className="h-full p-2">
            {references.map((ref) => (
              <button
                key={ref.tag}
                onClick={() => setSelectedTag(ref.tag)}
                className={cn(
                  "w-full text-left px-3 py-2 rounded text-sm transition-colors",
                  selectedTag === ref.tag
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-secondary text-muted-foreground hover:text-foreground"
                )}
              >
                <div className="font-medium truncate">{ref.name}</div>
                <div className="text-xs opacity-70">{ref.tag}</div>
              </button>
            ))}
          </ScrollArea.Viewport>
        </ScrollArea.Root>
      </div>

      {/* Images */}
      <div className="flex-1">
        {selectedRef ? (
          <ScrollArea.Root className="h-full">
            <ScrollArea.Viewport className="h-full p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {selectedRef.images.map((image) => (
                  <div
                    key={image.path}
                    className={cn(
                      "bg-card rounded-lg border overflow-hidden",
                      image.isKey ? "border-primary ring-2 ring-primary/20" : "border-border"
                    )}
                  >
                    <div className="aspect-square bg-secondary relative">
                      <img
                        src={`/api/images/${encodeURIComponent(image.path)}`}
                        alt={image.name}
                        className="w-full h-full object-cover"
                      />
                      {image.isKey && (
                        <div className="absolute top-2 right-2 p-1 bg-primary rounded">
                          <Star className="h-3 w-3 text-primary-foreground fill-current" />
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-xs text-muted-foreground truncate">{image.name}</p>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea.Viewport>
          </ScrollArea.Root>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            Select a tag to view references
          </div>
        )}
      </div>
    </div>
  );
}

