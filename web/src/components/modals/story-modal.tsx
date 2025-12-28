'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { X, Play, Loader2, Image, ImageOff } from 'lucide-react';
import { useStore, useAppStore } from '@/lib/store';
import { fetchAPI } from '@/lib/utils';

interface StoryModalProps {
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

const VISUAL_STYLES = [
  { key: 'live_action', name: 'Live Action' },
  { key: 'anime', name: 'Anime' },
  { key: 'animation_2d', name: '2D Animation' },
  { key: 'animation_3d', name: '3D Animation' },
  { key: 'mixed_reality', name: 'Mixed Reality' },
];

const PROJECT_SIZES = [
  { key: 'micro', name: 'Micro', scenes: 3, framesPerScene: 4, totalFrames: '9-12', duration: '~1 min', description: 'Quick concept or scene test' },
  { key: 'short', name: 'Short', scenes: 8, framesPerScene: 5, totalFrames: '32-40', duration: '~3-5 min', description: 'Short film or music video' },
  { key: 'medium', name: 'Medium', scenes: 15, framesPerScene: 6, totalFrames: '75-90', duration: '~10-15 min', description: 'Full short film or episode' },
  { key: 'long', name: 'Long', scenes: 30, framesPerScene: 6, totalFrames: '150-180', duration: '~25-30 min', description: 'Feature-length or pilot episode' },
];

const IMAGE_MODELS = [
  { key: 'flux_2_pro', name: 'Flux 2 Pro' },
  { key: 'seedream', name: 'SeeDream 4.5' },
  { key: 'nano_banana_pro', name: 'Nano Banana Pro' },
];

export function StoryModal({ open, onOpenChange }: StoryModalProps) {
  const { projectPath } = useStore();
  const {
    addPipelineProcess,
    updatePipelineProcess,
    addProcessLog,
    setWorkspaceMode,
    setStoryPhaseComplete
  } = useAppStore();

  const [activeTab, setActiveTab] = useState('pitch');
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);

  // Form state
  const [pitch, setPitch] = useState<PitchData>({
    title: '', logline: '', genre: '', synopsis: '', characters: '', locations: ''
  });
  const [projectSize, setProjectSize] = useState('short');
  const [visualStyle, setVisualStyle] = useState('live_action');
  const [styleNotes, setStyleNotes] = useState('');
  const [generateImages, setGenerateImages] = useState(true);
  const [imageModel, setImageModel] = useState('flux_2_pro');

  // Load data when modal opens
  useEffect(() => {
    if (open && projectPath) {
      loadPitchData();
      loadStyleData();
    }
  }, [open, projectPath]);

  const loadPitchData = async () => {
    try {
      const data = await fetchAPI<PitchData>(`/api/projects/${encodeURIComponent(projectPath)}/pitch-data`);
      setPitch(data);
    } catch (e) {
      console.error('Failed to load pitch:', e);
    }
  };

  const loadStyleData = async () => {
    try {
      const data = await fetchAPI<{ visual_style?: string; style_notes?: string }>(`/api/projects/${encodeURIComponent(projectPath)}/style-data`);
      setVisualStyle(data.visual_style || 'live_action');
      setStyleNotes(data.style_notes || '');
    } catch (e) {
      console.error('Failed to load style:', e);
    }
  };

