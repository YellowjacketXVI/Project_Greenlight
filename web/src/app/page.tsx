"use client";

import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { Workspace } from "@/components/workspace";
import { PipelinePanel } from "@/components/pipeline-panel";
import { AssistantPanel } from "@/components/assistant-panel";

export default function Home() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <Workspace />
        <PipelinePanel />
        <AssistantPanel />
      </div>
    </div>
  );
}
