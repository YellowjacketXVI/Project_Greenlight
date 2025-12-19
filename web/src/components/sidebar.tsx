"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore, type ViewScope } from "@/lib/store";
import {
  User,
  Zap,
  Activity,
  ChevronUp,
  ChevronDown,
  Loader,
} from "lucide-react";

// Mock data - will be replaced with real data from backend
const MOCK_CHARACTERS = [
  { id: 'c1', name: 'Elara', glyph: '◈', color: '#8b5cf6', role: 'Protagonist', plots: ['Identity Crisis', 'The Heist'] },
  { id: 'c2', name: 'Kael', glyph: '⟡', color: '#10b981', role: 'Ally', plots: ['Redemption Arc', 'Betrayal'] },
  { id: 'c3', name: 'Vex', glyph: '⏣', color: '#ef4444', role: 'Antagonist', plots: ['Domination', 'The Fall'] },
];

const MOCK_EVENTS = [
  { id: 'ev1', name: 'The Blackout', buildup: 'Slow', delivery: 'Sudden', color: '#f59e0b' },
  { id: 'ev2', name: 'Core Breach', buildup: 'Exponential', delivery: 'Explosive', color: '#ec4899' }
];

const MOCK_TASKS = [
  { id: 1, name: "Log Generating", progress: 45, status: "processing" as const },
  { id: 2, name: "Processing Checks", progress: 12, status: "processing" as const },
  { id: 3, name: "Context Sync", progress: 100, status: "complete" as const },
  { id: 4, name: "Vector Analysis", progress: 78, status: "processing" as const },
];

