"use client";

import React from "react";
import { NexoraLogo } from "@/components/branding/NexoraLogo";
import { DEFAULT_SUGGESTIONS } from "@/lib/constants";
import { Code, Atom, Cpu, ShieldAlert, ArrowUpRight } from "lucide-react";

interface EmptyChatStateProps {
  onSelectPrompt: (prompt: string) => void;
}

const ICONS: Record<string, React.ReactNode> = {
  Code: <Code className="w-5 h-5 text-cyan-400" />,
  Atom: <Atom className="w-5 h-5 text-indigo-400" />,
  Cpu: <Cpu className="w-5 h-5 text-purple-400" />,
  ShieldAlert: <ShieldAlert className="w-5 h-5 text-emerald-400" />,
};

export const EmptyChatState: React.FC<EmptyChatStateProps> = ({ onSelectPrompt }) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-3xl mx-auto select-none">
      <div className="mb-6 relative">
        <div className="absolute inset-0 rounded-full bg-cyan-500/20 blur-2xl animate-pulse" />
        <NexoraLogo size={64} className="relative shadow-2xl" />
      </div>

      <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-800 dark:from-white dark:via-cyan-100 dark:to-indigo-200 bg-clip-text text-transparent">
        What will you engineer today?
      </h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 max-w-md">
        NEXORA is your autonomous neural workspace for deep reasoning, architectural design, and full-stack innovation.
      </p>

      {/* Suggested prompts grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full mt-8">
        {DEFAULT_SUGGESTIONS.map((item, idx) => (
          <button
            key={idx}
            onClick={() => onSelectPrompt(item.prompt)}
            className="flex items-start gap-3 p-4 rounded-2xl border border-slate-200/80 dark:border-slate-800/80 bg-white/60 dark:bg-slate-900/40 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:border-cyan-500/40 text-left transition-all duration-200 group shadow-sm hover:shadow-md"
          >
            <div className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800/80 flex-shrink-0 group-hover:scale-105 transition-transform">
              {ICONS[item.icon] || <Code className="w-5 h-5 text-cyan-400" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-xs md:text-sm text-slate-800 dark:text-slate-200 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
                  {item.title}
                </h3>
                <ArrowUpRight className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                {item.prompt}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
