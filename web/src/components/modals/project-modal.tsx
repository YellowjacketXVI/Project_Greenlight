'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, FolderPlus, FolderOpen, Clock } from 'lucide-react';
import { useStore } from '@/lib/store';
import { fetchAPI } from '@/lib/utils';

interface NewProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface OpenProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TEMPLATES = [
  { key: 'blank', name: 'Blank' },
  { key: 'feature_film', name: 'Feature Film' },
  { key: 'series', name: 'Series' },
  { key: 'short_film', name: 'Short Film' },
  { key: 'music_video', name: 'Music Video' },
  { key: 'commercial', name: 'Commercial' },
];

const GENRES = ['Drama', 'Comedy', 'Action', 'Thriller', 'Horror', 'Sci-Fi', 'Fantasy', 'Romance', 'Documentary', 'Animation'];

export function NewProjectModal({ open, onOpenChange }: NewProjectModalProps) {
  const { setProjectPath } = useStore();
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [template, setTemplate] = useState('feature_film');
  const [logline, setLogline] = useState('');
  const [genre, setGenre] = useState('Drama');
  const [pitch, setPitch] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setIsCreating(true);

    try {
      const response = await fetchAPI<{ success: boolean; project_path?: string }>('/api/projects/create', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          location: location || 'projects',
          template,
          logline,
          genre,
          pitch
        })
      });

      if (response.project_path) {
        setProjectPath(response.project_path);
        onOpenChange(false);
      }
    } catch (e) {
      console.error('Failed to create project:', e);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] max-h-[80vh] bg-gl-bg-dark rounded-lg shadow-xl z-50 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary flex items-center gap-2">
              <FolderPlus className="w-5 h-5" /> Create New Project
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <div>
              <label className="block text-sm text-gl-text-secondary mb-1">Project Name *</label>
              <input type="text" value={name} onChange={e => setName(e.target.value)}
                className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="My Storyboard Project" />
            </div>

            <div>
              <label className="block text-sm text-gl-text-secondary mb-1">Location</label>
              <input type="text" value={location} onChange={e => setLocation(e.target.value)}
                className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="projects (default)" />
            </div>

            <div>
              <label className="block text-sm text-gl-text-secondary mb-1">Template</label>
              <select value={template} onChange={e => setTemplate(e.target.value)}
                className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary">
                {TEMPLATES.map(t => <option key={t.key} value={t.key}>{t.name}</option>)}
              </select>
            </div>

            <div className="pt-2 border-t border-gl-border">
              <h3 className="text-sm font-medium text-gl-accent mb-3">📝 Story & Pitch</h3>
              
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">Logline</label>
                  <input type="text" value={logline} onChange={e => setLogline(e.target.value)}
                    className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary" placeholder="A [protagonist] must [goal] before [stakes]..." />
                </div>

                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">Genre</label>
                  <select value={genre} onChange={e => setGenre(e.target.value)}
                    className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary">
                    {GENRES.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-gl-text-secondary mb-1">Synopsis / Pitch</label>
                  <textarea value={pitch} onChange={e => setPitch(e.target.value)} rows={4}
                    className="w-full px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary resize-none" placeholder="Describe your story idea..." />
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-gl-border">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary">
              Cancel
            </button>
            <button onClick={handleCreate} disabled={!name.trim() || isCreating}
              className="px-4 py-2 text-sm bg-gl-accent hover:bg-gl-accent/80 rounded text-white disabled:opacity-50">
              Create Project
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function OpenProjectModal({ open, onOpenChange }: OpenProjectModalProps) {
  const { setProjectPath } = useStore();
  const [recentProjects, setRecentProjects] = useState<string[]>([]);
  const [browsePath, setBrowsePath] = useState('');

  useEffect(() => {
    if (open) {
      loadRecentProjects();
    }
  }, [open]);

  const loadRecentProjects = async () => {
    try {
      const data = await fetchAPI<{ projects?: string[] }>('/api/projects/recent');
      setRecentProjects(data.projects || []);
    } catch (e) {
      console.error('Failed to load recent projects:', e);
    }
  };

  const handleOpen = (path: string) => {
    setProjectPath(path);
    onOpenChange(false);
  };

  const handleBrowse = () => {
    if (browsePath.trim()) {
      handleOpen(browsePath.trim());
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[450px] max-h-[60vh] bg-gl-bg-dark rounded-lg shadow-xl z-50 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary flex items-center gap-2">
              <FolderOpen className="w-5 h-5" /> Open Project
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {/* Recent Projects */}
            <div>
              <h3 className="text-sm font-medium text-gl-text-secondary mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4" /> Recent Projects
              </h3>
              <div className="bg-gl-bg-medium rounded-lg max-h-40 overflow-y-auto">
                {recentProjects.length > 0 ? (
                  recentProjects.map((project, i) => (
                    <button key={i} onClick={() => handleOpen(project)}
                      className="w-full px-4 py-2 text-left text-sm text-gl-text-primary hover:bg-gl-bg-hover first:rounded-t-lg last:rounded-b-lg">
                      {project}
                    </button>
                  ))
                ) : (
                  <p className="px-4 py-3 text-sm text-gl-text-muted">No recent projects</p>
                )}
              </div>
            </div>

            {/* Browse */}
            <div>
              <h3 className="text-sm font-medium text-gl-text-secondary mb-2">Browse for Project</h3>
              <div className="flex gap-2">
                <input type="text" value={browsePath} onChange={e => setBrowsePath(e.target.value)}
                  className="flex-1 px-3 py-2 bg-gl-bg-medium border border-gl-border rounded text-gl-text-primary text-sm" placeholder="Enter project path..." />
                <button onClick={handleBrowse} disabled={!browsePath.trim()}
                  className="px-4 py-2 text-sm bg-gl-accent hover:bg-gl-accent/80 rounded text-white disabled:opacity-50">
                  Open
                </button>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end px-6 py-4 border-t border-gl-border">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary">
              Cancel
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

