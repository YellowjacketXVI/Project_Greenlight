'use client';

import { useState, useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import { X, Save } from 'lucide-react';
import { fetchAPI } from '@/lib/utils';

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface Settings {
  llm: {
    anthropic_key: string;
    openai_key: string;
    google_key: string;
  };
  ui: {
    theme: string;
    font_size: number;
  };
  project: {
    default_llm: string;
    auto_save: boolean;
    auto_regen: boolean;
  };
}

const DEFAULT_SETTINGS: Settings = {
  llm: { anthropic_key: '', openai_key: '', google_key: '' },
  ui: { theme: 'dark', font_size: 13 },
  project: { default_llm: 'anthropic', auto_save: true, auto_regen: false }
};

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = async () => {
    try {
      const data = await fetchAPI<Partial<Settings>>('/api/settings');
      setSettings({ ...DEFAULT_SETTINGS, ...data });
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await fetchAPI<void>('/api/settings', {
        method: 'POST',
        body: JSON.stringify(settings)
      });
      onOpenChange(false);
    } catch (e) {
      console.error('Failed to save settings:', e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] max-h-[70vh] bg-gl-bg-dark rounded-lg shadow-xl z-50 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gl-border">
            <Dialog.Title className="text-xl font-semibold text-gl-text-primary">
              ⚙️ Settings
            </Dialog.Title>
            <Dialog.Close className="p-1 hover:bg-gl-bg-hover rounded">
              <X className="w-5 h-5 text-gl-text-muted" />
            </Dialog.Close>
          </div>

          {/* Tabs */}
          <Tabs.Root defaultValue="llm" className="flex-1 flex flex-col overflow-hidden">
            <Tabs.List className="flex border-b border-gl-border px-6">
              <Tabs.Trigger value="llm" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                LLM Providers
              </Tabs.Trigger>
              <Tabs.Trigger value="ui" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                UI Preferences
              </Tabs.Trigger>
              <Tabs.Trigger value="project" className="px-4 py-2 text-sm data-[state=active]:text-gl-accent data-[state=active]:border-b-2 data-[state=active]:border-gl-accent">
                Project Defaults
              </Tabs.Trigger>
            </Tabs.List>

            {/* LLM Tab */}
            <Tabs.Content value="llm" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">Anthropic (Claude)</h3>
                <input type="password" value={settings.llm.anthropic_key}
                  onChange={e => setSettings({...settings, llm: {...settings.llm, anthropic_key: e.target.value}})}
                  className="w-full px-3 py-2 bg-gl-bg-dark border border-gl-border rounded text-gl-text-primary" placeholder="API Key" />
              </div>
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">OpenAI (GPT)</h3>
                <input type="password" value={settings.llm.openai_key}
                  onChange={e => setSettings({...settings, llm: {...settings.llm, openai_key: e.target.value}})}
                  className="w-full px-3 py-2 bg-gl-bg-dark border border-gl-border rounded text-gl-text-primary" placeholder="API Key" />
              </div>
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">Google (Gemini)</h3>
                <input type="password" value={settings.llm.google_key}
                  onChange={e => setSettings({...settings, llm: {...settings.llm, google_key: e.target.value}})}
                  className="w-full px-3 py-2 bg-gl-bg-dark border border-gl-border rounded text-gl-text-primary" placeholder="API Key" />
              </div>
            </Tabs.Content>

            {/* UI Tab */}
            <Tabs.Content value="ui" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">Theme</h3>
                <select value={settings.ui.theme}
                  onChange={e => setSettings({...settings, ui: {...settings.ui, theme: e.target.value}})}
                  className="w-full px-3 py-2 bg-gl-bg-dark border border-gl-border rounded text-gl-text-primary">
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="system">System</option>
                </select>
              </div>
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">Font Size: {settings.ui.font_size}px</h3>
                <input type="range" min="10" max="18" value={settings.ui.font_size}
                  onChange={e => setSettings({...settings, ui: {...settings.ui, font_size: parseInt(e.target.value)}})}
                  className="w-full" />
              </div>
            </Tabs.Content>

            {/* Project Tab */}
            <Tabs.Content value="project" className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="bg-gl-bg-medium rounded-lg p-4">
                <h3 className="text-sm font-medium text-gl-text-primary mb-2">Default LLM Provider</h3>
                <select value={settings.project.default_llm}
                  onChange={e => setSettings({...settings, project: {...settings.project, default_llm: e.target.value}})}
                  className="w-full px-3 py-2 bg-gl-bg-dark border border-gl-border rounded text-gl-text-primary">
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="google">Google</option>
                </select>
              </div>
              <div className="bg-gl-bg-medium rounded-lg p-4 space-y-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={settings.project.auto_save}
                    onChange={e => setSettings({...settings, project: {...settings.project, auto_save: e.target.checked}})}
                    className="w-4 h-4 rounded" />
                  <span className="text-sm text-gl-text-primary">Enable auto-save</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={settings.project.auto_regen}
                    onChange={e => setSettings({...settings, project: {...settings.project, auto_regen: e.target.checked}})}
                    className="w-4 h-4 rounded" />
                  <span className="text-sm text-gl-text-primary">Auto-queue regeneration on edit</span>
                </label>
              </div>
            </Tabs.Content>
          </Tabs.Root>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-gl-border">
            <button onClick={() => onOpenChange(false)} className="px-4 py-2 text-sm bg-gl-bg-medium hover:bg-gl-bg-hover rounded text-gl-text-primary">
              Cancel
            </button>
            <button onClick={handleSave} disabled={isSaving}
              className="px-4 py-2 text-sm bg-gl-accent hover:bg-gl-accent/80 rounded text-white flex items-center gap-2 disabled:opacity-50">
              <Save className="w-4 h-4" /> Save Settings
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

