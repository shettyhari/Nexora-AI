"use client";

import React, { useState, useEffect } from "react";
import { NexoraLogo } from "@/components/branding/NexoraLogo";
import { STORAGE_KEYS } from "@/lib/constants";
import { Sparkles, BrainCircuit, Zap, ArrowRight, X } from "lucide-react";

export const OnboardingModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const hasSeen = localStorage.getItem(STORAGE_KEYS.ONBOARDED);
    if (!hasSeen) {
      setIsOpen(true);
    }
  }, []);

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEYS.ONBOARDED, "true");
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-lg rounded-3xl border border-cyan-500/30 bg-white dark:bg-[#0c1220] shadow-2xl p-6 md:p-8 overflow-hidden">
        {/* Glow background accent */}
        <div className="absolute -top-20 -left-20 w-48 h-48 bg-cyan-500/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -right-20 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center justify-between mb-4">
            <NexoraLogo size={44} />
            <button
              onClick={handleDismiss}
              className="p-1.5 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <h2 className="text-xl md:text-2xl font-extrabold text-slate-900 dark:text-white">
            Welcome to NEXORA AI
          </h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            Your high-performance AI assistant engineered for deep reasoning, streaming synthesis, and precision problem-solving.
          </p>

          <div className="mt-6 space-y-3.5">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-500 mt-0.5">
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                  Instant Streaming & Syntax Highlighting
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Real-time token generation with syntax-highlighted code blocks, tables, and LaTeX math.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-500 mt-0.5">
                <BrainCircuit className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                  Deep Reasoning Mode
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Activate &quot;Reason&quot; mode for multi-step algorithmic derivation and transparent thoughts.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-500 mt-0.5">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                  Multi-Model Ecosystem
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Switch between NEXORA Flagship, Gemini, GPT-4o, and Claude on the fly.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={handleDismiss}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-semibold text-sm shadow-lg shadow-cyan-500/20 hover:scale-[1.02] active:scale-98 transition-all"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

