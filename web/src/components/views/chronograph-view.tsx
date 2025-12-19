"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { Info, X } from "lucide-react";

// Mock data for the chronograph visualization
const MOCK_SCOPE_DATA = {
  series: {
    nodes: [
      { x: 0, y: 20, label: 'S1 Start' },
      { x: 25, y: 45, label: 'S1 Mid' },
      { x: 50, y: 60, label: 'S1 Peak' },
      { x: 75, y: 40, label: 'S1 Resolve' },
      { x: 100, y: 80, label: 'S1 Cliffhanger' },
    ],
    color: '#6366f1',
    label: 'Series Arc'
  },
  season: {
    nodes: [
      { x: 0, y: 30, label: 'Ep1 Hook' },
      { x: 20, y: 50, label: 'Ep2 Build' },
      { x: 40, y: 35, label: 'Ep3 Twist' },
      { x: 60, y: 70, label: 'Ep4 Climax' },
      { x: 80, y: 55, label: 'Ep5 Fall' },
      { x: 100, y: 85, label: 'Finale' },
    ],
    color: '#a855f7',
    label: 'Season Arc'
  },
  episode: {
    nodes: [
      { x: 0, y: 25, label: 'Cold Open' },
      { x: 15, y: 40, label: 'Inciting' },
      { x: 30, y: 55, label: 'Rising' },
      { x: 50, y: 75, label: 'Midpoint' },
      { x: 70, y: 60, label: 'Complications' },
      { x: 85, y: 90, label: 'Climax' },
      { x: 100, y: 45, label: 'Resolution' },
    ],
    color: '#06b6d4',
    label: 'Episode Arc'
  }
};

const CHARACTER_LINES = [
  { id: 'c1', name: 'Elara', color: '#8b5cf6', nodes: [
    { x: 0, y: 30 }, { x: 20, y: 45 }, { x: 40, y: 60 }, { x: 60, y: 50 }, { x: 80, y: 75 }, { x: 100, y: 55 }
  ]},
  { id: 'c2', name: 'Kael', color: '#10b981', nodes: [
    { x: 0, y: 20 }, { x: 25, y: 35 }, { x: 50, y: 55 }, { x: 75, y: 70 }, { x: 100, y: 60 }
  ]},
  { id: 'c3', name: 'Vex', color: '#ef4444', nodes: [
    { x: 0, y: 40 }, { x: 30, y: 50 }, { x: 60, y: 80 }, { x: 90, y: 65 }, { x: 100, y: 85 }
  ]},
];

interface NodeInfo {
  label: string;
  x: number;
  y: number;
  color: string;
  type: string;
}

export function ChronographView() {
  const { viewScope, activeLines, activePrimary } = useAppStore();
  const [selectedNode, setSelectedNode] = useState<NodeInfo | null>(null);

  const scopeData = MOCK_SCOPE_DATA[viewScope];

  // Generate SVG path from nodes
  const generatePath = (nodes: { x: number; y: number }[]) => {
    if (nodes.length === 0) return '';
    const points = nodes.map((n, i) => {
      const x = (n.x / 100) * 100;
      const y = 100 - n.y;
      return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
    });
    return points.join(' ');
  };

  // Filter character lines based on activeLines
  const visibleCharacterLines = useMemo(() => {
    return CHARACTER_LINES.filter(line => activeLines.includes(line.id));
  }, [activeLines]);

  // Check if primary line should be shown
  const showPrimaryLine = activePrimary.includes(`${viewScope}_critical`);

  return (
    <div className="flex-1 flex flex-col bg-black overflow-hidden">
      {/* Graph Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100">Chronograph</h2>
          <p className="text-xs text-slate-500">Story Escalation & Progression Tracking</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: scopeData.color }} />
            <span className="text-xs text-slate-400">{scopeData.label}</span>
          </div>
          {visibleCharacterLines.map(line => (
            <div key={line.id} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: line.color }} />
              <span className="text-xs text-slate-400">{line.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Graph Area */}
      <div className="flex-1 p-6 relative">
        <div className="w-full h-full bg-slate-950 rounded-xl border border-slate-800 p-4 relative overflow-hidden">
          {/* Grid Background */}
          <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
            <defs>
              <pattern id="grid" width="10%" height="20%" patternUnits="userSpaceOnUse">
                <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#1e293b" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          {/* Main Graph SVG */}
          <svg className="w-full h-full relative z-10" viewBox="0 0 100 100" preserveAspectRatio="none">
            {/* Primary scope line */}
            {showPrimaryLine && (
              <g>
                <path
                  d={generatePath(scopeData.nodes)}
                  fill="none"
                  stroke={scopeData.color}
                  strokeWidth="0.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="drop-shadow-lg"
                  style={{ filter: `drop-shadow(0 0 4px ${scopeData.color})` }}
                />
                {scopeData.nodes.map((node, i) => (
                  <circle
                    key={i}
                    cx={(node.x / 100) * 100}
                    cy={100 - node.y}
                    r="1.5"
                    fill={scopeData.color}
                    className="cursor-pointer hover:r-2 transition-all"
                    onClick={() => setSelectedNode({
                      label: node.label,
                      x: node.x,
                      y: node.y,
                      color: scopeData.color,
                      type: scopeData.label
                    })}
                  />
                ))}
              </g>
            )}

            {/* Character lines */}
            {visibleCharacterLines.map(line => (
              <g key={line.id}>
                <path
                  d={generatePath(line.nodes)}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="0.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray="2,1"
                  style={{ filter: `drop-shadow(0 0 3px ${line.color})` }}
                />
              </g>
            ))}
          </svg>

          {/* Y-Axis Labels */}
          <div className="absolute left-2 top-4 bottom-4 flex flex-col justify-between text-[10px] text-slate-600 font-mono">
            <span>100</span>
            <span>75</span>
            <span>50</span>
            <span>25</span>
            <span>0</span>
          </div>

          {/* X-Axis Labels */}
          <div className="absolute bottom-2 left-8 right-4 flex justify-between text-[10px] text-slate-600 font-mono">
            <span>Start</span>
            <span>25%</span>
            <span>50%</span>
            <span>75%</span>
            <span>End</span>
          </div>
        </div>

        {/* Selected Node Detail Panel */}
        {selectedNode && (
          <div className="absolute top-8 right-8 w-64 bg-slate-900 border border-slate-700 rounded-lg shadow-xl p-4 z-20">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedNode.color }} />
                <span className="text-sm font-bold text-slate-200">{selectedNode.type}</span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1 hover:bg-slate-800 rounded"
              >
                <X size={14} className="text-slate-500" />
              </button>
            </div>
            <div className="space-y-2">
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Node</div>
                <div className="text-sm text-slate-200">{selectedNode.label}</div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-950 p-2 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase">Position</div>
                  <div className="text-sm text-slate-200">{selectedNode.x}%</div>
                </div>
                <div className="bg-slate-950 p-2 rounded border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase">Escalation</div>
                  <div className="text-sm text-slate-200">{selectedNode.y}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Empty State */}
      {!showPrimaryLine && visibleCharacterLines.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <Info size={48} className="text-slate-700 mx-auto mb-4" />
            <p className="text-slate-500 text-sm">Enable Lucid Lines in the sidebar to visualize story progression</p>
          </div>
        </div>
      )}
    </div>
  );
}