function TaskItem({ name, progress, status }: { name: string; progress: number; status: string }) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex justify-between text-[10px] text-slate-400 mb-1 uppercase tracking-wider">
        <span>{name}</span>
        <span>{status === 'complete' ? 'Done' : `${progress}%`}</span>
      </div>
      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            status === 'complete' ? 'bg-emerald-500' : 'bg-cyan-600'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export function Sidebar() {
  const {
    viewScope,
    setViewScope,
    activeLines,
    toggleLine,
    activePrimary,
    togglePrimary,
    sidebarOpen,
  } = useAppStore();

  const [sections, setSections] = useState({ characters: false, events: false });

  const toggleSection = (sec: 'characters' | 'events') => {
    setSections(prev => ({ ...prev, [sec]: !prev[sec] }));
  };

  // Use mock data for now - will be replaced with store data
  const characters = MOCK_CHARACTERS;
  const events = MOCK_EVENTS;
  const tasks = MOCK_TASKS;

  return (
    <div className={cn(
      "bg-slate-900 border-r border-slate-800 flex flex-col h-full transition-all duration-300 z-20 shadow-2xl",
      sidebarOpen ? "w-72" : "w-16"
    )}>
      {/* Header / Logo */}
      <div className="p-6 flex items-center gap-4 border-b border-slate-800 h-20 shrink-0 bg-slate-950">
        <div className="w-10 h-10 bg-slate-100 rounded flex items-center justify-center shadow-lg shadow-white/10 overflow-hidden">
          <div className="text-black font-serif font-bold text-2xl tracking-tighter">LL</div>
        </div>
        {sidebarOpen && (
          <div className="flex flex-col">
            <span className="font-bold text-slate-100 tracking-wide text-lg">LucidLines</span>
            <span className="text-[10px] text-cyan-500 uppercase tracking-widest">Operation System</span>
          </div>
        )}
      </div>

      {/* Scope Selector */}
      <div className="p-4 border-b border-slate-800 shrink-0 bg-slate-900">
        {sidebarOpen && (
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">View Scope</div>
        )}
        <div className="flex bg-slate-800 rounded-lg p-1">
          {(['series', 'season', 'episode'] as ViewScope[]).map(s => (
            <button
              key={s}
              onClick={() => setViewScope(s)}
              className={cn(
                "flex-1 text-center py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wide transition-all",
                viewScope === s
                  ? 'bg-cyan-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              )}
            >
              {sidebarOpen ? s : s[0].toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {sidebarOpen && (
          <div className="p-4 pb-0 mb-2">
            <span className="text-xs font-bold text-slate-100 uppercase tracking-wider border-b-2 border-cyan-500 pb-1">
              Lucid Lines
            </span>
          </div>
        )}

        {/* Primary Lines (Top Level) */}
        <div className="px-3 py-2 space-y-1">
          {['Series Critical', 'Season Critical', 'Episode Critical'].map(type => {
            const id = type.toLowerCase().replace(' ', '_');
            const isActive = activePrimary.includes(id);
            return (
              <button
                key={id}
                onClick={() => togglePrimary(id)}
                className={cn(
                  "w-full flex items-center justify-between p-2 rounded-lg text-xs font-medium transition-all",
                  isActive
                    ? 'bg-indigo-900/50 text-indigo-200 border border-indigo-500/30'
                    : 'text-slate-400 hover:bg-slate-800'
                )}
              >
                <span className="flex items-center gap-2">
                  <Activity size={14} className={isActive ? 'text-indigo-400' : 'text-slate-600'} />
                  {sidebarOpen ? `${type} Plots` : type.split(' ')[0][0]}
                </span>
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  isActive ? 'bg-indigo-400 shadow-glow-indigo' : 'bg-slate-700'
                )} />
              </button>
            );
          })}
        </div>

        {/* Dropdowns - only show when sidebar is open */}
        {sidebarOpen && (
          <div className="px-3 space-y-2 mt-2">
            {/* Characters Dropdown */}
            <div className="border border-slate-800 rounded-lg bg-slate-900/50 overflow-hidden">
              <button
                onClick={() => toggleSection('characters')}
                className="w-full flex items-center justify-between p-3 text-xs font-bold text-slate-300 hover:bg-slate-800 transition-colors"
              >
                <span className="flex items-center gap-2"><User size={14} /> Characters</span>
                {sections.characters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>

              {sections.characters && (
                <div className="bg-slate-950/30 p-2 space-y-1 border-t border-slate-800">
                  {characters.map(char => {
                    const isActive = activeLines.includes(char.id);
                    return (
                      <div key={char.id} className="rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleLine(char.id)}
                          className={cn(
                            "w-full flex items-center gap-3 p-2 transition-all",
                            isActive ? 'bg-slate-800' : 'hover:bg-slate-800/50'
                          )}
                        >
                          <span style={{ color: char.color }} className="text-sm">{char.glyph}</span>
                          <span className={cn(
                            "text-xs flex-1 text-left",
                            isActive ? 'text-white' : 'text-slate-400'
                          )}>{char.name}</span>
                          {isActive && (
                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: char.color }} />
                          )}
                        </button>

                        {/* Sub-plots for character */}
                        {isActive && (
                          <div className="pl-9 pr-2 py-1 space-y-1">
                            {char.plots.map((plot, i) => (
                              <div key={i} className="flex items-center gap-2 text-[10px] text-slate-500">
                                <div className="w-1 h-1 rounded-full bg-slate-600" />
                                {plot}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Events Dropdown */}
            <div className="border border-slate-800 rounded-lg bg-slate-900/50 overflow-hidden">
              <button
                onClick={() => toggleSection('events')}
                className="w-full flex items-center justify-between p-3 text-xs font-bold text-slate-300 hover:bg-slate-800 transition-colors"
              >
                <span className="flex items-center gap-2"><Zap size={14} /> Events</span>
                {sections.events ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>

              {sections.events && (
                <div className="bg-slate-950/30 p-2 space-y-1 border-t border-slate-800">
                  {events.map(ev => (
                    <div key={ev.id} className="p-2 hover:bg-slate-800/50 rounded cursor-pointer group">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-300 font-medium group-hover:text-white transition-colors">
                          {ev.name}
                        </span>
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ev.color }} />
                      </div>
                      <div className="grid grid-cols-2 gap-2 mt-1">
                        <div className="bg-slate-900/80 p-1 rounded border border-slate-800">
                          <div className="text-[8px] text-slate-500 uppercase">Buildup</div>
                          <div className="text-[10px] text-slate-300">{ev.buildup}</div>
                        </div>
                        <div className="bg-slate-900/80 p-1 rounded border border-slate-800">
                          <div className="text-[8px] text-slate-500 uppercase">Delivery</div>
                          <div className="text-[10px] text-slate-300">{ev.delivery}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Task List (Bottom Toolbar) */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/80 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-3 text-xs font-bold text-slate-500 uppercase tracking-wider">
          <Activity size={12} />
          {sidebarOpen && <span>System Tasks</span>}
        </div>
        {sidebarOpen ? (
          <div className="space-y-2">
            {tasks.map(task => (
              <TaskItem key={task.id} {...task} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Loader size={16} className="text-cyan-500 animate-spin" />
          </div>
        )}
      </div>
    </div>
  );
}

