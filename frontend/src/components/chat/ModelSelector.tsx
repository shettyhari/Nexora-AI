"use client";

import React, { useState, useRef, useEffect } from "react";
import { ModelConfig } from "@/types/chat";
import { ChevronDown, Sparkles, Zap, Bot } from "lucide-react";

interface ModelSelectorProps {
  models: ModelConfig[];
  selectedModelKey: string;
  onSelectModel: (key: string) => void;
  disabled?: boolean;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  models,
  selectedModelKey,
  onSelectModel,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedModel = models.find((m) => m.model_key === selectedModelKey) || models[0] || {
    display_name: "NEXORA Pro",
    badge: "Flagship",
    description: "Intelligent general model",
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm text-slate-800 dark:text-slate-200 text-xs md:text-sm font-medium hover:border-cyan-500/50 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-all shadow-sm"
      >
        <Sparkles className="w-4 h-4 text-cyan-500" />
        <span className="font-semibold">{selectedModel.display_name}</span>
        {selectedModel.badge && (
          <span className="px-1.5 py-0.2 rounded-full bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 text-[10px] font-bold border border-cyan-500/20">
            {selectedModel.badge}
          </span>
        )}
        <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-72 md:w-80 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="px-2 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Available Models
          </div>
          <div className="space-y-1">
            {models.map((model) => (
              <button
                key={model.id || model.model_key}
                onClick={() => {
                  onSelectModel(model.model_key);
                  setIsOpen(false);
                }}
                className={`w-full flex flex-col text-left p-2.5 rounded-xl transition-all ${
                  model.model_key === selectedModelKey
                    ? "bg-cyan-500/10 border border-cyan-500/30 text-slate-900 dark:text-white"
                    : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300 border border-transparent"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 font-semibold text-sm truncate">
                    {model.provider === "gemini" || model.provider === "google" ? (
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                    ) : (
                      <Bot className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    )}
                    <span className="truncate">{model.display_name}</span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {model.is_proprietary && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                        NEXORA
                      </span>
                    )}
                    {model.plan_permitted === false && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 uppercase">
                        {model.min_plan_tier || "PRO"}
                      </span>
                    )}
                    {model.badge && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                        {model.badge}
                      </span>
                    )}
                  </div>
                </div>
                {model.description && (
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-snug">
                    {model.description}
                  </p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

