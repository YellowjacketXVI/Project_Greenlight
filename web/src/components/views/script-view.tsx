"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn } from "@/lib/utils";
import { FileText, Film, Image as ImageIcon, RefreshCw, Camera, MapPin, Lightbulb, User, Sparkles, Save, Edit3, ChevronDown, ChevronUp } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import { MentionInput } from "@/components/mention-input";

interface Scene {
  number: number;
  title: string;
  content: string;
  tags: string[];
}

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
}

const tabs = [
  { id: "pitch", label: "Pitch", icon: Sparkles },
  { id: "script", label: "Script", icon: FileText },
  { id: "visual", label: "Visual Script", icon: Film },
  { id: "prompts", label: "Prompts", icon: ImageIcon },
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
  const [script, setScript] = useState<string>("");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [visualFrames, setVisualFrames] = useState<VisualFrame[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
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

      // Load script
      const scriptData = await fetchAPI<{ content: string; scenes: Scene[] }>(
        `/api/projects/${encodeURIComponent(currentProject.path)}/script`
      );
      setScript(scriptData.content);
      setScenes(scriptData.scenes || []);

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
        const promptsData = await fetchAPI<{ prompts: Prompt[] }>(
          `/api/projects/${encodeURIComponent(currentProject.path)}/prompts`
        );
        setPrompts(promptsData.prompts || []);
      } catch {
        setPrompts([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load script");
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

      {/* Script Tab */}
      <Tabs.Content value="script" className="flex-1 overflow-hidden">
        <ScriptTab script={script} scenes={scenes} />
      </Tabs.Content>

      {/* Visual Script Tab */}
      <Tabs.Content value="visual" className="flex-1 overflow-hidden">
        <VisualScriptTab frames={visualFrames} />
      </Tabs.Content>

      {/* Prompts Tab */}
      <Tabs.Content value="prompts" className="flex-1 overflow-hidden">
        <PromptsTab prompts={prompts} />
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

function ScriptTab({ script, scenes }: { script: string; scenes: Scene[] }) {
  const [expandedScenes, setExpandedScenes] = useState<Set<number>>(new Set());

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

  const expandAll = () => {
    setExpandedScenes(new Set(scenes.map(s => s.number)));
  };

  const collapseAll = () => {
    setExpandedScenes(new Set());
  };

  // Threshold for truncation (characters)
  const TRUNCATE_THRESHOLD = 300;

  if (!script && scenes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
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
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Script
            </h1>
            <div className="flex items-center gap-3">
              <div className="flex gap-1">
                <button
                  onClick={expandAll}
                  className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Expand All
                </button>
                <span className="text-muted-foreground">|</span>
                <button
                  onClick={collapseAll}
                  className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Collapse All
                </button>
              </div>
              <span className="text-sm text-muted-foreground">{scenes.length} scenes</span>
            </div>
          </div>

          {scenes.length > 0 ? (
            <div className="space-y-4">
              {scenes.map((scene) => {
                const isExpanded = expandedScenes.has(scene.number);
                const needsTruncation = scene.content.length > TRUNCATE_THRESHOLD;
                const displayContent = isExpanded || !needsTruncation
                  ? scene.content
                  : scene.content.slice(0, TRUNCATE_THRESHOLD) + "...";

                return (
                  <div key={scene.number} className="bg-card rounded-lg border border-border overflow-hidden">
                    {/* Header - always visible, clickable */}
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary/30 transition-colors"
                      onClick={() => needsTruncation && toggleScene(scene.number)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-primary/10 text-primary text-xs font-medium rounded">
                          Scene {scene.number}
                        </span>
                        <h3 className="font-medium">{scene.title}</h3>
                      </div>
                      {needsTruncation && (
                        <button
                          className="p-1 hover:bg-secondary rounded transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleScene(scene.number);
                          }}
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                      )}
                    </div>

                    {/* Content */}
                    <div className="px-4 pb-4">
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                        {displayContent}
                      </p>

                      {/* Expand/Collapse button for long content */}
                      {needsTruncation && !isExpanded && (
                        <button
                          onClick={() => toggleScene(scene.number)}
                          className="mt-2 text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
                        >
                          <ChevronDown className="h-3 w-3" />
                          View Full Text
                        </button>
                      )}

                      {/* Tags */}
                      {scene.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-4 pt-3 border-t border-border">
                          {scene.tags.map((tag) => {
                            const style = getTagStyle(tag);
                            return (
                              <span
                                key={tag}
                                className={cn("px-2 py-0.5 bg-secondary text-xs rounded flex items-center gap-1", style.color)}
                              >
                                <span>{style.icon}</span>
                                [{tag}]
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 bg-card rounded-lg border border-border">
              <pre className="text-sm whitespace-pre-wrap font-mono">{script}</pre>
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

function VisualScriptTab({ frames }: { frames: VisualFrame[] }) {
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

  // Group frames by scene
  const framesByScene: Record<number, VisualFrame[]> = {};
  frames.forEach((frame) => {
    if (!framesByScene[frame.scene]) framesByScene[frame.scene] = [];
    framesByScene[frame.scene].push(frame);
  });

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Film className="h-5 w-5" />
              Visual Script
            </h1>
            <span className="text-sm text-muted-foreground">
              {Object.keys(framesByScene).length} scenes • {frames.length} frames
            </span>
          </div>

          {Object.entries(framesByScene).map(([sceneNum, sceneFrames]) => (
            <div key={sceneNum} className="space-y-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg">
                <MapPin className="h-4 w-4 text-blue-400" />
                <span className="font-medium">Scene {sceneNum}</span>
                <span className="text-xs text-muted-foreground">({sceneFrames.length} frames)</span>
              </div>

              {sceneFrames.map((frame) => (
                <div key={frame.id} className="p-4 bg-card rounded-lg border border-border ml-4">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-mono font-medium rounded">
                      [{frame.scene}.{frame.frame}.{frame.camera || "cA"}]
                    </span>
                    {frame.camera && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Camera className="h-3 w-3" />
                        {frame.camera}
                      </span>
                    )}
                  </div>

                  {/* Technical notations */}
                  <div className="flex flex-wrap gap-2 mb-3">
                    {frame.position && (
                      <span className="px-2 py-1 bg-secondary text-xs rounded flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {frame.position.slice(0, 50)}{frame.position.length > 50 ? "..." : ""}
                      </span>
                    )}
                    {frame.lighting && (
                      <span className="px-2 py-1 bg-secondary text-xs rounded flex items-center gap-1">
                        <Lightbulb className="h-3 w-3" />
                        {frame.lighting.slice(0, 40)}{frame.lighting.length > 40 ? "..." : ""}
                      </span>
                    )}
                  </div>

                  {/* Tags */}
                  {frame.tags && frame.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {frame.tags.slice(0, 8).map((tag) => {
                        const style = getTagStyle(tag);
                        return (
                          <span key={tag} className={cn("px-1.5 py-0.5 bg-secondary/50 text-xs rounded", style.color)}>
                            {style.icon} [{tag}]
                          </span>
                        );
                      })}
                      {frame.tags.length > 8 && (
                        <span className="text-xs text-muted-foreground">+{frame.tags.length - 8} more</span>
                      )}
                    </div>
                  )}

                  {/* Prompt */}
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {frame.prompt.slice(0, 500)}{frame.prompt.length > 500 ? "..." : ""}
                  </p>
                </div>
              ))}
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

function PromptsTab({ prompts: initialPrompts }: { prompts: Prompt[] }) {
  const { currentProject } = useAppStore();
  const [prompts, setPrompts] = useState<Prompt[]>(initialPrompts);
  const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
  const [editingPrompt, setEditingPrompt] = useState<string | null>(null);
  const [editedText, setEditedText] = useState<string>("");
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [allExpanded, setAllExpanded] = useState(false);

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
            ? { ...p, original_prompt: editedText, prompt: editedText, status: "success" }
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

  if (prompts.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <ImageIcon className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Prompts</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Storyboard pipeline to generate prompts
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
            <h1 className="text-xl font-bold flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              Storyboard Prompts
            </h1>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">{prompts.length} prompts</span>
              <button
                onClick={allExpanded ? collapseAll : expandAll}
                className="text-xs text-primary hover:underline"
              >
                {allExpanded ? "Collapse All" : "Expand All"}
              </button>
            </div>
          </div>

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
                const fullPrompt = prompt.full_prompt || prompt.prompt;
                const displayPrompt = prompt.original_prompt || prompt.prompt;

                return (
                  <div key={prompt.id} className="bg-card rounded-lg border border-border ml-4 overflow-hidden">
                    {/* Header row */}
                    <div
                      className="flex items-center justify-between p-4 cursor-pointer hover:bg-secondary/30"
                      onClick={() => toggleExpand(prompt.id)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-mono font-medium rounded">
                          🖼️ [{prompt.id}]
                        </span>
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
                                <button
                                  onClick={(e) => { e.stopPropagation(); regeneratePrompt(prompt.id); }}
                                  disabled={isRegenerating}
                                  className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-xs rounded hover:bg-primary/90 disabled:opacity-50"
                                >
                                  <RefreshCw className={cn("h-3 w-3", isRegenerating && "animate-spin")} />
                                  {isRegenerating ? "Regenerating..." : "Regenerate"}
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); cancelEditing(); }}
                                  className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                                >
                                  Cancel
                                </button>
                              </div>
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

