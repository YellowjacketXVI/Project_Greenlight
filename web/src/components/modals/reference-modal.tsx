'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
import { X, Star, FileImage, Loader2, RefreshCw, Upload, Sparkles } from 'lucide-react';
import { fetchAPI, cn, API_BASE_URL } from '@/lib/utils';
import { useAppStore } from '@/lib/store';

interface ReferenceImage {
  path: string;
  name: string;
  isKey: boolean;
}

interface ReferenceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tag: string;
  name: string;
  tagType: string;
  projectPath: string;
  onRefresh?: () => void;
}

const MODEL_OPTIONS = [
  { key: 'nano_banana', name: 'Nano Banana (Basic)' },
  { key: 'nano_banana_pro', name: 'Nano Banana Pro (Best)' },
  { key: 'seedream', name: 'Seedream 4.5 (Fast)' },
];

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

export function ReferenceModal({
  open,
  onOpenChange,
  tag,
  name,
  tagType,
  projectPath,
  onRefresh
}: ReferenceModalProps) {
  const { addPipelineProcess, updatePipelineProcess, addProcessLog, setWorkspaceMode } = useAppStore();
  const [images, setImages] = useState<ReferenceImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('nano_banana_pro');
  const [generatingSheet, setGeneratingSheet] = useState<string | null>(null);
  const [settingKey, setSettingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadReferences = async () => {
    if (!projectPath || !tag) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAPI<{ images: ReferenceImage[] }>(
        `/api/projects/${encodeURIComponent(projectPath)}/references/${encodeURIComponent(tag)}`
      );
      setImages(data.images || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load references');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadReferences();
    }
  }, [open, projectPath, tag]);

  const uploadFile = async (file: File) => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Invalid file type. Allowed: PNG, JPG, JPEG, WebP');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(
        `${API_BASE_URL}/api/projects/${encodeURIComponent(projectPath)}/references/${encodeURIComponent(tag)}/upload`,
        {
          method: 'POST',
          body: formData,
        }
      );

      const result = await response.json();

      if (result.success) {
        await loadReferences();
        onRefresh?.();
      } else {
        setError(result.error || 'Failed to upload image');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
  }, [projectPath, tag]);

  const handleSetKeyReference = async (imagePath: string) => {
    setSettingKey(imagePath);
    try {
      await fetchAPI(`/api/projects/${encodeURIComponent(projectPath)}/references/${encodeURIComponent(tag)}/set-key`, {
        method: 'POST',
        body: JSON.stringify({ imagePath })
      });
      await loadReferences();
      onRefresh?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set key reference');
    } finally {
      setSettingKey(null);
    }
  };

  const handleGenerateSheet = async (imagePath: string) => {
    // Create a local process ID for tracking
    const localProcessId = `sheet-${tag}-${Date.now()}`;
    const modelLabel = MODEL_OPTIONS.find(m => m.key === selectedModel)?.name || selectedModel;

    addPipelineProcess({
      id: localProcessId,
      name: `Generate ${tagType} Sheet: ${name}`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      addProcessLog(localProcessId, `Starting ${tagType} sheet generation for ${tag}...`, 'info');
      addProcessLog(localProcessId, `Using model: ${modelLabel}`, 'info');
      updatePipelineProcess(localProcessId, { status: 'running' });

      const result = await fetchAPI<{ success: boolean; message: string; process_id?: string }>(
        `/api/projects/${encodeURIComponent(projectPath)}/references/${encodeURIComponent(tag)}/generate-sheet`,
        {
          method: 'POST',
          body: JSON.stringify({ imagePath, model: selectedModel })
        }
      );

      if (result.success && result.process_id) {
        // Store backend ID for cancellation
        updatePipelineProcess(localProcessId, { backendId: result.process_id });
        addProcessLog(localProcessId, `Process started with ID: ${result.process_id}`, 'info');
        // Start polling for status updates
        pollSheetStatus(result.process_id, localProcessId);
      } else {
        addProcessLog(localProcessId, result.message || 'Failed to start generation', 'error');
        updatePipelineProcess(localProcessId, { status: 'error', endTime: new Date() });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      addProcessLog(localProcessId, `Error: ${errorMsg}`, 'error');
      updatePipelineProcess(localProcessId, { status: 'error', error: errorMsg, endTime: new Date() });
    }
  };

  const pollSheetStatus = async (backendProcessId: string, localProcessId: string) => {
    let lastLogCount = 0;

    const poll = async () => {
      try {
        const status = await fetchAPI<{
          status: string;
          progress: number;
          logs: string[];
          output_path?: string;
          error?: string;
        }>(`/api/projects/${encodeURIComponent(projectPath)}/image-generation/status/${backendProcessId}`);

        // Update progress
        updatePipelineProcess(localProcessId, { progress: status.progress });

        // Add only new logs (avoid duplicates)
        if (status.logs && status.logs.length > lastLogCount) {
          const newLogs = status.logs.slice(lastLogCount);
          newLogs.forEach((log) => {
            const type = log.includes('❌') || log.includes('Error') || log.includes('Failed') ? 'error' :
                        log.includes('✅') || log.includes('✓') || log.includes('Complete') ? 'success' :
                        log.includes('⚠') ? 'warning' : 'info';
            addProcessLog(localProcessId, log, type);
          });
          lastLogCount = status.logs.length;
        }

        // Check completion status
        if (status.status === 'complete') {
          updatePipelineProcess(localProcessId, { status: 'complete', progress: 1, endTime: new Date() });
          onRefresh?.();
        } else if (status.status === 'failed') {
          addProcessLog(localProcessId, status.error || 'Generation failed', 'error');
          updatePipelineProcess(localProcessId, { status: 'error', error: status.error, endTime: new Date() });
        } else if (status.status === 'cancelled') {
          updatePipelineProcess(localProcessId, { status: 'cancelled', endTime: new Date() });
        } else {
          // Still running, poll again
          setTimeout(poll, 1000);
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        addProcessLog(localProcessId, `Polling error: ${errorMsg}`, 'error');
        updatePipelineProcess(localProcessId, { status: 'error', error: errorMsg, endTime: new Date() });
      }
    };

    poll();
  };

  const handleGenerateReference = async () => {
    // Create a local process ID for tracking
    const localProcessId = `ref-${tag}-${Date.now()}`;
    const modelLabel = MODEL_OPTIONS.find(m => m.key === selectedModel)?.name || selectedModel;

    addPipelineProcess({
      id: localProcessId,
      name: `Generate Reference: ${name}`,
      status: 'initializing',
      progress: 0,
      startTime: new Date(),
    });

    // Close modal and switch to progress view
    onOpenChange(false);
    setWorkspaceMode('progress');

    try {
      addProcessLog(localProcessId, `Starting ${tagType} reference generation for ${tag}...`, 'info');
      addProcessLog(localProcessId, `Using model: ${modelLabel}`, 'info');
      updatePipelineProcess(localProcessId, { status: 'running' });

      const result = await fetchAPI<{ success: boolean; message: string; process_id?: string }>(
        `/api/projects/${encodeURIComponent(projectPath)}/references/${encodeURIComponent(tag)}/generate`,
        {
          method: 'POST',
          body: JSON.stringify({ model: selectedModel })
        }
      );

      if (result.success && result.process_id) {
        // Store backend ID for cancellation
        updatePipelineProcess(localProcessId, { backendId: result.process_id });
        addProcessLog(localProcessId, `Process started with ID: ${result.process_id}`, 'info');
        // Start polling for status updates (reuse the same polling function)
        pollSheetStatus(result.process_id, localProcessId);
      } else {
        addProcessLog(localProcessId, result.message || 'Failed to start generation', 'error');
        updatePipelineProcess(localProcessId, { status: 'error', endTime: new Date() });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      addProcessLog(localProcessId, `Error: ${errorMsg}`, 'error');
      updatePipelineProcess(localProcessId, { status: 'error', error: errorMsg, endTime: new Date() });
    }
  };

  const getTagColor = () => {
    if (tagType === 'character') return 'text-blue-400 bg-blue-500/10';
    if (tagType === 'location') return 'text-green-400 bg-green-500/10';
    if (tagType === 'prop') return 'text-orange-400 bg-orange-500/10';
    return 'text-primary bg-primary/10';
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-card border border-border rounded-lg shadow-xl z-50 w-[90vw] max-w-4xl max-h-[92vh] flex flex-col">
          <VisuallyHidden.Root>
            <Dialog.Description>
              Manage reference images for {name}
            </Dialog.Description>
          </VisuallyHidden.Root>
          
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <div className="flex items-center gap-3">
              <span className={cn("px-2 py-1 text-xs font-mono rounded", getTagColor())}>
                [{tag}]
              </span>
              <Dialog.Title className="text-lg font-semibold">{name}</Dialog.Title>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={loadReferences}
                className="p-2 hover:bg-secondary rounded transition-colors"
                title="Refresh"
              >
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              </button>
              <Dialog.Close className="p-2 hover:bg-secondary rounded transition-colors">
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>
          </div>

          {/* Content */}
          <div
            className="flex-1 overflow-hidden flex flex-col p-4"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {/* Model Selection & Upload */}
            <div className="flex items-center justify-between gap-4 mb-4 pb-4 border-b border-border">
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted-foreground">Generation Model:</span>
                <div className="flex gap-2">
                  {MODEL_OPTIONS.map((model) => (
                    <button
                      key={model.key}
                      onClick={() => setSelectedModel(model.key)}
                      className={cn(
                        "px-3 py-1.5 text-sm rounded transition-colors",
                        selectedModel === model.key
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary hover:bg-secondary/80"
                      )}
                    >
                      {model.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Generate & Upload Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerateReference}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-primary hover:bg-primary/90 text-primary-foreground rounded transition-colors"
                >
                  <Sparkles className="h-4 w-4" />
                  Generate Reference
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg,image/webp"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-secondary hover:bg-secondary/80 rounded transition-colors"
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  Upload
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded text-destructive text-sm">
                {error}
              </div>
            )}

            {/* Drag Overlay */}
            {isDragging && (
              <div className="absolute inset-4 border-2 border-dashed border-primary bg-primary/10 rounded-lg flex items-center justify-center z-10 pointer-events-none">
                <div className="text-center">
                  <Upload className="h-12 w-12 text-primary mx-auto mb-2" />
                  <p className="text-lg font-medium text-primary">Drop image here</p>
                  <p className="text-sm text-muted-foreground">PNG, JPG, JPEG, or WebP</p>
                </div>
              </div>
            )}

            {/* Images Grid */}
            <div className="flex-1 overflow-auto">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : images.length === 0 ? (
                <div
                  className="flex flex-col items-center justify-center h-full text-center cursor-pointer hover:bg-secondary/50 rounded-lg transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="font-medium">No Reference Images</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    Drag & drop an image here, or click to upload
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Or generate references from the World Bible panel
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {images.map((image) => (
                    <div
                      key={image.path}
                      className={cn(
                        "bg-secondary rounded-lg overflow-hidden border-2 transition-colors",
                        image.isKey ? "border-yellow-500" : "border-transparent hover:border-primary/50"
                      )}
                    >
                      {/* Image */}
                      <div className="aspect-square relative bg-black">
                        <img
                          src={`${API_BASE_URL}/api/images/${encodeURIComponent(image.path)}`}
                          alt={image.name}
                          className="w-full h-full object-contain"
                        />
                        {image.isKey && (
                          <div className="absolute top-2 left-2 px-2 py-1 bg-yellow-500 text-black text-xs font-bold rounded">
                            ⭐ KEY
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="p-2 space-y-2">
                        <p className="text-xs text-muted-foreground truncate" title={image.name}>
                          {image.name}
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSetKeyReference(image.path)}
                            disabled={settingKey !== null || image.isKey}
                            className={cn(
                              "flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs rounded transition-colors",
                              image.isKey
                                ? "bg-yellow-500/20 text-yellow-500 cursor-default"
                                : "bg-secondary hover:bg-yellow-500/20 hover:text-yellow-500"
                            )}
                          >
                            {settingKey === image.path ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Star className={cn("h-3 w-3", image.isKey && "fill-current")} />
                            )}
                            {image.isKey ? 'Key' : 'Set Key'}
                          </button>
                          {(tagType === 'character' || tagType === 'prop') && (
                            <button
                              onClick={() => handleGenerateSheet(image.path)}
                              disabled={generatingSheet !== null}
                              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-primary/10 hover:bg-primary/20 text-primary rounded transition-colors"
                            >
                              {generatingSheet === image.path ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <FileImage className="h-3 w-3" />
                              )}
                              Sheet
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

