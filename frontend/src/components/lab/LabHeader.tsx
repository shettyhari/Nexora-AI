"use client";

import React from "react";
import Link from "next/link";
import {
  FlaskConical,
  Database,
  Sliders,
  Cpu,
  History,
  HardDrive,
  Award,
  ArrowLeft,
  Activity,
  Layers,
  Gauge,
  GitCompare,
  Server,
  Rocket,
  BarChart3
} from "lucide-react";

export type LabTab =
  | "models"
  | "datasets"
  | "tokenizers"
  | "architecture"
  | "finetuning"
  | "telemetry"
  | "experiments"
  | "training"
  | "checkpoints"
  | "evaluations"
  | "comparison"
  | "optimization"
  | "deployments";

interface LabHeaderProps {
  activeTab: LabTab;
  onTabChange: (tab: LabTab) => void;
  environment?: Record<string, any>;
  counts?: {
    models: number;
    datasets: number;
    experiments: number;
    checkpoints: number;
    jobs?: number;
    deployments?: number;
  };
}

export const LabHeader: React.FC<LabHeaderProps> = ({
  activeTab,
  onTabChange,
  environment,
  counts
}) => {
  const tabs = [
    { id: "models", label: "Model Registry", icon: Layers, count: counts?.models },
    { id: "datasets", label: "Dataset Library", icon: Database, count: counts?.datasets },
    { id: "finetuning", label: "Fine-Tuning Jobs", icon: Rocket, count: counts?.jobs },
    { id: "telemetry", label: "GPU & Telemetry", icon: BarChart3 },
    { id: "checkpoints", label: "Checkpoints", icon: HardDrive, count: counts?.checkpoints },
    { id: "comparison", label: "Benchmark Compare", icon: GitCompare },
    { id: "optimization", label: "Quantization Bench", icon: Gauge },
    { id: "deployments", label: "Inference Server", icon: Server, count: counts?.deployments },
    { id: "tokenizers", label: "Tokenizer Lab", icon: Sliders },
    { id: "architecture", label: "Architecture", icon: Cpu },
    { id: "experiments", label: "Experiments", icon: History, count: counts?.experiments },
    { id: "training", label: "Pretrain Config", icon: Activity },
    { id: "evaluations", label: "Legacy Evals", icon: Award },
  ];

  return (
    <header className="border-b border-border bg-card/60 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        {/* Top Row: Back button, Title & Environment status */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              title="Return to Nexora Chat"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
              <FlaskConical className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-lg text-foreground tracking-tight">NEXORA MODEL LAB</h1>
                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  Training &amp; GPU Infrastructure
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Foundation Model Research, Isolated Fine-Tuning Workers, Quantization &amp; OpenAI Serving
              </p>
            </div>
          </div>

          {/* Environment Status Pills */}
          {environment && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/60 border border-border">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Python {environment.python_version || "3.11"}</span>
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/60 border border-border">
                <span>{environment.cpu_cores || 8} CPU Cores</span>
              </span>
              <span className="hidden md:inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-muted/60 border border-border font-mono text-[11px]">
                commit:{String(environment.git_commit || "HEAD").slice(0, 7)}
              </span>
            </div>
          )}
        </div>

        {/* Tab Strip */}
        <nav className="flex items-center gap-1 mt-4 overflow-x-auto pb-1 no-scrollbar border-t border-border/40 pt-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id as LabTab)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  isActive
                    ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                {typeof tab.count === "number" && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                      isActive ? "bg-cyan-500/30 text-cyan-200" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
