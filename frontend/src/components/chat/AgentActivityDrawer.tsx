"use client";

import React, { useState } from "react";
import {
  Bot,
  BrainCircuit,
  Search,
  Code2,
  BarChart3,
  FileSearch,
  Globe2,
  Eye,
  UserCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
  ShieldCheck,
  ChevronRight,
  X,
  Sparkles,
} from "lucide-react";
import { AgentStepInfo, AgentWorkflowInfo } from "@/types/chat";
import { api } from "@/lib/api";

interface AgentActivityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  workflow?: AgentWorkflowInfo | null;
  onApproveTool?: (toolId: string) => void;
}

const AGENT_ICONS: Record<string, React.ReactNode> = {
  orchestrator: <BrainCircuit className="w-4 h-4 text-purple-400" />,
  research: <Search className="w-4 h-4 text-blue-400" />,
  coding: <Code2 className="w-4 h-4 text-emerald-400" />,
  data_analysis: <BarChart3 className="w-4 h-4 text-amber-400" />,
  document: <FileSearch className="w-4 h-4 text-rose-400" />,
  browser: <Globe2 className="w-4 h-4 text-cyan-400" />,
  vision: <Eye className="w-4 h-4 text-indigo-400" />,
  personal_assistant: <UserCheck className="w-4 h-4 text-pink-400" />,
};

const AGENT_TITLES: Record<string, string> = {
  orchestrator: "Central Orchestrator",
  research: "Web & Literature Research Agent",
  coding: "Software Engineering & Coding Agent",
  data_analysis: "Data Analysis & Chart Agent",
  document: "Document Intelligence Agent",
  browser: "Safe Browser Agent",
  vision: "Multimodal Vision Agent",
  personal_assistant: "Personal Executive Assistant",
};

export const AgentActivityDrawer: React.FC<AgentActivityDrawerProps> = ({
  isOpen,
  onClose,
  workflow,
  onApproveTool,
}) => {
  const [activeTab, setActiveTab] = useState<"timeline" | "agents">("timeline");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-card border-l border-border shadow-2xl flex flex-col animate-slide-left">
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/20">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-nexora-indigo to-nexora-violet flex items-center justify-center text-white shadow-md">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-foreground flex items-center gap-1.5">
              Multi-Agent Orchestrator
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/30 font-medium">
                8 Autonomous Agents
              </span>
            </h3>
            <p className="text-[11px] text-muted-foreground">Coordinated execution timeline & tool telemetry</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border px-5 bg-muted/10">
        <button
          onClick={() => setActiveTab("timeline")}
          className={`py-2.5 text-xs font-medium border-b-2 transition-all mr-4 ${
            activeTab === "timeline"
              ? "border-nexora-indigo text-nexora-indigo"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Active Workflow
        </button>
        <button
          onClick={() => setActiveTab("agents")}
          className={`py-2.5 text-xs font-medium border-b-2 transition-all ${
            activeTab === "agents"
              ? "border-nexora-indigo text-nexora-indigo"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Registered Agents (8)
        </button>
      </div>

      {/* Drawer Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {activeTab === "timeline" ? (
          workflow ? (
            <div className="space-y-4">
              {/* Goal summary */}
              <div className="p-3.5 rounded-xl border border-border/80 bg-muted/30 space-y-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-nexora-violet" />
                  Orchestrated Goal
                </p>
                <p className="text-xs text-foreground font-medium leading-relaxed">{workflow.goal}</p>
                <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-nexora-indigo" />
                    Status: <strong className="text-foreground capitalize">{workflow.status}</strong>
                  </span>
                  <span>•</span>
                  <span>{workflow.plan.length} Planned Steps</span>
                </div>
              </div>

              {/* Timeline Steps */}
              <div className="space-y-3 relative before:absolute before:inset-0 before:left-3.5 before:w-0.5 before:bg-border/60">
                {workflow.plan.map((step, idx) => {
                  const stepResult = workflow.step_results?.find((r) => r.step_number === step.step_number);
                  const isCompleted = stepResult?.status === "completed";
                  const isRunning = stepResult?.status === "running";
                  const isWaiting = stepResult?.status === "waiting_approval";

                  return (
                    <div key={idx} className="relative flex items-start gap-3 pl-1">
                      <div
                        className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 z-10 ${
                          isCompleted
                            ? "bg-emerald-500 text-white"
                            : isRunning
                            ? "bg-nexora-indigo text-white animate-pulse"
                            : isWaiting
                            ? "bg-amber-500 text-white animate-bounce"
                            : "bg-muted border border-border text-muted-foreground"
                        }`}
                      >
                        {isCompleted ? <CheckCircle2 className="w-3.5 h-3.5" /> : step.step_number}
                      </div>

                      <div className="flex-1 rounded-xl border border-border bg-card p-3 shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                            {AGENT_ICONS[step.agent_type] || <Bot className="w-3.5 h-3.5" />}
                            {AGENT_TITLES[step.agent_type] || step.agent_type}
                          </span>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                              isCompleted
                                ? "bg-emerald-500/10 text-emerald-500"
                                : isRunning
                                ? "bg-nexora-indigo/10 text-nexora-indigo"
                                : isWaiting
                                ? "bg-amber-500/10 text-amber-500"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {stepResult?.status || "planned"}
                          </span>
                        </div>

                        <p className="text-xs text-muted-foreground leading-relaxed">{step.description}</p>

                        {/* Required tools */}
                        {step.required_tools.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {step.required_tools.map((tool, tIdx) => (
                              <span
                                key={tIdx}
                                className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border"
                              >
                                {tool}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Approval banner if waiting */}
                        {isWaiting && (
                          <div className="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between">
                            <span className="text-[11px] text-amber-500 flex items-center gap-1">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              Sensitive tool execution requires approval
                            </span>
                            <button
                              onClick={() => onApproveTool?.(step.required_tools[0])}
                              className="px-2.5 py-1 text-xs font-medium rounded bg-amber-500 text-white hover:bg-amber-600 transition-colors"
                            >
                              Approve
                            </button>
                          </div>
                        )}

                        {/* Step Output */}
                        {stepResult?.output && (
                          <div className="mt-2 pt-2 border-t border-border/40 text-[11px] text-foreground/80 font-mono bg-muted/20 p-2 rounded line-clamp-3">
                            {stepResult.output}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground space-y-2">
              <Bot className="w-10 h-10 mx-auto text-muted-foreground/40" />
              <p className="text-sm font-medium">No active agent workflow</p>
              <p className="text-xs">
                Ask a multi-faceted question or toggle Agent Mode in the composer to launch autonomous agents.
              </p>
            </div>
          )
        ) : (
          <div className="space-y-2.5">
            {Object.entries(AGENT_TITLES).map(([key, title]) => (
              <div
                key={key}
                className="p-3 rounded-xl border border-border bg-card hover:border-nexora-indigo/40 transition-all space-y-1"
              >
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-muted text-foreground">
                    {AGENT_ICONS[key] || <Bot className="w-4 h-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-foreground truncate">{title}</p>
                    <p className="text-[11px] text-muted-foreground font-mono">type: {key}</p>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-medium">
                    Ready
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
