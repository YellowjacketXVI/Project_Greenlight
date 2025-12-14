"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI } from "@/lib/utils";
import { FileText, RefreshCw } from "lucide-react";
import * as ScrollArea from "@radix-ui/react-scroll-area";

interface Scene {
  number: number;
  title: string;
  content: string;
  tags: string[];
}

export function ScriptView() {
  const { currentProject } = useAppStore();
  const [script, setScript] = useState<string>("");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScript = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ content: string; scenes: Scene[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/script`
      );
      setScript(data.content);
      setScenes(data.scenes || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load script");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScript();
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
          <button
            onClick={loadScript}
            className="text-sm text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!script && scenes.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Script Available</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Writer pipeline to generate a script
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <h1 className="text-2xl font-bold">Script</h1>
          
          {scenes.length > 0 ? (
            <div className="space-y-4">
              {scenes.map((scene) => (
                <div
                  key={scene.number}
                  className="p-4 bg-card rounded-lg border border-border"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded">
                      Scene {scene.number}
                    </span>
                    <h3 className="font-medium">{scene.title}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {scene.content}
                  </p>
                  {scene.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {scene.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-1.5 py-0.5 bg-secondary text-xs rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-card rounded-lg border border-border">
              <pre className="text-sm whitespace-pre-wrap font-mono">
                {script}
              </pre>
            </div>
          )}
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar
        className="flex select-none touch-none p-0.5 bg-secondary transition-colors w-2"
        orientation="vertical"
      >
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full relative" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

