"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, BrainCircuit } from "lucide-react";

interface ThinkingBlockProps {
  reasoning: string;
  isStreaming?: boolean;
}

export const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ reasoning, isStreaming }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!reasoning && !isStreaming) return null;

  return (
    <div className="mb-3 rounded-xl border border-indigo-200/60 dark:border-indigo-900/50 bg-indigo-50/40 dark:bg-indigo-950/20 overflow-hidden text-xs transition-all">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-2 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100/40 dark:hover:bg-indigo-900/30 transition-colors select-none font-medium"
      >
        <div className="flex items-center gap-2">
          <BrainCircuit className={`w-3.5 h-3.5 text-indigo-500 ${isStreaming ? "animate-pulse" : ""}`} />
          <span>{isStreaming ? "Thinking through response..." : "Reasoning Process"}</span>
          {isStreaming && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          )}
        </div>
        <div className="flex items-center gap-1 text-indigo-500">
          <span>{isOpen ? "Hide" : "Show"}</span>
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {(isOpen || isStreaming) && (
        <div className="p-3.5 border-t border-indigo-100 dark:border-indigo-900/40 text-slate-600 dark:text-slate-300 font-mono text-[11px] leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto bg-slate-50/50 dark:bg-slate-950/30">
          {reasoning}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3 ml-1 bg-indigo-400 animate-pulse align-middle" />
          )}
        </div>
      )}
    </div>
  );
};
