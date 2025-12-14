"use client";

import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { Workspace } from "@/components/workspace";
import { PipelinePanel } from "@/components/pipeline-panel";
import { AssistantPanel } from "@/components/assistant-panel";
import { SettingsModal } from "@/components/modals";
import { useAppStore } from "@/lib/store";

export default function Home() {
  const { settingsOpen, setSettingsOpen } = useAppStore();

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <Workspace />
        <PipelinePanel />
        <AssistantPanel />
      </div>

      {/* Global Modals */}
      <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  );
}
