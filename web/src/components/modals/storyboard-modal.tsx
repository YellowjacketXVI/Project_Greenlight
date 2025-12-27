'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { X, Play, Loader2, Image as ImageIcon } from 'lucide-react';
import { useStore, useAppStore } from '@/lib/store';
import { fetchAPI } from '@/lib/utils';

interface StoryboardModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ImageModel {
  key: string;
  display_name: string;
  provider: string;
  description: string;
}

interface VisualScriptData {
  total_frames: number;
  total_scenes: number;
  scenes: Array<{
    scene_number: number;
    frames: Array<{ prompt: string }>;
  }>;
}

export function StoryboardModal({ open, onOpenChange }: StoryboardModalProps) {
  const { projectPath } = useStore();
  const { addPipelineProcess, updatePipelineProcess, addProcessLog, setWorkspaceMode } = useAppStore();
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [models, setModels] = useState<ImageModel[]>([]);
  const [selectedModel, setSelectedModel] = useState('seedream_4_5');
  const [visualScript, setVisualScript] = useState<VisualScriptData | null>(null);
  const [backendPipelineId, setBackendPipelineId] = useState<string | null>(null);
  const [processId, setProcessId] = useState<string | null>(null);

  useEffect(() => {
    if (open && projectPath) {
      loadModels();
      loadVisualScript();
    }
  }, [open, projectPath]);

  const loadModels = async () => {
    try {
      // Use storyboard-models endpoint for curated list (Seedream, Nano Banana Pro, FLUX Kontext)
      const data = await fetchAPI<{ models?: ImageModel[] }>('/api/settings/storyboard-models');
      const modelList = data.models || [];
      setModels(modelList);
      // Default to seedream if available
      const seedream = modelList.find(m => m.key.includes('seedream'));
      if (seedream) {
        setSelectedModel(seedream.key);
      } else if (modelList.length > 0) {
        setSelectedModel(modelList[0].key);
      }
    } catch (e) {
      console.error('Failed to load models:', e);
    }
  };

  const loadVisualScript = async () => {
    try {
      const data = await fetchAPI<{ visual_script?: VisualScriptData }>(`/api/projects/${encodeURIComponent(projectPath)}/storyboard`);
      if (data.visual_script) {
        setVisualScript(data.visual_script);
      }
    } catch (e) {
      console.error('Failed to load visual script:', e);
    }
  };

  const handleGenerate = async () => {
    if (!projectPath || !visualScript) return;
    setIsRunning(true);
    setProgress(0);
    setLogs([]);
    setBackendPipelineId(null);

    // Create a new process in the global store
    const newProcessId = `storyboard-${Date.now()}`;
    setProcessId(newProcessId);
    addPipelineProcess({
      id: newProcessId,
      name: `Storyboard: ${visualScript.total_frames} frames`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      addProcessLog(newProcessId, 'Starting Storyboard generation...', 'info');
      updatePipelineProcess(newProcessId, { status: 'running' });

      const response = await fetchAPI<{ pipeline_id?: string }>('/api/pipelines/storyboard', {
        method: 'POST',
        body: JSON.stringify({
          project_path: projectPath,
          image_model: selectedModel
        })
      });

      if (response.pipeline_id) {
        // Store backend ID for cancellation
        setBackendPipelineId(response.pipeline_id);
        updatePipelineProcess(newProcessId, { backendId: response.pipeline_id });
        addProcessLog(newProcessId, `Pipeline started with ID: ${response.pipeline_id}`, 'info');
        pollStatus(response.pipeline_id, newProcessId);
      }
    } catch (e) {
      addProcessLog(newProcessId, `Error: ${e}`, 'error');
      updatePipelineProcess(newProcessId, { status: 'error', error: String(e), endTime: new Date() });
      setIsRunning(false);
    }
  };

  const pollStatus = async (pipelineId: string, processId: string) => {
    let lastLogIndex = 0;

    const poll = async () => {
      try {
        const status = await fetchAPI<{
          status: string;
          progress?: number;
          logs?: string[];
          current_stage?: string;
          stages?: Array<{ name: string; status: string; message?: string }>;
          total_items?: number;
          completed_items?: number;
          current_item?: string;
        }>(`/api/pipelines/status/${pipelineId}`);

        setProgress(status.progress || 0);

        // Build update object with all new fields
        const updates: Record<string, unknown> = {
          progress: status.progress || 0,
        };

        // Update current stage and item info
        if (status.current_stage !== undefined) {
          updates.currentStage = status.current_stage;
        }
        if (status.current_item !== undefined) {
          updates.currentItem = status.current_item;
        }
        if (status.total_items !== undefined) {
          updates.totalItems = status.total_items;
        }
        if (status.completed_items !== undefined) {
          updates.completedItems = status.completed_items;
        }

        // Update stages from backend
        if (status.stages && status.stages.length > 0) {
          updates.stages = status.stages.map(s => ({
            name: s.name,
            status: s.status as "running" | "complete" | "error" | "initializing",
            message: s.message,
          }));
        }

        updatePipelineProcess(processId, updates);

        // Add only NEW logs to the process (using index tracking)
        const newLogs = status.logs || [];
        if (newLogs.length > lastLogIndex) {
          const addedLogs = newLogs.slice(lastLogIndex);
          addedLogs.forEach(log => {
            const type = log.includes('❌') || log.includes('Error') || log.includes('Failed') ? 'error' :
                        log.includes('✓') || log.includes('✅') || log.includes('Complete') ? 'success' :
                        log.includes('⚠') ? 'warning' : 'info';
            addProcessLog(processId, log, type);
          });
          lastLogIndex = newLogs.length;
        }
        setLogs(newLogs);

        if (status.status === 'complete') {
          addProcessLog(processId, 'Storyboard generation completed successfully!', 'success');
          updatePipelineProcess(processId, {
            status: 'complete',
            progress: 1,
            endTime: new Date(),
            currentStage: undefined,
            currentItem: undefined
          });
          setIsRunning(false);
        } else if (status.status === 'failed') {
          addProcessLog(processId, 'Storyboard generation failed', 'error');
          updatePipelineProcess(processId, { status: 'error', endTime: new Date() });
          setIsRunning(false);
        } else if (status.status === 'cancelled') {
          updatePipelineProcess(processId, { status: 'cancelled', endTime: new Date() });
          setIsRunning(false);
        } else {
          setTimeout(poll, 2000);
        }
      } catch (e) {
        addProcessLog(processId, `Polling error: ${e}`, 'error');
        updatePipelineProcess(processId, { status: 'error', error: String(e), endTime: new Date() });
        setIsRunning(false);
      }
    };
    poll();
  };

  // Extract tag counts from visual script
  const getTagCounts = () => {
    if (!visualScript) return { chars: 0, locs: 0, props: 0 };
    const allTags = new Set<string>();
    visualScript.scenes?.forEach(scene => {
      scene.frames?.forEach(frame => {
        const tags = frame.prompt?.match(/\[(CHAR_|LOC_|PROP_)[A-Z0-9_]+\]/g) || [];
        tags.forEach(t => allTags.add(t));
      });
    });
    return {
      chars: [...allTags].filter(t => t.includes('CHAR_')).length,
      locs: [...allTags].filter(t => t.includes('LOC_')).length,
      props: [...allTags].filter(t => t.includes('PROP_')).length,
    };
  };

  const tagCounts = getTagCounts();
  const selectedModelData = models.find(m => m.key === selectedModel);
  const estMinutes = visualScript ? Math.ceil((visualScript.total_frames * 20) / 60) : 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] max-h-[80vh] bg-gradient-to-br from-[#0a1f0a] via-[#0d0d0d] to-[#0a0a0a] border border-[#39ff14]/30 rounded-lg shadow-xl shadow-[#39ff14]/10 z-50 flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Generate storyboard images from your visual script using AI image generation.
            </Dialog.Description>
          </VisuallyHidden.Root>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary flex items-center gap-2">
              <ImageIcon className="w-5 h-5" /> Generate Storyboard
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {!visualScript ? (
              <div className="text-center py-8">
                <p className="text-gl-text-muted mb-2">No visual script found</p>
                <p className="text-sm text-gl-text-muted">Run the Director pipeline first.</p>
              </div>
            ) : (
              <>
                {/* Brief */}
                <div className="bg-gl-bg-medium rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gl-text-secondary mb-2">📋 Generation Brief</h3>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-gl-accent">{visualScript.total_frames}</span>
                    <span className="text-gl-text-muted">frames across {visualScript.total_scenes} scenes</span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    {tagCounts.chars > 0 && <span className="text-xs bg-gl-bg-dark px-2 py-1 rounded">👤 {tagCounts.chars} characters</span>}
                    {tagCounts.locs > 0 && <span className="text-xs bg-gl-bg-dark px-2 py-1 rounded">📍 {tagCounts.locs} locations</span>}
                    {tagCounts.props > 0 && <span className="text-xs bg-gl-bg-dark px-2 py-1 rounded">🎭 {tagCounts.props} props</span>}
                  </div>
                </div>

                {/* Model Selection */}
                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">🤖 Image Generation Model</label>
                  <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 bg-[#2a2a2a] border border-gl-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100">
                    {models.map(m => <option key={m.key} value={m.key} className="bg-[#2a2a2a] text-gray-100">{m.display_name} ({m.provider})</option>)}
                  </select>
                  {selectedModelData && (
                    <p className="text-xs text-gl-text-muted mt-1">{selectedModelData.description}</p>
                  )}
                </div>

                {/* Estimate */}
                <div className="bg-gl-bg-light rounded p-3">
                  <p className="text-sm text-gl-text-secondary">⏱️ Estimated time: {estMinutes}-{estMinutes * 2} minutes</p>
                </div>

                {/* Progress */}
                {(isRunning || logs.length > 0) && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gl-text-secondary">Progress</span>
                      <span className="text-gl-text-primary">{Math.round(progress * 100)}%</span>
                    </div>
                    <div className="h-2 bg-gl-bg-medium rounded-full overflow-hidden mb-3">
                      <div className="h-full bg-gl-success transition-all" style={{ width: `${progress * 100}%` }} />
                    </div>
                    <div className="bg-gl-bg-medium rounded p-3 h-32 overflow-y-auto font-mono text-xs">
                      {logs.map((log, i) => <div key={i} className="text-gl-text-secondary">{log}</div>)}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-gl-border">
            <button
              onClick={async () => {
                // If running, send cancel request to backend
                if (isRunning && backendPipelineId) {
                  try {
                    await fetchAPI(`/api/pipelines/cancel/${backendPipelineId}`, { method: 'POST' });
                    addProcessLog(processId, 'Cancellation requested...', 'warning');
                  } catch (e) {
                    console.error('Cancel request failed:', e);
                  }
                }
                onOpenChange(false);
              }}
              className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary"
            >
              {isRunning ? 'Stop & Close' : 'Cancel'}
            </button>
            <button onClick={handleGenerate} disabled={isRunning || !visualScript}
              className="px-4 py-2 text-sm bg-gl-success hover:bg-gl-success/80 rounded text-white flex items-center gap-2 disabled:opacity-50">
              {isRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Play className="w-4 h-4" /> Continue</>}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

