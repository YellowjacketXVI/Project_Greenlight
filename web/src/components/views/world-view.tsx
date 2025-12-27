"use client";

import { useState, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { fetchAPI, cn, API_BASE_URL } from "@/lib/utils";
import { Globe, User, MapPin, Package, RefreshCw, Palette, ChevronDown, ChevronUp, FolderOpen, Save, Edit2, Sparkles, Loader2, X, Info } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import * as Dialog from "@radix-ui/react-dialog";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import { ReferenceModal } from "@/components/modals";

const MODEL_OPTIONS = [
  { key: 'nano_banana_pro', name: 'Nano Banana Pro (Best)' },
  { key: 'seedream', name: 'Seedream 4.5 (Fast)' },
  { key: 'flux_2_pro', name: 'FLUX 2 Pro (8 refs, text)' },
  { key: 'p_image_edit', name: 'P-Image-Edit ($0.01, fast)' },
];

const VISUAL_STYLES = [
  { key: 'live_action', name: 'Live Action', description: 'Photorealistic live-action cinematography' },
  { key: 'anime', name: 'Anime', description: 'Anime style with expressive characters and bold colors' },
  { key: 'animation_2d', name: '2D Animation', description: 'Hand-drawn 2D animation aesthetic' },
  { key: 'animation_3d', name: '3D Animation', description: 'Modern 3D CGI rendering' },
  { key: 'mixed_reality', name: 'Mixed Reality', description: 'Seamless blend of live action and CGI' },
];

interface WorldEntity {
  tag: string;
  name: string;
  description: string;
  imagePath?: string;
  relationships?: string[];
  scenes?: number[];
  // Extended character fields
  role?: string;
  want?: string;
  need?: string;
  flaw?: string;
  backstory?: string;
  voice_signature?: string;
  emotional_tells?: Record<string, string>;
  physicality?: string;
  speech_patterns?: string;
}

interface StyleData {
  visual_style?: string;
  style_notes?: string;
  lighting?: string;
  vibe?: string;
}

interface WorldData {
  characters: WorldEntity[];
  locations: WorldEntity[];
  props: WorldEntity[];
  style?: StyleData;
}

const tabs = [
  { id: "characters", label: "Characters", icon: User },
  { id: "locations", label: "Locations", icon: MapPin },
  { id: "props", label: "Props", icon: Package },
  { id: "style", label: "Style Core", icon: Palette },
];

// Get icon based on entity type
function getEntityIcon(tab: string) {
  switch (tab) {
    case "characters": return User;
    case "locations": return MapPin;
    case "props": return Package;
    default: return Globe;
  }
}

// Get tag color based on prefix
function getTagColor(tag: string): string {
  if (tag.startsWith("CHAR_")) return "text-blue-400 bg-blue-500/10";
  if (tag.startsWith("LOC_")) return "text-green-400 bg-green-500/10";
  if (tag.startsWith("PROP_")) return "text-orange-400 bg-orange-500/10";
  return "text-primary bg-primary/10";
}

export function WorldView() {
  const { currentProject, addPipelineProcess, updatePipelineProcess, addProcessLog, setWorkspaceMode } = useAppStore();
  const [worldData, setWorldData] = useState<WorldData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("characters");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  // FAB state for bulk reference generation
  const [generatingAll, setGeneratingAll] = useState(false);
  const [fabModel, setFabModel] = useState('nano_banana_pro');
  const [fabMenuOpen, setFabMenuOpen] = useState(false);

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

  const toggleCard = (tag: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  };

  // Track logs we've already added to avoid duplicates during polling
  const [processedLogs, setProcessedLogs] = useState<Set<string>>(new Set());

  const handleGenerateAll = async () => {
    if (!currentProject || generatingAll) return;

    setGeneratingAll(true);
    setFabMenuOpen(false);
    setProcessedLogs(new Set());

    // Create a local process ID for the store (different from backend process_id)
    const localProcessId = `references-${Date.now()}`;
    const tabLabel = activeTab.charAt(0).toUpperCase() + activeTab.slice(1);
    const modelLabel = MODEL_OPTIONS.find(m => m.key === fabModel)?.name || fabModel;

    addPipelineProcess({
      id: localProcessId,
      name: `Generate ${tabLabel} References`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Switch to progress view to show the generation
    setWorkspaceMode('progress');

    try {
      addProcessLog(localProcessId, `Starting reference generation for ${tabLabel}...`, 'info');
      addProcessLog(localProcessId, `Using model: ${modelLabel}`, 'info');
      updatePipelineProcess(localProcessId, { status: 'running' });

      // Start the background process - returns immediately with process_id
      const response = await fetchAPI<{
        success: boolean;
        message: string;
        process_id?: string;
      }>(`/api/projects/${encodeURIComponent(currentProject.path)}/references/generate-all`, {
        method: 'POST',
        body: JSON.stringify({
          tagType: activeTab,
          model: fabModel,
          overwrite: false,
          visual_style: worldData?.style?.visual_style || 'live_action'
        })
      });

      if (response.success && response.process_id) {
        // Store backend ID for cancellation
        updatePipelineProcess(localProcessId, { backendId: response.process_id });
        addProcessLog(localProcessId, `Process started with ID: ${response.process_id}`, 'info');
        // Start polling for status updates
        pollReferenceStatus(response.process_id, localProcessId);
      } else {
        addProcessLog(localProcessId, response.message || 'Failed to start generation', 'error');
        updatePipelineProcess(localProcessId, {
          status: 'error',
          endTime: new Date()
        });
        setGeneratingAll(false);
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      addProcessLog(localProcessId, `Error: ${errorMsg}`, 'error');
      updatePipelineProcess(localProcessId, {
        status: 'error',
        error: errorMsg,
        endTime: new Date()
      });
      setGeneratingAll(false);
    }
  };

  const pollReferenceStatus = async (backendProcessId: string, localProcessId: string) => {
    if (!currentProject) return;

    const poll = async () => {
      try {
        const status = await fetchAPI<{
          status: string;
          progress: number;
          logs: string[];
          generated: number;
          skipped: number;
          total: number;
          errors: string[];
          error?: string;
        }>(`/api/projects/${encodeURIComponent(currentProject.path)}/references/status/${backendProcessId}`);

        // Update progress
        updatePipelineProcess(localProcessId, { progress: status.progress });

        // Add new logs (avoid duplicates)
        if (status.logs && status.logs.length > 0) {
          status.logs.forEach((log, idx) => {
            const logKey = `${idx}-${log}`;
            if (!processedLogs.has(logKey)) {
              const type = log.includes('❌') || log.includes('Error') || log.includes('Failed') ? 'error' :
                          log.includes('✓') || log.includes('✅') || log.includes('Complete') ? 'success' :
                          log.includes('⏭️') || log.includes('Skipping') ? 'warning' : 'info';
              addProcessLog(localProcessId, log, type);
              setProcessedLogs(prev => new Set(prev).add(logKey));
            }
          });
        }

        // Check completion status
        if (status.status === 'complete') {
          updatePipelineProcess(localProcessId, {
            status: 'complete',
            progress: 1,
            endTime: new Date()
          });
          setGeneratingAll(false);
          // Refresh world data to show new images
          loadWorld();
        } else if (status.status === 'failed') {
          addProcessLog(localProcessId, status.error || 'Generation failed', 'error');
          updatePipelineProcess(localProcessId, {
            status: 'error',
            error: status.error,
            endTime: new Date()
          });
          setGeneratingAll(false);
        } else {
          // Still running, poll again
          setTimeout(poll, 1000);
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        addProcessLog(localProcessId, `Polling error: ${errorMsg}`, 'error');
        updatePipelineProcess(localProcessId, {
          status: 'error',
          error: errorMsg,
          endTime: new Date()
        });
        setGeneratingAll(false);
      }
    };

    poll();
  };

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

  const getCounts = () => ({
    characters: worldData.characters?.length || 0,
    locations: worldData.locations?.length || 0,
    props: worldData.props?.length || 0,
  });

  const counts = getCounts();

  return (
    <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
      <Tabs.List className="flex border-b border-border px-4 bg-card/50">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const count = counts[tab.id as keyof typeof counts];
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
              {count !== undefined && count > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-secondary rounded-full">{count}</span>
              )}
            </Tabs.Trigger>
          );
        })}
      </Tabs.List>

      {/* Entity Tabs */}
      {activeTab !== "style" && (
        <Tabs.Content value={activeTab} className="flex-1 overflow-hidden">
          <EntityGrid
            entities={getEntities()}
            tabType={activeTab}
            expandedCards={expandedCards}
            onToggleCard={toggleCard}
            projectPath={currentProject?.path}
            onRefresh={loadWorld}
          />
        </Tabs.Content>
      )}

      {/* Style Core Tab */}
      <Tabs.Content value="style" className="flex-1 overflow-hidden">
        <StyleCoreTab
          style={worldData.style}
          projectPath={currentProject?.path}
          onSave={loadWorld}
        />
      </Tabs.Content>

      {/* Generate All References FAB - only show on entity tabs */}
      {activeTab !== "style" && (
        <div className="fixed bottom-6 right-6 z-40">
          {/* FAB with dropdown */}
          <div className="relative">
            {fabMenuOpen && (
              <div className="absolute bottom-full right-0 mb-2 w-48 bg-card border border-border rounded-lg shadow-xl overflow-hidden">
                <div className="p-2 border-b border-border">
                  <span className="text-xs text-muted-foreground">Select Model</span>
                </div>
                {MODEL_OPTIONS.map((model) => (
                  <button
                    key={model.key}
                    onClick={() => setFabModel(model.key)}
                    className={cn(
                      "w-full text-left px-3 py-2 text-sm hover:bg-secondary transition-colors",
                      fabModel === model.key && "bg-secondary text-primary"
                    )}
                  >
                    {model.name}
                    {fabModel === model.key && " ✓"}
                  </button>
                ))}
                <div className="border-t border-border p-2">
                  <button
                    onClick={handleGenerateAll}
                    disabled={generatingAll}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {generatingAll ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Generate All
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            <button
              onClick={() => setFabMenuOpen(!fabMenuOpen)}
              disabled={generatingAll}
              className={cn(
                "flex items-center gap-2 px-4 py-3 rounded-full shadow-lg transition-all",
                generatingAll
                  ? "bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-xl"
              )}
            >
              {generatingAll ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Sparkles className="h-5 w-5" />
              )}
              <span className="font-medium">
                {generatingAll ? "Generating..." : "Generate All References"}
              </span>
            </button>
          </div>
        </div>
      )}
    </Tabs.Root>
  );
}

function EntityGrid({
  entities,
  tabType,
  expandedCards,
  onToggleCard,
  projectPath,
  onRefresh
}: {
  entities: WorldEntity[];
  tabType: string;
  expandedCards: Set<string>;
  onToggleCard: (tag: string) => void;
  projectPath?: string;
  onRefresh?: () => void;
}) {
  const Icon = getEntityIcon(tabType);

  if (entities.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Icon className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No {tabType} found</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Writer pipeline to extract {tabType}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {entities.map((entity) => (
            <EntityCard
              key={entity.tag}
              entity={entity}
              tabType={tabType}
              isExpanded={expandedCards.has(entity.tag)}
              onToggle={() => onToggleCard(entity.tag)}
              projectPath={projectPath}
              onRefresh={onRefresh}
            />
          ))}
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

function EntityCard({
  entity,
  tabType,
  isExpanded,
  onToggle,
  projectPath,
  onRefresh
}: {
  entity: WorldEntity;
  tabType: string;
  isExpanded: boolean;
  onToggle: () => void;
  projectPath?: string;
  onRefresh?: () => void;
}) {
  const [referenceModalOpen, setReferenceModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedDescription, setEditedDescription] = useState(entity.description);
  const [saving, setSaving] = useState(false);
  const Icon = getEntityIcon(tabType);
  const tagColor = getTagColor(entity.tag);

  // Reset edited description when entity changes
  useEffect(() => {
    setEditedDescription(entity.description);
  }, [entity.description]);

  const handleSaveDescription = async () => {
    if (!projectPath || editedDescription === entity.description) {
      setIsEditing(false);
      return;
    }

    setSaving(true);
    try {
      await fetchAPI(`/api/projects/${encodeURIComponent(projectPath)}/world/entity/${encodeURIComponent(entity.tag)}`, {
        method: 'PATCH',
        body: JSON.stringify({ description: editedDescription })
      });
      setIsEditing(false);
      onRefresh?.();
    } catch (err) {
      console.error('Failed to save description:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditedDescription(entity.description);
    setIsEditing(false);
  };

  // Map tabType to tagType for the modal
  const tagType = tabType === "characters" ? "character" : tabType === "locations" ? "location" : "prop";

  // Check if entity has extended details (for characters)
  const hasExtendedDetails = tabType === "characters" && (
    entity.role || entity.want || entity.need || entity.flaw ||
    entity.backstory || entity.voice_signature || entity.emotional_tells ||
    entity.physicality || entity.speech_patterns
  );

  return (
    <>
      <div className="bg-card rounded-lg border border-border overflow-hidden hover:border-primary/50 transition-colors">
        {/* Image Section */}
        <div className="aspect-[16/12] bg-secondary flex items-center justify-center relative group">
          {entity.imagePath ? (
            <>
              <img
                src={`${API_BASE_URL}/api/images/${encodeURIComponent(entity.imagePath)}`}
                alt={entity.name}
                className="w-full h-full object-contain bg-black"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                <button
                  onClick={() => setReferenceModalOpen(true)}
                  className="px-3 py-1.5 bg-primary text-primary-foreground text-sm rounded-md hover:bg-primary/90 transition-colors flex items-center gap-1"
                >
                  <FolderOpen className="h-4 w-4" />
                  Manage References
                </button>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Icon className="h-12 w-12 text-muted-foreground" />
              <button
                onClick={() => setReferenceModalOpen(true)}
                className="px-3 py-1.5 bg-secondary text-foreground text-xs rounded-md hover:bg-secondary/80 transition-colors flex items-center gap-1"
              >
                <FolderOpen className="h-3 w-3" />
                Manage References
              </button>
            </div>
          )}
        </div>

        {/* Content Section */}
        <div className="p-4 space-y-3">
          {/* Tag Badge and Role */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={cn("px-2 py-1 text-xs font-mono rounded", tagColor)}>
                [{entity.tag}]
              </span>
              {entity.role && (
                <span className="px-2 py-0.5 bg-secondary text-xs rounded capitalize">
                  {entity.role.replace(/_/g, ' ')}
                </span>
              )}
            </div>
            <button
              onClick={onToggle}
              className="p-1 hover:bg-secondary rounded transition-colors"
            >
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>

          {/* Name */}
          <h3 className="font-semibold text-lg">{entity.name}</h3>

          {/* Description - editable */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {tabType === "characters" ? "Appearance" : "Description"}
              </span>
              {!isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="p-1 hover:bg-secondary rounded transition-colors"
                  title="Edit description"
                >
                  <Edit2 className="h-3 w-3 text-muted-foreground" />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                <textarea
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  className="w-full min-h-[80px] p-2 text-xs bg-secondary border border-border rounded resize-y focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Enter description..."
                />
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={handleCancelEdit}
                    disabled={saving}
                    className="px-2 py-1 text-xs bg-secondary hover:bg-secondary/80 rounded transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveDescription}
                    disabled={saving}
                    className="px-2 py-1 text-xs bg-primary text-primary-foreground hover:bg-primary/90 rounded transition-colors flex items-center gap-1"
                  >
                    {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                    Save
                  </button>
                </div>
              </div>
            ) : (
              <p className={cn(
                "text-xs text-muted-foreground leading-relaxed",
                !isExpanded && "line-clamp-5"
              )}>
                {entity.description}
              </p>
            )}
          </div>

          {/* Expanded Details */}
          {isExpanded && (
            <div className="pt-3 border-t border-border space-y-2">
              {entity.relationships && entity.relationships.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-muted-foreground">Relationships:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {entity.relationships.map((rel) => (
                      <span key={rel} className="px-1.5 py-0.5 bg-secondary text-xs rounded">
                        {rel}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {entity.scenes && entity.scenes.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-muted-foreground">Appears in:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {entity.scenes.map((scene) => (
                      <span key={scene} className="px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded">
                        Scene {scene}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* See More button for characters with extended details */}
              {hasExtendedDetails && (
                <button
                  onClick={() => setDetailModalOpen(true)}
                  className="w-full mt-2 px-3 py-2 bg-secondary hover:bg-secondary/80 text-sm rounded-md transition-colors flex items-center justify-center gap-2"
                >
                  <Info className="h-4 w-4" />
                  See Full Profile
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Reference Modal */}
      {projectPath && (
        <ReferenceModal
          open={referenceModalOpen}
          onOpenChange={setReferenceModalOpen}
          tag={entity.tag}
          name={entity.name}
          tagType={tagType}
          projectPath={projectPath}
          onRefresh={onRefresh}
        />
      )}

      {/* Character Detail Modal */}
      {hasExtendedDetails && (
        <CharacterDetailModal
          open={detailModalOpen}
          onOpenChange={setDetailModalOpen}
          entity={entity}
        />
      )}
    </>
  );
}

// Character Detail Modal Component
function CharacterDetailModal({
  open,
  onOpenChange,
  entity
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entity: WorldEntity;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-card border border-border rounded-lg shadow-xl z-50 w-[90vw] max-w-3xl max-h-[85vh] flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Full character profile for {entity.name}
            </Dialog.Description>
          </VisuallyHidden.Root>

          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <Dialog.Title className="text-lg font-semibold flex items-center gap-2">
              <User className="h-5 w-5" />
              {entity.name}
              {entity.role && (
                <span className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded capitalize">
                  {entity.role.replace(/_/g, ' ')}
                </span>
              )}
            </Dialog.Title>
            <Dialog.Close className="p-2 hover:bg-secondary rounded-md transition-colors">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {/* Content */}
          <ScrollArea.Root className="flex-1 overflow-hidden">
            <ScrollArea.Viewport className="h-full w-full p-6">
              <div className="space-y-6">
                {/* Description */}
                <section>
                  <h3 className="text-sm font-semibold text-primary mb-2">Description</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {entity.description}
                  </p>
                </section>

                {/* Core Motivations */}
                {(entity.want || entity.need || entity.flaw) && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Core Motivations</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {entity.want && (
                        <div className="p-3 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-green-400">WANT</span>
                          <p className="text-sm text-muted-foreground mt-1">{entity.want}</p>
                        </div>
                      )}
                      {entity.need && (
                        <div className="p-3 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-blue-400">NEED</span>
                          <p className="text-sm text-muted-foreground mt-1">{entity.need}</p>
                        </div>
                      )}
                      {entity.flaw && (
                        <div className="p-3 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-red-400">FLAW</span>
                          <p className="text-sm text-muted-foreground mt-1">{entity.flaw}</p>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* Backstory */}
                {entity.backstory && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Backstory</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {entity.backstory}
                    </p>
                  </section>
                )}

                {/* Voice & Speech */}
                {(entity.voice_signature || entity.speech_patterns) && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Voice & Speech</h3>
                    <div className="space-y-2">
                      {entity.voice_signature && (
                        <div className="p-3 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-purple-400">Voice Signature</span>
                          <p className="text-sm text-muted-foreground mt-1">{entity.voice_signature}</p>
                        </div>
                      )}
                      {entity.speech_patterns && (
                        <div className="p-3 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-purple-400">Speech Patterns</span>
                          <p className="text-sm text-muted-foreground mt-1">{entity.speech_patterns}</p>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* Physicality */}
                {entity.physicality && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Physicality</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {entity.physicality}
                    </p>
                  </section>
                )}

                {/* Emotional Tells */}
                {entity.emotional_tells && Object.keys(entity.emotional_tells).length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Emotional Tells</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {Object.entries(entity.emotional_tells).map(([emotion, tell]) => (
                        <div key={emotion} className="p-2 bg-secondary/50 rounded-lg">
                          <span className="text-xs font-medium text-orange-400 capitalize">{emotion}</span>
                          <p className="text-xs text-muted-foreground mt-1">{tell}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Relationships */}
                {entity.relationships && entity.relationships.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Relationships</h3>
                    <div className="flex flex-wrap gap-2">
                      {entity.relationships.map((rel) => (
                        <span key={rel} className="px-2 py-1 bg-secondary text-sm rounded">
                          {rel}
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                {/* Scenes */}
                {entity.scenes && entity.scenes.length > 0 && (
                  <section>
                    <h3 className="text-sm font-semibold text-primary mb-2">Appears In</h3>
                    <div className="flex flex-wrap gap-2">
                      {entity.scenes.map((scene) => (
                        <span key={scene} className="px-2 py-1 bg-primary/10 text-primary text-sm rounded">
                          Scene {scene}
                        </span>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            </ScrollArea.Viewport>
            <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
              <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
            </ScrollArea.Scrollbar>
          </ScrollArea.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function StyleCoreTab({
  style,
  projectPath,
  onSave
}: {
  style?: StyleData;
  projectPath?: string;
  onSave?: () => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editedStyle, setEditedStyle] = useState<StyleData>({
    visual_style: style?.visual_style || 'live_action',
    style_notes: style?.style_notes || '',
    lighting: style?.lighting || '',
    vibe: style?.vibe || '',
  });

  // Update local state when style prop changes
  useEffect(() => {
    if (style) {
      setEditedStyle({
        visual_style: style.visual_style || 'live_action',
        style_notes: style.style_notes || '',
        lighting: style.lighting || '',
        vibe: style.vibe || '',
      });
    }
  }, [style]);

  const handleSave = async () => {
    if (!projectPath) return;
    setIsSaving(true);
    try {
      await fetchAPI(`/api/projects/${encodeURIComponent(projectPath)}/style`, {
        method: 'POST',
        body: JSON.stringify(editedStyle)
      });
      setIsEditing(false);
      onSave?.();
    } catch (err) {
      console.error('Failed to save style:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const getStyleDisplayName = (key: string) => {
    return VISUAL_STYLES.find(s => s.key === key)?.name || key;
  };

  // Show empty state only if no style data AND not editing
  if (!isEditing && (!style || (!style.visual_style && !style.style_notes && !style.lighting && !style.vibe))) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4">
          <Palette className="h-12 w-12 text-muted-foreground mx-auto" />
          <div>
            <h3 className="font-medium">No Style Data</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Run the Writer pipeline or click Edit to add style information
            </p>
          </div>
          {projectPath && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Edit2 className="h-4 w-4 inline mr-2" />
              Add Style
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <ScrollArea.Root className="h-full">
      <ScrollArea.Viewport className="h-full w-full p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Palette className="h-6 w-6 text-primary" />
              <h1 className="text-xl font-bold">Style Core</h1>
            </div>
            {projectPath && (
              <div className="flex gap-2">
                {isEditing ? (
                  <>
                    <button
                      onClick={() => setIsEditing(false)}
                      className="px-3 py-1.5 text-sm bg-secondary hover:bg-secondary/80 rounded transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className="px-3 py-1.5 text-sm bg-primary text-primary-foreground hover:bg-primary/90 rounded transition-colors flex items-center gap-1 disabled:opacity-50"
                    >
                      <Save className="h-4 w-4" />
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-3 py-1.5 text-sm bg-secondary hover:bg-secondary/80 rounded transition-colors flex items-center gap-1"
                  >
                    <Edit2 className="h-4 w-4" />
                    Edit
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="space-y-4">
            {/* Visual Style - Dropdown when editing */}
            <div className="p-4 bg-card rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <span>🎬</span>
                <h3 className="font-medium text-sm text-muted-foreground">Visual Style</h3>
              </div>
              {isEditing ? (
                <div className="space-y-2">
                  <select
                    value={editedStyle.visual_style}
                    onChange={(e) => setEditedStyle({ ...editedStyle, visual_style: e.target.value })}
                    className="w-full px-3 py-2 bg-[#2a2a2a] border border-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100"
                  >
                    {VISUAL_STYLES.map((s) => (
                      <option key={s.key} value={s.key} className="bg-[#2a2a2a] text-gray-100">{s.name}</option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    {VISUAL_STYLES.find(s => s.key === editedStyle.visual_style)?.description}
                  </p>
                </div>
              ) : (
                <p className="text-foreground leading-relaxed">
                  {getStyleDisplayName(editedStyle.visual_style || 'live_action')}
                </p>
              )}
            </div>

            {/* Style Notes - Textarea when editing */}
            <div className="p-4 bg-card rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <span>📝</span>
                <h3 className="font-medium text-sm text-muted-foreground">Style Notes</h3>
              </div>
              {isEditing ? (
                <textarea
                  value={editedStyle.style_notes}
                  onChange={(e) => setEditedStyle({ ...editedStyle, style_notes: e.target.value })}
                  rows={4}
                  placeholder="Describe the visual style, color palette, mood..."
                  className="w-full px-3 py-2 bg-secondary border border-border rounded text-foreground resize-none"
                />
              ) : (
                <p className="text-foreground leading-relaxed">
                  {editedStyle.style_notes || <span className="text-muted-foreground italic">No style notes</span>}
                </p>
              )}
            </div>

            {/* Lighting - Textarea when editing */}
            <div className="p-4 bg-card rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <span>💡</span>
                <h3 className="font-medium text-sm text-muted-foreground">Lighting</h3>
              </div>
              {isEditing ? (
                <textarea
                  value={editedStyle.lighting}
                  onChange={(e) => setEditedStyle({ ...editedStyle, lighting: e.target.value })}
                  rows={3}
                  placeholder="Describe the lighting style (e.g., chiaroscuro, natural, neon...)"
                  className="w-full px-3 py-2 bg-secondary border border-border rounded text-foreground resize-none"
                />
              ) : (
                <p className="text-foreground leading-relaxed">
                  {editedStyle.lighting || <span className="text-muted-foreground italic">No lighting defined</span>}
                </p>
              )}
            </div>

            {/* Vibe - Input when editing */}
            <div className="p-4 bg-card rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <span>✨</span>
                <h3 className="font-medium text-sm text-muted-foreground">Vibe</h3>
              </div>
              {isEditing ? (
                <input
                  type="text"
                  value={editedStyle.vibe}
                  onChange={(e) => setEditedStyle({ ...editedStyle, vibe: e.target.value })}
                  placeholder="3-5 mood words (e.g., Intimate, Poetic, Subversive)"
                  className="w-full px-3 py-2 bg-secondary border border-border rounded text-foreground"
                />
              ) : (
                <p className="text-foreground leading-relaxed">
                  {editedStyle.vibe || <span className="text-muted-foreground italic">No vibe defined</span>}
                </p>
              )}
            </div>
          </div>
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex select-none touch-none p-0.5 bg-secondary w-2" orientation="vertical">
        <ScrollArea.Thumb className="flex-1 bg-muted-foreground rounded-full" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

