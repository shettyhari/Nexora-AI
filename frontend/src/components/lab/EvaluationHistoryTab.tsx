"use client";

import React, { useState } from "react";
import { LabEvaluation, LabExperiment } from "@/types/lab";
import { Award, Plus, Sparkles, CheckCircle2, TrendingUp, BarChart2 } from "lucide-react";
import { api } from "@/lib/api";

interface EvaluationHistoryTabProps {
  evaluations: LabEvaluation[];
  experiments: LabExperiment[];
  onRefresh: () => void;
}

export const EvaluationHistoryTab: React.FC<EvaluationHistoryTabProps> = ({
  evaluations,
  experiments,
  onRefresh
}) => {
  const [showModal, setShowModal] = useState(false);
  const [selectedExpId, setSelectedExpId] = useState(experiments[0]?.id || "");
  const [benchmarkName, setBenchmarkName] = useState("WikiText-Perplexity");
  const [loading, setLoading] = useState(false);

  const handleRunEvaluation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExpId) return;
    setLoading(true);
    try {
      await api.runLabEvaluation({
        experiment_id: selectedExpId,
        benchmark_name: benchmarkName
      });
      setShowModal(false);
      onRefresh();
    } catch (err: any) {
      alert(`Evaluation run failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Award className="w-5 h-5 text-cyan-400" />
            Evaluation History & Benchmark Registry
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Perplexity, zero-shot accuracy, bits-per-byte metrics, and autoregressive generation verification.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Run Benchmark Evaluation</span>
        </button>
      </div>

      {/* Evaluations Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {evaluations.length === 0 ? (
          <div className="md:col-span-2 border border-border rounded-xl p-8 text-center text-xs text-muted-foreground bg-card">
            No evaluation benchmarks recorded yet. Click &quot;Run Benchmark Evaluation&quot; to test a checkpoint.
          </div>
        ) : (
          evaluations.map((ev) => (
            <div key={ev.id} className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    {ev.benchmark_name}
                  </span>
                  <h3 className="font-bold text-sm text-foreground mt-1.5">
                    Benchmark Evaluation #{ev.id.slice(0, 8)}
                  </h3>
                </div>
                <span className="text-[11px] text-muted-foreground font-mono">
                  {new Date(ev.created_at).toLocaleDateString()}
                </span>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-3 gap-2.5 pt-1">
                <div className="bg-muted/40 p-2.5 rounded-lg border border-border/50 text-center">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Perplexity
                  </span>
                  <span className="font-mono font-bold text-base text-cyan-400">
                    {ev.metrics?.perplexity?.toFixed(2) || "—"}
                  </span>
                </div>

                <div className="bg-muted/40 p-2.5 rounded-lg border border-border/50 text-center">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Loss (CE)
                  </span>
                  <span className="font-mono font-bold text-base text-emerald-400">
                    {ev.metrics?.cross_entropy_loss?.toFixed(4) || "—"}
                  </span>
                </div>

                <div className="bg-muted/40 p-2.5 rounded-lg border border-border/50 text-center">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Accuracy
                  </span>
                  <span className="font-mono font-bold text-base text-indigo-400">
                    {ev.metrics?.accuracy ? `${(ev.metrics.accuracy * 100).toFixed(1)}%` : "—"}
                  </span>
                </div>
              </div>

              {/* Sample Generation Outputs */}
              {ev.sample_generations && ev.sample_generations.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-border/40">
                  <span className="text-xs font-semibold text-foreground block">
                    Sample Autoregressive Generations:
                  </span>
                  <div className="space-y-1.5 font-mono text-[11px]">
                    {ev.sample_generations.map((g, idx) => (
                      <div key={idx} className="p-2 rounded bg-muted/30 border border-border/40">
                        <span className="text-cyan-400 font-semibold">{g.prompt}</span>
                        <span className="text-foreground">{g.completion}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Run Evaluation Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-foreground mb-1">Run Benchmark Evaluation</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Executes validation perplexity and token generation scoring on a trained checkpoint.
            </p>

            <form onSubmit={handleRunEvaluation} className="space-y-3.5">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Target Experiment</label>
                <select
                  value={selectedExpId}
                  onChange={(e) => setSelectedExpId(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                >
                  {experiments.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name} ({e.status} - best loss: {e.best_val_loss?.toFixed(2) || "N/A"})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Benchmark Suite</label>
                <select
                  value={benchmarkName}
                  onChange={(e) => setBenchmarkName(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                >
                  <option value="WikiText-Perplexity">WikiText-Perplexity (Language Modeling)</option>
                  <option value="HumanEval-Mini">HumanEval-Mini (Python Synthesis)</option>
                  <option value="GSM8K-Mini">GSM8K-Mini (Grade School Math)</option>
                  <option value="CommonsenseQA-Mini">CommonsenseQA-Mini (Common Knowledge)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium disabled:opacity-50"
                >
                  {loading ? "Evaluating..." : "Run Evaluation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

