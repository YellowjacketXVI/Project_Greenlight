"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn } from "@/lib/utils";
import { Film, Image as ImageIcon, RefreshCw, Camera, MapPin, Lightbulb, Sparkles, Save, Edit3, ChevronDown, ChevronUp } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import { MentionInput } from "@/components/mention-input";

interface VisualFrame {
  id: string;
  scene: number;
  frame: number;
  camera: string;
  position: string;
  lighting: string;
  prompt: string;
  tags: string[];
}

interface Prompt {
  id: string;
  prompt: string;
  full_prompt?: string;
  original_prompt?: string;
  model?: string;
  tags?: string[];
  reference_images?: string[];
  has_prior_frame?: boolean;
  status?: string;
  timestamp?: string;
  output_path?: string;
  scene?: string;
  camera_notation?: string;
  position_notation?: string;
  lighting_notation?: string;
  location_direction?: string;
  edited?: boolean;
}

const tabs = [
  { id: "pitch", label: "Pitch", icon: Sparkles },
  { id: "visual", label: "Visual Script", icon: Film },
  { id: "prompts", label: "Visual Prompts", icon: ImageIcon },
];

// Tag color mapping based on prefix
function getTagStyle(tag: string): { color: string; icon: string } {
  if (tag.startsWith("CHAR_")) return { color: "text-blue-400", icon: "👤" };
  if (tag.startsWith("LOC_")) return { color: "text-green-400", icon: "📍" };
  if (tag.startsWith("PROP_")) return { color: "text-orange-400", icon: "🎭" };
  if (tag.startsWith("CONCEPT_")) return { color: "text-purple-400", icon: "💡" };
  if (tag.startsWith("EVENT_")) return { color: "text-red-400", icon: "📅" };
  if (tag.startsWith("ENV_")) return { color: "text-gray-400", icon: "🌤️" };
  return { color: "text-muted-foreground", icon: "🏷️" };
}

