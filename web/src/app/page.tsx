"use client";

import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { Workspace } from "@/components/workspace";
import { FloatingPrompt } from "@/components/floating-prompt";
import { useAppStore } from "@/lib/store";

export default function Home() {
  const { sidebarOpen } = useAppStore();

  return (
    <div className="h-screen flex overflow-hidden bg-black">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <Header />

        {/* Workspace */}
        <Workspace />
      </div>

      {/* Floating AI Prompt */}
      <FloatingPrompt />
    </div>
  );
}
