'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { X, Play, Loader2 } from 'lucide-react';
import { useStore, useAppStore } from '@/lib/store';
import { fetchAPI } from '@/lib/utils';

interface WriterModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface PitchData {
  title: string;
  logline: string;
  genre: string;
  synopsis: string;
  characters: string;
  locations: string;
}

interface StyleData {
  visual_style: string;
  style_notes: string;
}

interface Preset {
  key: string;
  name: string;
  total_words: number;
  scenes: number;
  shots: number;
}

const VISUAL_STYLES = [
  { key: 'live_action', name: 'Live Action' },
  { key: 'anime', name: 'Anime' },
  { key: 'animation_2d', name: '2D Animation' },
  { key: 'animation_3d', name: '3D Animation' },
  { key: 'mixed_reality', name: 'Mixed Reality' },
];

const LLM_OPTIONS = [
  { key: 'claude-haiku-4.5', name: 'Claude Haiku 4.5' },
  { key: 'claude-opus-4.5', name: 'Claude Opus 4.5' },
  { key: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { key: 'gemini-3-pro', name: 'Gemini 3 Pro' },
  { key: 'grok-4', name: 'Grok 4' },
];

export function WriterModal({ open, onOpenChange }: WriterModalProps) {
  const { projectPath } = useStore();
  const { addPipelineProcess, updatePipelineProcess, addProcessLog, setWorkspaceMode } = useAppStore();
  const [activeTab, setActiveTab] = useState('pitch');
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  
  // Form state
  const [pitch, setPitch] = useState<PitchData>({
    title: '', logline: '', genre: '', synopsis: '', characters: '', locations: ''
  });
  const [selectedPreset, setSelectedPreset] = useState('standard');
  const [selectedLLM, setSelectedLLM] = useState('claude-haiku-4.5');
  const [visualStyle, setVisualStyle] = useState('live_action');
  const [styleNotes, setStyleNotes] = useState('');

  // Load data when modal opens
  useEffect(() => {
    if (open && projectPath) {
      loadPitchData();
      loadStyleData();
      loadPresets();
    }
  }, [open, projectPath]);

  const loadPitchData = async () => {
    try {
      const data = await fetchAPI<PitchData>(`/api/writer/${encodeURIComponent(projectPath)}/pitch`);
      setPitch(data);
    } catch (e) { console.error('Failed to load pitch:', e); }
  };

  const loadStyleData = async () => {
    try {
      const data = await fetchAPI<{ visual_style?: string; style_notes?: string }>(`/api/writer/${encodeURIComponent(projectPath)}/style`);
      setVisualStyle(data.visual_style || 'live_action');
      setStyleNotes(data.style_notes || '');
    } catch (e) { console.error('Failed to load style:', e); }
  };

  const loadPresets = async () => {
    try {
      const data = await fetchAPI<{ presets?: Preset[] }>('/api/writer/presets');
      setPresets(data.presets || []);
    } catch (e) { console.error('Failed to load presets:', e); }
  };

  const handleRun = async () => {
    if (!projectPath) return;
    setIsRunning(true);
    setProgress(0);
    setLogs([]);

    // Create a new process in the global store
    const processId = `writer-${Date.now()}`;
    setCurrentProcessId(processId);
    addPipelineProcess({
      id: processId,
      name: `Writer: ${pitch.title || 'Untitled'}`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      addProcessLog(processId, 'Starting Writer pipeline...', 'info');
      updatePipelineProcess(processId, { status: 'running' });

      const response = await fetchAPI<{ pipeline_id?: string }>('/api/writer/run', {
        method: 'POST',
        body: JSON.stringify({
          project_path: projectPath,
          llm: selectedLLM,
          media_type: selectedPreset,
          visual_style: visualStyle,
          style_notes: styleNotes,
          pitch: pitch
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
          stage?: string;
          current_stage?: string;
          stages?: Array<{ name: string; status: string; message?: string }>;
        }>(`/api/writer/status/${pipelineId}`);

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
          addProcessLog(processId, 'Writer pipeline completed successfully!', 'success');
          updatePipelineProcess(processId, {
            status: 'complete',
            progress: 1,
            endTime: new Date(),
            currentStage: undefined
          });
          setIsRunning(false);
        } else if (status.status === 'failed') {
          addProcessLog(processId, 'Writer pipeline failed', 'error');
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

  const selectedPresetData = presets.find(p => p.key === selectedPreset);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] max-h-[85vh] bg-gradient-to-br from-[#0a1f0a] via-[#0d0d0d] to-[#0a0a0a] border border-[#39ff14]/30 rounded-lg shadow-xl shadow-[#39ff14]/10 z-50 flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Configure and run the Writer pipeline to generate a script from your pitch.
            </Dialog.Description>
          </VisuallyHidden.Root>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary">
              ✍️ Writer Pipeline
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Tabs */}
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
            <Tabs.List className="flex border-b border-gl-border px-6">
              <Tabs.Trigger value="pitch" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                Pitch
              </Tabs.Trigger>
              <Tabs.Trigger value="config" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                Configuration
              </Tabs.Trigger>
              <Tabs.Trigger value="progress" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                Progress
              </Tabs.Trigger>
            </Tabs.List>

            {/* Pitch Tab */}
            <Tabs.Content value="pitch" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Title</label>
                <input type="text" value={pitch.title} onChange={e => setPitch({...pitch, title: e.target.value})}
                  className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="Project Title" />
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Logline</label>
                <input type="text" value={pitch.logline} onChange={e => setPitch({...pitch, logline: e.target.value})}
                  className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="One sentence summary" />
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Genre</label>
                <input type="text" value={pitch.genre} onChange={e => setPitch({...pitch, genre: e.target.value})}
                  className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="Drama, Action, Thriller" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">Characters (optional)</label>
                  <input type="text" value={pitch.characters} onChange={e => setPitch({...pitch, characters: e.target.value})}
                    className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="Mei, Lin, The General" />
                </div>
                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">Locations (optional)</label>
                  <input type="text" value={pitch.locations} onChange={e => setPitch({...pitch, locations: e.target.value})}
                    className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="Palace, Market, Temple" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Synopsis</label>
                <textarea value={pitch.synopsis} onChange={e => setPitch({...pitch, synopsis: e.target.value})} rows={6}
                  className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary resize-none" placeholder="Describe your story..." />
              </div>
            </Tabs.Content>

            {/* Config Tab */}
            <Tabs.Content value="config" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Project Size</label>
                <select value={selectedPreset} onChange={e => setSelectedPreset(e.target.value)}
                  className="w-full px-3 py-2 bg-[#2a2a2a] border border-gl-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100">
                  {presets.map(p => <option key={p.key} value={p.key} className="bg-[#2a2a2a] text-gray-100">{p.name}</option>)}
                </select>
                {selectedPresetData && (
                  <p className="text-xs text-gl-text-muted mt-1">
                    ~{selectedPresetData.total_words} words, {selectedPresetData.scenes} scenes, {selectedPresetData.shots} shots
                  </p>
                )}
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">AI Model</label>
                <select value={selectedLLM} onChange={e => setSelectedLLM(e.target.value)}
                  className="w-full px-3 py-2 bg-[#2a2a2a] border border-gl-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100">
                  {LLM_OPTIONS.map(l => <option key={l.key} value={l.key} className="bg-[#2a2a2a] text-gray-100">{l.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Visual Style</label>
                <select value={visualStyle} onChange={e => setVisualStyle(e.target.value)}
                  className="w-full px-3 py-2 bg-[#2a2a2a] border border-gl-border rounded text-gray-100 [&>option]:bg-[#2a2a2a] [&>option]:text-gray-100">
                  {VISUAL_STYLES.map(s => <option key={s.key} value={s.key} className="bg-[#2a2a2a] text-gray-100">{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gl-text-secondary mb-1">Style Notes</label>
                <textarea value={styleNotes} onChange={e => setStyleNotes(e.target.value)} rows={4}
                  className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary resize-none" placeholder="Additional style guidance..." />
              </div>
            </Tabs.Content>

            {/* Progress Tab */}
            <Tabs.Content value="progress" className="flex-1 overflow-y-auto p-6">
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gl-text-secondary">Progress</span>
                  <span className="text-gl-text-primary">{Math.round(progress * 100)}%</span>
                </div>
                <div className="h-2 bg-gl-bg-medium rounded-full overflow-hidden">
                  <div className="h-full bg-gl-accent transition-all" style={{ width: `${progress * 100}%` }} />
                </div>
              </div>
              <div className="bg-gl-bg-medium rounded p-4 h-64 overflow-y-auto font-mono text-sm">
                {logs.length === 0 ? (
                  <p className="text-gl-text-muted">Pipeline logs will appear here...</p>
                ) : (
                  logs.map((log, i) => <div key={i} className="text-gl-text-secondary">{log}</div>)
                )}
              </div>
            </Tabs.Content>
          </Tabs.Root>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-gl-border">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary">
              Cancel
            </button>
            <button onClick={handleRun} disabled={isRunning || !projectPath}
              className="px-4 py-2 text-sm bg-gl-accent hover:bg-gl-accent/80 rounded text-white flex items-center gap-2 disabled:opacity-50">
              {isRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Running...</> : <><Play className="w-4 h-4" /> Run Pipeline</>}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