export function ScriptView() {
  const { currentProject } = useAppStore();
  const [activeTab, setActiveTab] = useState("pitch");
  const [pitch, setPitch] = useState<string>("");
  const [visualFrames, setVisualFrames] = useState<VisualFrame[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [promptsSource, setPromptsSource] = useState<string>("none");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!currentProject) return;
    setLoading(true);
    setError(null);
    try {
      // Load pitch
      try {
        const pitchData = await fetchAPI<{ content: string; exists: boolean }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/pitch`
        );
        setPitch(pitchData.content || "");
      } catch {
        setPitch("");
      }

      // Load visual script
      try {
        const visualData = await fetchAPI<{ frames: VisualFrame[] }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/visual-script`
        );
        setVisualFrames(visualData.frames || []);
      } catch {
        setVisualFrames([]);
      }

      // Load prompts
      try {
        const promptsData = await fetchAPI<{ prompts: Prompt[]; source: string }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/prompts`
        );
        setPrompts(promptsData.prompts || []);
        setPromptsSource(promptsData.source || "none");
      } catch {
        setPrompts([]);
        setPromptsSource("none");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
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
          <p className="text-destructive">{error}</p>
          <button onClick={loadData} className="text-sm text-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
      <Tabs.List className="flex border-b border-border px-4 bg-card/50">
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

      {/* Pitch Tab */}
      <Tabs.Content value="pitch" className="flex-1 overflow-hidden">
        <PitchTab pitch={pitch} setPitch={setPitch} projectPath={currentProject?.path || ""} />
      </Tabs.Content>

      {/* Visual Script Tab */}
      <Tabs.Content value="visual" className="flex-1 overflow-hidden">
        <VisualScriptTab frames={visualFrames} />
      </Tabs.Content>

      {/* Prompts Tab */}
      <Tabs.Content value="prompts" className="flex-1 overflow-hidden">
        <PromptsTab prompts={prompts} source={promptsSource} />
      </Tabs.Content>
    </Tabs.Root>
  );
}

interface PitchTabProps {
  pitch: string;
  setPitch: (pitch: string) => void;
  projectPath: string;
}

interface WorldEntity {
  tag: string;
  name: string;
  description: string;
}

function PitchTab({ pitch, setPitch, projectPath }: PitchTabProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(pitch);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [entities, setEntities] = useState<{ tag: string; name: string; type: "character" | "location" | "prop" }[]>([]);

  // Load entities from world API
  useEffect(() => {
    if (!projectPath) return;
    const loadEntities = async () => {
      try {
        const data = await fetchAPI<{
          characters: WorldEntity[];
          locations: WorldEntity[];
          props: WorldEntity[];
        }>(`/api/projects/${encodeURIComponent(projectPath)}/world`);

        const allEntities = [
          ...data.characters.map(e => ({ tag: e.tag, name: e.name, type: "character" as const })),
          ...data.locations.map(e => ({ tag: e.tag, name: e.name, type: "location" as const })),
          ...data.props.map(e => ({ tag: e.tag, name: e.name, type: "prop" as const })),
        ];
        setEntities(allEntities);
      } catch {
        // Entities not available yet
      }
    };
    loadEntities();
  }, [projectPath]);

  // Convert storage format to display format for editing
  const storageToDisplay = (text: string) => {
    let result = text;
    for (const entity of entities) {
      const regex = new RegExp(`\\[${entity.tag}\\]`, 'g');
      result = result.replace(regex, `@${entity.name}`);
    }
    return result;
  };

  // Convert display format to storage format for saving
  const displayToStorage = (text: string) => {
    let result = text;
    for (const entity of entities) {
      const regex = new RegExp(`@${entity.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      result = result.replace(regex, `[${entity.tag}]`);
    }
    return result;
  };

  // Sync editContent when pitch changes (convert to display format)
  useEffect(() => {
    setEditContent(storageToDisplay(pitch));
  }, [pitch, entities]);

  const handleSave = async () => {
    if (!projectPath) return;
    setSaving(true);
    setSaveError(null);
    try {
      // Convert display format (@Name) to storage format ([TAG]) before saving
      const storageContent = displayToStorage(editContent);
      await fetchAPI(`/api/projects/${encodeURIComponent(projectPath)}/pitch`, {
        method: 'POST',
        body: JSON.stringify({ content: storageContent })
      });
      setPitch(storageContent);
      setIsEditing(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save pitch');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditContent(storageToDisplay(pitch));
    setIsEditing(false);
    setSaveError(null);
  };

  if (!pitch && !isEditing) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Sparkles className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Pitch Available</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Create a pitch to get started with your project
            </p>
          </div>
          <button
            onClick={() => setIsEditing(true)}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
          >
            Create Pitch
          </button>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              Pitch
            </h1>
            <div className="flex items-center gap-2">
              {isEditing ? (
                <>
                  <button
                    onClick={handleCancel}
                    className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {saving ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-secondary hover:bg-secondary/80 rounded transition-colors"
                >
                  <Edit3 className="h-4 w-4" />
                  Edit
                </button>
              )}
            </div>
          </div>

          {saveError && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded text-destructive text-sm">
              {saveError}
            </div>
          )}

          {isEditing ? (
            <div className="space-y-2">
              <div className="text-xs text-muted-foreground">
                💡 Type <span className="text-primary">@</span> to mention characters, locations, or props
              </div>
              <MentionInput
                value={editContent}
                onChange={setEditContent}
                entities={entities}
                placeholder="# Project Title&#10;&#10;## Logline&#10;A brief one-sentence summary...&#10;&#10;## Synopsis&#10;The full story synopsis...&#10;&#10;Use @CharacterName to tag characters"
                className="h-[calc(100vh-320px)] min-h-[400px]"
              />
            </div>
          ) : (
            <div className="p-6 bg-card rounded-lg border border-border">
              <div className="prose prose-invert max-w-none">
                <PitchContent content={pitch} />
              </div>
            </div>
          )}
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

// Simple markdown-like renderer for pitch content
function PitchContent({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];

  lines.forEach((line, idx) => {
    if (line.startsWith('# ')) {
      elements.push(<h1 key={idx} className="text-2xl font-bold mb-4">{line.slice(2)}</h1>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={idx} className="text-xl font-semibold mt-6 mb-3 text-primary">{line.slice(3)}</h2>);
    } else if (line.startsWith('### ')) {
      elements.push(<h3 key={idx} className="text-lg font-medium mt-4 mb-2">{line.slice(4)}</h3>);
    } else if (line.trim() === '') {
      elements.push(<br key={idx} />);
    } else {
      // Highlight tags in the content
      const tagRegex = /\[([A-Z]+_[A-Z0-9_]+)\]/g;
      const parts = line.split(tagRegex);
      const rendered = parts.map((part, partIdx) => {
        if (part.match(/^[A-Z]+_[A-Z0-9_]+$/)) {
          const style = getTagStyle(part);
          return (
            <span key={partIdx} className={cn("px-1.5 py-0.5 bg-secondary text-xs rounded mx-0.5", style.color)}>
              {style.icon} [{part}]
            </span>
          );
        }
        return part;
      });
      elements.push(<p key={idx} className="text-muted-foreground leading-relaxed mb-2">{rendered}</p>);
    }
  });

  return <>{elements}</>;
}

function VisualScriptTab({ frames }: { frames: VisualFrame[] }) {
  const [expandedScenes, setExpandedScenes] = useState<Set<number>>(new Set());
  const [expandedFrames, setExpandedFrames] = useState<Set<string>>(new Set());

  if (frames.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Film className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Visual Script</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Director pipeline to generate a visual script
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Group frames by scene, then by frame number
  const framesByScene: Record<number, Record<number, VisualFrame[]>> = {};
  frames.forEach((frame) => {
    if (!framesByScene[frame.scene]) framesByScene[frame.scene] = {};
    if (!framesByScene[frame.scene][frame.frame]) framesByScene[frame.scene][frame.frame] = [];
    framesByScene[frame.scene][frame.frame].push(frame);
  });

  const toggleScene = (sceneNum: number) => {
    setExpandedScenes(prev => {
      const next = new Set(prev);
      if (next.has(sceneNum)) {
        next.delete(sceneNum);
      } else {
        next.add(sceneNum);
      }
      return next;
    });
  };

  const toggleFrame = (frameKey: string) => {
    setExpandedFrames(prev => {
      const next = new Set(prev);
      if (next.has(frameKey)) {
        next.delete(frameKey);
      } else {
        next.add(frameKey);
      }
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
    setExpandedFrames(allFrameKeys);
  };

  const collapseAll = () => {
    setExpandedScenes(new Set());
    setExpandedFrames(new Set());
  };

  // Count total frames and cameras
  const totalScenes = Object.keys(framesByScene).length;
  const totalFrameGroups = Object.values(framesByScene).reduce(
    (acc, scene) => acc + Object.keys(scene).length, 0
  );

  // Collect all unique tags across all frames in a scene
  const getSceneTags = (sceneFrameGroups: Record<number, VisualFrame[]>): string[] => {
    const tagSet = new Set<string>();
    Object.values(sceneFrameGroups).forEach(cameras => {
      cameras.forEach(cam => {
        cam.tags?.forEach(tag => tagSet.add(tag));
      });
    });
    return Array.from(tagSet);
  };

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Film className="h-5 w-5" />
              Visual Script
            </h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                {totalScenes} scenes • {totalFrameGroups} frames • {frames.length} cameras
              </span>
              <button
                onClick={expandedScenes.size > 0 ? collapseAll : expandAll}
                className="text-xs text-primary hover:underline"
              >
                {expandedScenes.size > 0 ? "Collapse All" : "Expand All"}
              </button>
            </div>
          </div>

          {/* Scene Dropdowns */}
          {Object.entries(framesByScene).map(([sceneNumStr, frameGroups]) => {
            const sceneNum = Number(sceneNumStr);
            const isSceneExpanded = expandedScenes.has(sceneNum);
            const sceneTags = getSceneTags(frameGroups);
            const frameCount = Object.keys(frameGroups).length;
            const cameraCount = Object.values(frameGroups).reduce((acc, cams) => acc + cams.length, 0);

            return (
              <div key={sceneNum} className="bg-card rounded-lg border border-border overflow-hidden">
                {/* Scene Header - Clickable */}
                <div
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary/30 transition-colors"
                  onClick={() => toggleScene(sceneNum)}
                >
                  <div className="flex items-center gap-3">
                    <span className="px-2 py-1 bg-blue-500/10 text-blue-400 text-sm font-medium rounded">
                      Scene {sceneNum}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {frameCount} frame{frameCount !== 1 ? "s" : ""} • {cameraCount} camera{cameraCount !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Scene tags preview (collapsed) */}
                    {!isSceneExpanded && sceneTags.length > 0 && (
                      <div className="flex gap-1">
                        {sceneTags.slice(0, 4).map(tag => {
                          const style = getTagStyle(tag);
                          return (
                            <span key={tag} className={cn("px-1.5 py-0.5 text-xs rounded", style.color)}>
                              {style.icon}
                            </span>
                          );
                        })}
                        {sceneTags.length > 4 && (
                          <span className="text-xs text-muted-foreground">+{sceneTags.length - 4}</span>
                        )}
                      </div>
                    )}
                    {isSceneExpanded ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </div>

                {/* Scene Content - Frames */}
                {isSceneExpanded && (
                  <div className="border-t border-border p-4 space-y-3">
                    {Object.entries(frameGroups).map(([frameNumStr, cameras]) => {
                      const frameNum = Number(frameNumStr);
                      const frameKey = `${sceneNum}.${frameNum}`;
                      const isFrameExpanded = expandedFrames.has(frameKey);

                      return (
                        <div key={frameKey} className="bg-secondary/30 rounded-lg overflow-hidden">
                          {/* Frame Header - Clickable */}
                          <div
                            className="flex items-center justify-between p-3 cursor-pointer hover:bg-secondary/50 transition-colors"
                            onClick={() => toggleFrame(frameKey)}
                          >
                            <div className="flex items-center gap-3">
                              <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-mono font-medium rounded">
                                {sceneNum}.{frameNum}
                              </span>
                              <span className="text-sm text-muted-foreground">
                                {cameras.length} camera{cameras.length !== 1 ? "s" : ""}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              {/* Camera labels preview */}
                              {!isFrameExpanded && (
                                <div className="flex gap-1">
                                  {cameras.map(cam => (
                                    <span
                                      key={cam.id}
                                      className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 text-xs font-mono rounded"
                                    >
                                      {cam.camera || "cA"}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {isFrameExpanded ? (
                                <ChevronUp className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              )}
                            </div>
                          </div>

                          {/* Frame Content - Cameras */}
                          {isFrameExpanded && (
                            <div className="border-t border-border/50 p-3 space-y-3">
                              {cameras.map((cam) => (
                                <div key={cam.id} className="p-3 bg-card rounded-lg border border-border">
                                  {/* Camera Header */}
                                  <div className="flex items-center gap-3 mb-3">
                                    <span className="px-2 py-1 bg-purple-500/10 text-purple-400 text-xs font-mono font-medium rounded flex items-center gap-1">
                                      <Camera className="h-3 w-3" />
                                      [{sceneNum}.{frameNum}.{cam.camera || "cA"}]
                                    </span>
                                  </div>

                                  {/* Technical notations */}
                                  <div className="flex flex-wrap gap-2 mb-3">
                                    {cam.position && (
                                      <span className="px-2 py-1 bg-secondary text-xs rounded flex items-center gap-1">
                                        <MapPin className="h-3 w-3" />
                                        {cam.position.slice(0, 60)}{cam.position.length > 60 ? "..." : ""}
                                      </span>
                                    )}
                                    {cam.lighting && (
                                      <span className="px-2 py-1 bg-secondary text-xs rounded flex items-center gap-1">
                                        <Lightbulb className="h-3 w-3" />
                                        {cam.lighting.slice(0, 50)}{cam.lighting.length > 50 ? "..." : ""}
                                      </span>
                                    )}
                                  </div>

                                  {/* Tags */}
                                  {cam.tags && cam.tags.length > 0 && (
                                    <div className="flex flex-wrap gap-1.5 mb-3">
                                      {cam.tags.map((tag) => {
                                        const style = getTagStyle(tag);
                                        return (
                                          <span key={tag} className={cn("px-1.5 py-0.5 bg-secondary/50 text-xs rounded", style.color)}>
                                            {style.icon} [{tag}]
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}

                                  {/* Prompt */}
                                  <p className="text-sm text-muted-foreground leading-relaxed">
                                    {cam.prompt.slice(0, 500)}{cam.prompt.length > 500 ? "..." : ""}
                                  </p>
                                </div>
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
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

function PromptsTab({ prompts: initialPrompts, source }: { prompts: Prompt[]; source?: string }) {
  const { currentProject } = useAppStore();
  const [prompts, setPrompts] = useState<Prompt[]>(initialPrompts);
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
  const [editingPrompt, setEditingPrompt] = useState<string | null>(null);
  const [editedText, setEditedText] = useState<string>("");
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [savingAll, setSavingAll] = useState(false);
  const [allExpanded, setAllExpanded] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Update prompts when initialPrompts changes
  useEffect(() => {
    setPrompts(initialPrompts);
  }, [initialPrompts]);

  const toggleExpand = (id: string) => {
    setExpandedPrompts(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedPrompts(new Set(prompts.map(p => p.id)));
    setAllExpanded(true);
  };

  const collapseAll = () => {
    setExpandedPrompts(new Set());
    setAllExpanded(false);
  };

  const startEditing = (prompt: Prompt) => {
    setEditingPrompt(prompt.id);
    setEditedText(prompt.original_prompt || prompt.prompt);
  };

  const cancelEditing = () => {
    setEditingPrompt(null);
    setEditedText("");
  };

  // Save a single prompt without regenerating
  const savePrompt = async (promptId: string) => {
    if (!currentProject?.path) return;

    setSaving(promptId);
    try {
      const response = await fetchAPI<{ success: boolean; message: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/prompts/${encodeURIComponent(promptId)}/save`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            frame_id: promptId,
            prompt: editedText,
          }),
        }
      );

      if (response.success) {
        // Update local state
        setPrompts(prev => prev.map(p =>
          p.id === promptId
            ? { ...p, original_prompt: editedText, prompt: editedText, edited: true }
            : p
        ));
        setEditingPrompt(null);
        setEditedText("");
        setHasUnsavedChanges(false);
      } else {
        console.error("Save failed:", response.message);
      }
    } catch (error) {
      console.error("Error saving prompt:", error);
    } finally {
      setSaving(null);
    }
  };

  // Save all edited prompts
  const saveAllPrompts = async () => {
    if (!currentProject?.path) return;

    const editedPrompts = prompts.filter(p => p.edited);
    if (editedPrompts.length === 0) return;

    setSavingAll(true);
    try {
      const response = await fetchAPI<{ success: boolean; message: string; saved_count: number }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/prompts/save`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompts: editedPrompts.map(p => ({ frame_id: p.id, prompt: p.prompt })),
          }),
        }
      );

      if (response.success) {
        setHasUnsavedChanges(false);
      } else {
        console.error("Save all failed:", response.message);
      }
    } catch (error) {
      console.error("Error saving all prompts:", error);
    } finally {
      setSavingAll(false);
    }
  };

  const regeneratePrompt = async (promptId: string) => {
    if (!currentProject?.path) return;

    setRegenerating(promptId);
    try {
      const response = await fetchAPI<{ success: boolean; message: string; output_path?: string }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/prompts/regenerate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            frame_id: promptId,
            prompt: editedText,
          }),
        }
      );

      if (response.success) {
        // Update local state
        setPrompts(prev => prev.map(p =>
          p.id === promptId
            ? { ...p, original_prompt: editedText, prompt: editedText, status: "success", edited: true }
            : p
        ));
        setEditingPrompt(null);
        setEditedText("");
      } else {
        console.error("Regeneration failed:", response.message);
      }
    } catch (error) {
      console.error("Error regenerating prompt:", error);
    } finally {
      setRegenerating(null);
    }
  };

  // Group prompts by scene
  const promptsByScene: Record<string, Prompt[]> = {};
  prompts.forEach(prompt => {
    const scene = prompt.scene || prompt.id.split(".")[0] || "1";
    if (!promptsByScene[scene]) promptsByScene[scene] = [];
    promptsByScene[scene].push(prompt);
  });

  // Count edited prompts
  const editedCount = prompts.filter(p => p.edited).length;

  if (prompts.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Prompts</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Director pipeline to generate prompts for editing
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
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold flex items-center gap-2">
                <ImageIcon className="h-5 w-5" />
                Storyboard Prompts
              </h1>
              {source === "prompts_json" && (
                <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                  Editable
                </span>
              )}
              {source === "prompts_log" && (
                <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                  Generated
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {editedCount > 0 && (
                <span className="text-xs text-amber-400">
                  {editedCount} edited
                </span>
              )}
              <span className="text-sm text-muted-foreground">{prompts.length} prompts</span>
              <button
                onClick={allExpanded ? collapseAll : expandAll}
                className="text-xs text-primary hover:underline"
              >
                {allExpanded ? "Collapse All" : "Expand All"}
              </button>
            </div>
          </div>

          {/* Info banner for editable prompts */}
          {source === "prompts_json" && (
            <div className="bg-secondary/50 border border-border rounded-lg p-4">
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">Edit prompts before generating images.</span>{" "}
                Click on any prompt to edit it, then save your changes. Run the Storyboard pipeline to generate images using your edited prompts.
              </p>
            </div>
          )}

          {/* Prompts grouped by scene */}
          {Object.entries(promptsByScene).map(([sceneNum, scenePrompts]) => (
            <div key={sceneNum} className="space-y-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg">
                <MapPin className="h-4 w-4 text-blue-400" />
                <span className="font-medium">Scene {sceneNum}</span>
                <span className="text-xs text-muted-foreground">({scenePrompts.length} frames)</span>
              </div>

              {scenePrompts.map((prompt) => {
                const isExpanded = expandedPrompts.has(prompt.id);
                const isEditing = editingPrompt === prompt.id;
                const isRegenerating = regenerating === prompt.id;
                const isSaving = saving === prompt.id;
                const fullPrompt = prompt.full_prompt || prompt.prompt;
                const displayPrompt = prompt.original_prompt || prompt.prompt;

                return (
                  <div key={prompt.id} className={cn(
                    "bg-card rounded-lg border ml-4 overflow-hidden",
                    prompt.edited ? "border-amber-500/50" : "border-border"
                  )}>
                    {/* Header row */}
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary/30"
                      onClick={() => toggleExpand(prompt.id)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-mono font-medium rounded">
                          🖼️ [{prompt.id}]
                        </span>
                        {prompt.edited && (
                          <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">
                            edited
                          </span>
                        )}
                        {prompt.status && (
                          <span className={cn(
                            "px-1.5 py-0.5 text-xs rounded",
                            prompt.status === "success" ? "bg-green-500/20 text-green-400" :
                            prompt.status === "failed" || prompt.status === "error" ? "bg-red-500/20 text-red-400" :
                            "bg-yellow-500/20 text-yellow-400"
                          )}>
                            {prompt.status}
                          </span>
                        )}
                        {prompt.has_prior_frame && (
                          <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                            +prior
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {prompt.model && (
                          <span className="text-xs text-muted-foreground">{prompt.model}</span>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                    </div>

                    {/* Tags row - always visible */}
                    {prompt.tags && prompt.tags.length > 0 && (
                      <div className="px-4 pb-3 flex flex-wrap gap-1.5">
                        {prompt.tags.map((tag) => {
                          const style = getTagStyle(tag);
                          return (
                            <span key={tag} className={cn("px-1.5 py-0.5 bg-secondary/50 text-xs rounded", style.color)}>
                              {style.icon} [{tag}]
                            </span>
                          );
                        })}
                      </div>
                    )}

                    {/* Collapsed preview */}
                    {!isExpanded && (
                      <div className="px-4 pb-4">
                        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">
                          {displayPrompt}
                        </p>
                      </div>
                    )}

                    {/* Expanded content */}
                    {isExpanded && (
                      <div className="px-4 pb-4 space-y-4 border-t border-border pt-4">
                        {/* Original Prompt Section */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-muted-foreground uppercase">Original Prompt</span>
                            {!isEditing && (
                              <button
                                onClick={(e) => { e.stopPropagation(); startEditing(prompt); }}
                                className="flex items-center gap-1 text-xs text-primary hover:underline"
                              >
                                <Edit3 className="h-3 w-3" />
                                Edit
                              </button>
                            )}
                          </div>
                          {isEditing ? (
                            <div className="space-y-2">
                              <textarea
                                value={editedText}
                                onChange={(e) => setEditedText(e.target.value)}
                                className="w-full h-32 p-3 bg-secondary rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                                onClick={(e) => e.stopPropagation()}
                              />
                              <div className="flex items-center gap-2">
                                {/* Save button - saves without regenerating */}
                                <button
                                  onClick={(e) => { e.stopPropagation(); savePrompt(prompt.id); }}
                                  disabled={isSaving}
                                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-xs rounded hover:bg-green-700 disabled:opacity-50"
                                >
                                  <Save className={cn("h-3 w-3", isSaving && "animate-pulse")} />
                                  {isSaving ? "Saving..." : "Save"}
                                </button>
                                {/* Regenerate button - saves and regenerates image */}
                                {source === "prompts_log" && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); regeneratePrompt(prompt.id); }}
                                    disabled={isRegenerating}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-xs rounded hover:bg-primary/90 disabled:opacity-50"
                                  >
                                    <RefreshCw className={cn("h-3 w-3", isRegenerating && "animate-spin")} />
                                    {isRegenerating ? "Regenerating..." : "Regenerate"}
                                  </button>
                                )}
                                <button
                                  onClick={(e) => { e.stopPropagation(); cancelEditing(); }}
                                  className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                                >
                                  Cancel
                                </button>
                              </div>
                              {source === "prompts_json" && (
                                <p className="text-xs text-muted-foreground">
                                  Save your edits, then run Storyboard pipeline to generate images.
                                </p>
                              )}
                            </div>
                          ) : (
                            <p className="text-sm text-foreground leading-relaxed bg-secondary/30 p-3 rounded-lg">
                              {displayPrompt}
                            </p>
                          )}
                        </div>

                        {/* Full Prompt Section (with labels) */}
                        {prompt.full_prompt && prompt.full_prompt !== displayPrompt && (
                          <div>
                            <span className="text-xs font-medium text-muted-foreground uppercase mb-2 block">
                              Full Prompt (with reference labels)
                            </span>
                            <p className="text-sm text-muted-foreground leading-relaxed bg-secondary/30 p-3 rounded-lg font-mono text-xs">
                              {fullPrompt}
                            </p>
                          </div>
                        )}

                        {/* Reference Images */}
                        {prompt.reference_images && prompt.reference_images.length > 0 && (
                          <div>
                            <span className="text-xs font-medium text-muted-foreground uppercase mb-2 block">
                              Reference Images ({prompt.reference_images.length})
                            </span>
                            <div className="flex flex-wrap gap-2">
                              {prompt.reference_images.map((refPath, idx) => {
                                const fileName = refPath.split(/[/\\]/).pop() || refPath;
                                return (
                                  <span key={idx} className="px-2 py-1 bg-secondary text-xs rounded">
                                    [{idx + 1}] {fileName}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Metadata */}
                        {prompt.timestamp && (
                          <div className="text-xs text-muted-foreground">
                            Generated: {new Date(prompt.timestamp).toLocaleString()}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

