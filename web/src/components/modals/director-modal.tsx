'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { X, Play, Loader2, Film } from 'lucide-react';
import { useStore, useAppStore } from '@/lib/store';
import { fetchAPI } from '@/lib/utils';

interface DirectorModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface SceneData {
  number: number;
  title: string;
}

const LLM_OPTIONS = [
  { key: 'claude-opus-4.5', name: 'Claude Opus 4.5' },
  { key: 'claude-haiku-4.5', name: 'Claude Haiku 4.5' },
  { key: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { key: 'gemini-3-pro', name: 'Gemini 3 Pro' },
  { key: 'grok-4', name: 'Grok 4' },
];

export function DirectorModal({ open, onOpenChange }: DirectorModalProps) {
  const { projectPath } = useStore();
  const { addPipelineProcess, updatePipelineProcess, addProcessLog, setWorkspaceMode } = useAppStore();
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [scenes, setScenes] = useState<SceneData[]>([]);
  const [scriptExists, setScriptExists] = useState(false);
  const [selectedLLM, setSelectedLLM] = useState('claude-opus-4.5');

  useEffect(() => {
    if (open && projectPath) {
      loadScriptData();
    }
  }, [open, projectPath]);

  const loadScriptData = async () => {
    try {
      const data = await fetchAPI<{ exists: boolean; scenes: SceneData[] }>(`/api/director/${encodeURIComponent(projectPath)}/script`);
      setScriptExists(data.exists);
      setScenes(data.scenes || []);
    } catch (e) {
      console.error('Failed to load script:', e);
      setScriptExists(false);
    }
  };

  const handleRun = async () => {
    if (!projectPath || !scriptExists) return;
    setIsRunning(true);
    setProgress(0);
    setLogs([]);

    // Create a new process in the global store
    const processId = `director-${Date.now()}`;
    addPipelineProcess({
      id: processId,
      name: `Director: ${scenes.length} scenes`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      addProcessLog(processId, 'Starting Director pipeline...', 'info');
      updatePipelineProcess(processId, { status: 'running' });

      const response = await fetchAPI<{ pipeline_id?: string }>('/api/director/run', {
        method: 'POST',
        body: JSON.stringify({
          project_path: projectPath,
          llm: selectedLLM
        })
      });

      if (response.pipeline_id) {
        addProcessLog(processId, `Pipeline started with ID: ${response.pipeline_id}`, 'info');
        pollStatus(response.pipeline_id, processId);
      }
    } catch (e) {
      addProcessLog(processId, `Error: ${e}`, 'error');
      updatePipelineProcess(processId, { status: 'error', error: String(e), endTime: new Date() });
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
        }>(`/api/director/status/${pipelineId}`);

        setProgress(status.progress || 0);

        // Build update object with all new fields
        const updates: Record<string, unknown> = {
          progress: status.progress || 0,
        };

        // Update current stage
        if (status.current_stage !== undefined) {
          updates.currentStage = status.current_stage;
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
          addProcessLog(processId, 'Director pipeline completed successfully!', 'success');
          updatePipelineProcess(processId, {
            status: 'complete',
            progress: 1,
            endTime: new Date(),
            currentStage: undefined
          });
          setIsRunning(false);
        } else if (status.status === 'failed') {
          addProcessLog(processId, 'Director pipeline failed', 'error');
          updatePipelineProcess(processId, { status: 'error', endTime: new Date() });
          setIsRunning(false);
        } else {
          setTimeout(poll, 1000);
        }
      } catch (e) {
        addProcessLog(processId, `Polling error: ${e}`, 'error');
        updatePipelineProcess(processId, { status: 'error', error: String(e), endTime: new Date() });
        setIsRunning(false);
      }
    };
    poll();
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] max-h-[80vh] bg-gradient-to-br from-[#0a1f0a] via-[#0d0d0d] to-[#0a0a0a] border border-[#39ff14]/30 rounded-lg shadow-xl shadow-[#39ff14]/10 z-50 flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Configure and run the Director pipeline to generate visual scripts from your scenes.
            </Dialog.Description>
          </VisuallyHidden.Root>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary flex items-center gap-2">
              <Film className="w-5 h-5" /> Director Pipeline
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {!scriptExists ? (
              <div className="text-center py-8">
                <p className="text-gl-text-muted mb-2">No script found</p>
                <p className="text-sm text-gl-text-muted">Run the Writer pipeline first to generate a script.</p>
              </div>
            ) : (
              <>
                {/* Script Summary */}
                <div className="bg-gl-bg-medium rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gl-text-primary mb-2">Script Summary</h3>
                  <p className="text-2xl font-bold text-gl-accent">{scenes.length}</p>
                  <p className="text-sm text-gl-text-muted">scenes to process</p>
                </div>

                {/* Scene List */}
                <div>
                  <h3 className="text-sm font-medium text-gl-text-primary mb-2">Scenes</h3>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {scenes.map(scene => (
                      <div key={scene.number} className="bg-gl-bg-medium rounded p-3">
                        <div className="flex justify-between items-start">
                          <span className="text-sm font-medium text-gl-text-primary">
                            Scene {scene.number}: {scene.title}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* LLM Selection */}
                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">AI Model</label>
                  <select value={selectedLLM} onChange={e => setSelectedLLM(e.target.value)}
                    className="w-full px-3 py-2 bg-[#2a2a2a] border border-gl-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100">
                    {LLM_OPTIONS.map(l => <option key={l.key} value={l.key} className="bg-[#2a2a2a] text-gray-100">{l.name}</option>)}
                  </select>
                </div>

                {/* Progress */}
                {(isRunning || logs.length > 0) && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gl-text-secondary">Progress</span>
                      <span className="text-gl-text-primary">{Math.round(progress * 100)}%</span>
                    </div>
                    <div className="h-2 bg-gl-bg-medium rounded-full overflow-hidden mb-3">
                      <div className="h-full bg-gl-accent transition-all" style={{ width: `${progress * 100}%` }} />
                    </div>
                    <div className="bg-gl-bg-medium rounded p-3 h-32 overflow-y-auto font-mono text-xs">
                      {logs.map((log, i) => <div key={`log-${i}`} className="text-gl-text-secondary">{log}</div>)}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-gl-border">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary">
              Cancel
            </button>
            <button onClick={handleRun} disabled={isRunning || !scriptExists}
              className="px-4 py-2 text-sm bg-gl-accent hover:bg-gl-accent/80 rounded text-white flex items-center gap-2 disabled:opacity-50">
              {isRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Running...</> : <><Play className="w-4 h-4" /> Run Director</>}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

