"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn } from "@/lib/utils";
import { Globe, User, MapPin, Package, RefreshCw } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import * as ScrollArea from "@radix-ui/react-scroll-area";

interface WorldEntity {
  tag: string;
  name: string;
  description: string;
  imagePath?: string;
}

interface WorldData {
  characters: WorldEntity[];
  locations: WorldEntity[];
  props: WorldEntity[];
}

const tabs = [
  { id: "characters", label: "Characters", icon: User },
  { id: "locations", label: "Locations", icon: MapPin },
  { id: "props", label: "Props", icon: Package },
];

export function WorldView() {
  const { currentProject } = useAppStore();
  const [worldData, setWorldData] = useState<WorldData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("characters");

  const loadWorld = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<WorldData>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/world`
      );
      setWorldData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load world data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorld();
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
          <button onClick={loadWorld} className="text-sm text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!worldData) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <Globe className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No World Data</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Writer pipeline to generate world data
            </p>
          </div>
        </div>
      </div>
    );
  }

  const getEntities = () => {
    switch (activeTab) {
      case "characters": return worldData.characters || [];
      case "locations": return worldData.locations || [];
      case "props": return worldData.props || [];
      default: return [];
    }
  };

  return (
    <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
      <Tabs.List className="flex border-b border-border px-4">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <Tabs.Trigger
              key={tab.id}
              value={tab.id}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </Tabs.Trigger>
          );
        })}
      </Tabs.List>

      <ScrollArea.Root className="flex-1">
        <ScrollArea.Viewport className="h-full w-full p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {getEntities().map((entity) => (
              <div key={entity.tag} className="bg-card rounded-lg border border-border overflow-hidden">
                <div className="aspect-square bg-secondary flex items-center justify-center">
                  {entity.imagePath ? (
                    <img
                      src={`/api/images/${encodeURIComponent(entity.imagePath)}`}
                      alt={entity.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <User className="h-12 w-12 text-muted-foreground" />
                  )}
                </div>
                <div className="p-3 space-y-1">
                  <span className="px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded">
                    {entity.tag}
                  </span>
                  <h3 className="font-medium">{entity.name}</h3>
                  <p className="text-xs text-muted-foreground line-clamp-3">{entity.description}</p>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
          <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </Tabs.Root>
  );
}