  const handleRun = async () => {
    if (!projectPath) return;
    setIsRunning(true);
    setProgress(0);
    setLogs([]);

    // Create a new process in the global store
    const processId = `story-${Date.now()}`;
    setCurrentProcessId(processId);
    addPipelineProcess({
      id: processId,
      name: `Generate Story: ${pitch.title || 'Untitled'}`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      // First, save the pitch data to pitch.md before running pipeline
      addProcessLog(processId, 'Saving pitch data...', 'info');
      await fetchAPI(`/api/projects/${encodeURIComponent(projectPath)}/pitch-data`, {
        method: 'POST',
        body: JSON.stringify({
          title: pitch.title,
          logline: pitch.logline,
          genre: pitch.genre,
          synopsis: pitch.synopsis,
          characters: pitch.characters,
          locations: pitch.locations
        })
      });
      addProcessLog(processId, 'Pitch saved successfully', 'success');

      addProcessLog(processId, 'Starting Story Phase (Passes 1-5)...', 'info');
      updatePipelineProcess(processId, { status: 'running' });

      const response = await fetchAPI<{ pipeline_id?: string }>('/api/pipelines/story', {
        method: 'POST',
        body: JSON.stringify({
          project_path: projectPath,
          visual_style: visualStyle,
          style_notes: styleNotes,
          project_size: projectSize,
          generate_images: generateImages,
          image_model: imageModel,
          max_continuity_corrections: 1  // Single pass for speed
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
        }>(`/api/pipelines/status/${pipelineId}`);

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

        // Add only NEW logs to the process
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
          addProcessLog(processId, 'Story Phase completed successfully!', 'success');
          updatePipelineProcess(processId, {
            status: 'complete',
            progress: 1,
            endTime: new Date(),
            currentStage: undefined
          });
          // Mark story phase as complete to enable storyboard button
          setStoryPhaseComplete(true);
          setIsRunning(false);
        } else if (status.status === 'failed') {
          addProcessLog(processId, 'Story Phase failed', 'error');
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
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] max-h-[85vh] bg-gradient-to-br from-[#1a1a0a] via-[#0d0d0d] to-[#0a0a0a] border border-yellow-400/30 rounded-lg shadow-xl shadow-yellow-400/10 z-50 flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Configure and run the Story Phase to generate world, references, keyframes, and prompts.
            </Dialog.Description>
          </VisuallyHidden.Root>
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-yellow-400/20">
            <Dialog.Title className="text-xl font-semibold text-white">
              📖 Generate Story
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-yellow-400/10 rounded">
              <X className="w-5 h-5 text-gray-400" />
            </Dialog.Close>
          </div>

          {/* Tabs */}
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
            <Tabs.List className="flex border-b border-yellow-400/20 px-6">
              <Tabs.Trigger value="pitch" className="px-4 py-2 text-sm data-[state=active]:text-yellow-400 data-[state=active]:border-b-2 data-[state=active]:border-yellow-400">
                Pitch
              </Tabs.Trigger>
              <Tabs.Trigger value="config" className="px-4 py-2 text-sm data-[state=active]:text-yellow-400 data-[state=active]:border-b-2 data-[state=active]:border-yellow-400">
                Configuration
              </Tabs.Trigger>
              <Tabs.Trigger value="progress" className="px-4 py-2 text-sm data-[state=active]:text-yellow-400 data-[state=active]:border-b-2 data-[state=active]:border-yellow-400">
                Progress
              </Tabs.Trigger>
            </Tabs.List>

            {/* Pitch Tab */}
            <Tabs.Content value="pitch" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Title</label>
                <input type="text" value={pitch.title} onChange={e => setPitch({...pitch, title: e.target.value})}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white focus:border-yellow-400/50 focus:outline-none" placeholder="Project Title" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Logline</label>
                <input type="text" value={pitch.logline} onChange={e => setPitch({...pitch, logline: e.target.value})}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white focus:border-yellow-400/50 focus:outline-none" placeholder="One sentence summary" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Genre</label>
                <input type="text" value={pitch.genre} onChange={e => setPitch({...pitch, genre: e.target.value})}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white focus:border-yellow-400/50 focus:outline-none" placeholder="Drama, Action, Thriller" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Characters (optional)</label>
                  <input type="text" value={pitch.characters} onChange={e => setPitch({...pitch, characters: e.target.value})}
                    className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white focus:border-yellow-400/50 focus:outline-none" placeholder="Mei, Lin, The General" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Locations (optional)</label>
                  <input type="text" value={pitch.locations} onChange={e => setPitch({...pitch, locations: e.target.value})}
                    className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white focus:border-yellow-400/50 focus:outline-none" placeholder="Palace, Market, Temple" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Synopsis</label>
                <textarea value={pitch.synopsis} onChange={e => setPitch({...pitch, synopsis: e.target.value})} rows={6}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white resize-none focus:border-yellow-400/50 focus:outline-none" placeholder="Describe your story..." />
              </div>
            </Tabs.Content>

            {/* Config Tab */}
            <Tabs.Content value="config" className="flex-1 overflow-y-auto p-6 space-y-5">
              {/* Project Size Cards */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-3">Project Size</label>
                <div className="grid grid-cols-2 gap-3">
                  {PROJECT_SIZES.map(size => (
                    <button
                      key={size.key}
                      onClick={() => setProjectSize(size.key)}
                      className={`p-4 rounded-lg border text-left transition-all ${
                        projectSize === size.key
                          ? 'bg-yellow-400/10 border-yellow-400 ring-1 ring-yellow-400/50'
                          : 'bg-[#1a1a1a] border-yellow-400/20 hover:border-yellow-400/40'
                      }`}
                    >
                      <div className={`text-lg font-semibold mb-1 ${projectSize === size.key ? 'text-yellow-400' : 'text-white'}`}>
                        {size.name}
                      </div>
                      <div className="text-xs text-gray-400 space-y-0.5">
                        <div>{size.scenes} scenes × {size.framesPerScene} frames</div>
                        <div className="text-yellow-400/70">{size.totalFrames} total frames</div>
                        <div className="text-gray-500">{size.duration}</div>
                      </div>
                      <div className="text-xs text-gray-500 mt-2 italic">
                        {size.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Visual Style */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Visual Style</label>
                <div className="flex flex-wrap gap-2">
                  {VISUAL_STYLES.map(s => (
                    <button
                      key={s.key}
                      onClick={() => setVisualStyle(s.key)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        visualStyle === s.key
                          ? 'bg-yellow-400/20 text-yellow-400 border border-yellow-400'
                          : 'bg-[#1a1a1a] text-gray-300 border border-yellow-400/20 hover:border-yellow-400/40'
                      }`}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Style Notes */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Style Notes</label>
                <textarea value={styleNotes} onChange={e => setStyleNotes(e.target.value)} rows={2}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-yellow-400/20 rounded text-white resize-none focus:border-yellow-400/50 focus:outline-none text-sm" placeholder="Era, mood, cinematography references..." />
              </div>

              {/* Image Generation Options */}
              <div className="border-t border-yellow-400/20 pt-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <label className="text-sm font-medium text-gray-300">Generate Reference Images & Keyframes</label>
                    <p className="text-xs text-gray-500">Creates character refs, location refs, and key frames</p>
                  </div>
                  <button
                    onClick={() => setGenerateImages(!generateImages)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      generateImages
                        ? 'bg-yellow-400/20 text-yellow-400 border border-yellow-400/40'
                        : 'bg-gray-700/50 text-gray-400 border border-gray-600'
                    }`}
                  >
                    {generateImages ? <Image className="w-4 h-4" /> : <ImageOff className="w-4 h-4" />}
                    {generateImages ? 'Enabled' : 'Disabled'}
                  </button>
                </div>
                {generateImages && (
                  <div className="flex flex-wrap gap-2">
                    {IMAGE_MODELS.map(m => (
                      <button
                        key={m.key}
                        onClick={() => setImageModel(m.key)}
                        className={`px-3 py-1.5 rounded text-sm transition-all ${
                          imageModel === m.key
                            ? 'bg-yellow-400/20 text-yellow-400 border border-yellow-400'
                            : 'bg-[#1a1a1a] text-gray-400 border border-yellow-400/20 hover:border-yellow-400/40'
                        }`}
                      >
                        {m.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </Tabs.Content>

            {/* Progress Tab */}
            <Tabs.Content value="progress" className="flex-1 overflow-y-auto p-6">
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Progress</span>
                  <span className="text-white">{Math.round(progress * 100)}%</span>
                </div>
                <div className="h-2 bg-[#1a1a1a] rounded-full overflow-hidden">
                  <div className="h-full bg-yellow-400 transition-all" style={{ width: `${progress * 100}%` }} />
                </div>
              </div>
              <div className="bg-[#1a1a1a] rounded p-4 h-64 overflow-y-auto font-mono text-sm">
                {logs.length === 0 ? (
                  <p className="text-gray-500">Pipeline logs will appear here...</p>
                ) : (
                  logs.map((log, i) => <div key={i} className="text-gray-300">{log}</div>)
                )}
              </div>
            </Tabs.Content>
          </Tabs.Root>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-yellow-400/20">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-[#2a2a2a] hover:bg-[#3a3a3a] rounded text-white">
              Cancel
            </button>
            <button onClick={handleRun} disabled={isRunning || !projectPath}
              className="px-4 py-2 text-sm bg-yellow-400 hover:bg-yellow-500 rounded text-black font-medium flex items-center gap-2 disabled:opacity-50">
              {isRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Running...</> : <><Play className="w-4 h-4" /> Generate Story</>}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
