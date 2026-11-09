"use client";

import React, { useState } from "react";
import { LabBenchmarkSuite, LabCheckpoint, LabDataset } from "@/types/lab";
import { Award, ShieldCheck, AlertTriangle, ThumbsUp, GitCompare } from "lucide-react";
import { api } from "@/lib/api";

interface BenchmarkCompareTabProps {
  suites: LabBenchmarkSuite[];
  checkpoints: LabCheckpoint[];
  datasets: LabDataset[];
  onRefresh: () => void;
}

const DIMENSION_LABELS: Record<string, string> = {
  general_knowledge: "General Knowledge",
  reasoning: "Reasoning",
  mathematics: "Mathematics",
  coding: "Coding",
  instruction_following: "Instruction Following",
  multilingual: "Multilingual",
  long_context: "Long-Context",
  factuality: "Factuality",
  safety: "Safety",
  tool_calling: "Tool Calling",
};

export const BenchmarkCompareTab: React.FC<BenchmarkCompareTabProps> = ({
  suites,
  checkpoints,
  datasets,
  onRefresh
}) => {
  const [name, setName] = useState("Base vs Fine-Tuned Evaluation");
  const [candModel, setCandModel] = useState("NEXORA NANO SFT");
  const [candCkptId, setCandCkptId] = useState(checkpoints[0]?.id || "");
  const [baseModel, setBaseModel] = useState("NEXORA NANO Base");
  const [baseCkptId, setBaseCkptId] = useState("");
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || "");
  const [loading, setLoading] = useState(false);

  const [ratingPrompt, setRatingPrompt] = useState("Compare fine-tuned response accuracy on attention derivation.");
  const [ratingPref, setRatingPref] = useState("candidate");
  const [ratingScore, setRatingScore] = useState(5);

  const handleRunCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.runLabComparativeBenchmark({
        name,
        candidate_model_name: candModel,
        candidate_checkpoint_id: candCkptId || undefined,
        baseline_model_name: baseModel,
        baseline_checkpoint_id: baseCkptId || undefined,
        dataset_id: datasetId || undefined,
      });
      onRefresh();
    } catch (err: any) {
      alert(`Comparative benchmark failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitHumanRating = async (suiteId: string) => {
    try {
      await api.submitLabHumanRating(suiteId, {
        evaluator: "principal-researcher",
        prompt: ratingPrompt,
        preference: ratingPref,
        coherence: ratingScore,
        helpfulness: ratingScore,
        safety_pass: true,
      });
      onRefresh();
    } catch (err: any) {
      alert(`Failed to save human rating: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <GitCompare className="w-5 h-5 text-cyan-400" />
          10-Dimension Model Evaluation, Comparison & Leakage Guard
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Benchmark Knowledge, Reasoning, Math, Code, Instruction, Multilingual, Long-Context, Factuality, Safety & Tool Calling with train/eval leakage scanning and human ratings.
        </p>
      </div>

      {/* Run Comparative Suite Form */}
      <form onSubmit={handleRunCompare} className="border border-border rounded-xl bg-card p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="text-muted-foreground block mb-1">Suite Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            />
          </div>
          <div>
            <label className="text-muted-foreground block mb-1">Candidate Checkpoint</label>
            <select
              value={candCkptId}
              onChange={(e) => setCandCkptId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="">Latest Analytical Candidate</option>
              {checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  Step {c.step} ({c.version}) — val_loss {c.val_loss.toFixed(3)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-muted-foreground block mb-1">Training Dataset (for Leakage Scan)</label>
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="">No external dataset file</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} v{d.version}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs items-end">
          <div>
            <label className="text-muted-foreground block mb-1">Candidate Label</label>
            <input
              type="text"
              value={candModel}
              onChange={(e) => setCandModel(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            />
          </div>
          <div>
            <label className="text-muted-foreground block mb-1">Baseline Model</label>
            <input
              type="text"
              value={baseModel}
              onChange={(e) => setBaseModel(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-semibold disabled:opacity-50"
          >
            {loading ? "Running 10-Axis Suite..." : "Run Base vs Fine-Tuned Comparison"}
          </button>
        </div>
      </form>

      {/* Suite Results */}
      <div className="space-y-5">
        {suites.map((suite) => (
          <div key={suite.id} className="border border-border rounded-xl bg-card p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-sm text-foreground">{suite.name}</h3>
                <p className="text-xs text-muted-foreground font-mono">
                  {suite.candidate_model_name} ({suite.aggregate_candidate_score}) vs {suite.baseline_model_name} (
                  {suite.aggregate_baseline_score})
                </p>
              </div>
              <div className="flex items-center gap-2 text-[11px] font-medium">
                <span
                  className={`px-2.5 py-1 rounded-full border flex items-center gap-1 ${
                    suite.leakage_blocked
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Leakage Scan: {suite.leakage_overlap_count} overlaps
                </span>
                <span
                  className={`px-2.5 py-1 rounded-full border flex items-center gap-1 ${
                    suite.regression_passed
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                  }`}
                >
                  {suite.regression_passed ? "Regression Gate Passed" : "Regression Detected"}
                </span>
              </div>
            </div>

            {/* 10 Dimensions Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              {Object.entries(DIMENSION_LABELS).map(([key, label]) => {
                const cand = suite.dimension_scores?.[key]?.score ?? 0;
                const delta = suite.deltas?.[key] ?? 0;
                return (
                  <div key={key} className="p-2.5 rounded-lg border border-border/60 bg-muted/20 text-xs">
                    <div className="text-[10px] font-semibold text-muted-foreground truncate">{label}</div>
                    <div className="flex items-baseline justify-between mt-1 font-mono">
                      <span className="font-bold text-foreground">{cand.toFixed(1)}</span>
                      <span className={delta >= 0 ? "text-emerald-400 text-[11px]" : "text-rose-400 text-[11px]"}>
                        {delta >= 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Human Evaluation Section */}
            <div className="pt-3 border-t border-border/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                Human Evaluations Recorded: <strong className="text-foreground">{suite.human_ratings?.length || 0}</strong>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <select
                  value={ratingPref}
                  onChange={(e) => setRatingPref(e.target.value)}
                  className="px-2 py-1 rounded border border-border bg-muted/40"
                >
                  <option value="candidate">Prefer Fine-Tuned Candidate</option>
                  <option value="tie">Tie</option>
                  <option value="baseline">Prefer Baseline</option>
                </select>
                <button
                  type="button"
                  onClick={() => handleSubmitHumanRating(suite.id)}
                  className="flex items-center gap-1 px-3 py-1 rounded bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30"
                >
                  <ThumbsUp className="w-3.5 h-3.5" /> Record Human Evaluation
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

