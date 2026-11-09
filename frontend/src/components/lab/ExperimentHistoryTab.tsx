"use client";

import React, { useState } from "react";
import { LabExperiment } from "@/types/lab";
import { History, Play, RotateCcw, CheckCircle2, Clock, AlertCircle, Eye, Lock } from "lucide-react";
import { api } from "@/lib/api";

interface ExperimentHistoryTabProps {
  experiments: LabExperiment[];
  onRefresh: () => void;
}

export const ExperimentHistoryTab: React.FC<ExperimentHistoryTabProps> = ({
  experiments,
  onRefresh
}) => {
  const [selectedExpId, setSelectedExpId] = useState<string | null>(null);
  const [details, setDetails] = useState<any>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleStart = async (id: string) => {
    setLoadingAction(`start_${id}`);
    try {
      await api.startLabExperiment(id);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to start experiment: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReproduce = async (id: string) => {
    setLoadingAction(`reproduce_${id}`);
    try {
      await api.reproduceLabExperiment(id);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to reproduce experiment: ${err.message}`);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleViewDetails = async (id: string) => {
    try {
      const res = await api.getLabExperimentDetails(id);
      setDetails(res);
      setSelectedExpId(id);
    } catch (err: any) {
      alert(`Failed to load details: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <History className="w-5 h-5 text-cyan-400" />
            Experiment Tracking & MLflow Lineage
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Immutable experiment tracking with exact random seed locking, real loss evaluation, and reproducible execution twins.
          </p>
        </div>
      </div>

      {/* Experiments Table */}
      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
              <tr>
                <th className="px-4 py-3">Experiment Run</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Model Target</th>
                <th className="px-4 py-3">Progress / Steps</th>
                <th className="px-4 py-3">Best Loss</th>
                <th className="px-4 py-3">Perplexity</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {experiments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    No experiments created yet. Go to Training Config to launch your first run.
                  </td>
                </tr>
              ) : (
                experiments.map((exp) => (
                  <tr key={exp.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground">{exp.name}</div>
                      <div className="text-[10px] font-mono text-muted-foreground">
                        seed: {exp.hyperparameters?.seed || 42} | id:{exp.id.slice(0, 8)}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${
                          exp.status === "completed"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : exp.status === "running"
                            ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                            : "bg-muted text-muted-foreground border border-border"
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            exp.status === "completed"
                              ? "bg-emerald-400"
                              : exp.status === "running"
                              ? "bg-cyan-400 animate-pulse"
                              : "bg-muted-foreground"
                          }`}
                        />
                        {exp.status}
                      </span>
                    </td>

                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground">{exp.model_name}</div>
                      <div className="text-[11px] text-muted-foreground">
                        ds v{exp.dataset_version}
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono">
                      {exp.current_step} / {exp.max_steps}
                      {exp.duration_seconds > 0 && (
                        <div className="text-[10px] text-muted-foreground">{exp.duration_seconds}s elapsed</div>
                      )}
                    </td>

                    <td className="px-4 py-3 font-mono text-foreground font-semibold">
                      {exp.best_val_loss ? exp.best_val_loss.toFixed(4) : "—"}
                    </td>

                    <td className="px-4 py-3 font-mono text-cyan-400 font-semibold">
                      {exp.best_perplexity ? exp.best_perplexity.toFixed(2) : "—"}
                    </td>

                    <td className="px-4 py-3 text-right space-x-1.5">
                      {exp.status === "created" && (
                        <button
                          onClick={() => handleStart(exp.id)}
                          disabled={loadingAction === `start_${exp.id}`}
                          className="px-2.5 py-1 rounded bg-cyan-500 hover:bg-cyan-600 text-white text-[11px] font-medium transition-colors disabled:opacity-50"
                        >
                          {loadingAction === `start_${exp.id}` ? "Running..." : "Start"}
                        </button>
                      )}

                      {exp.status === "completed" && (
                        <button
                          onClick={() => handleReproduce(exp.id)}
                          disabled={loadingAction === `reproduce_${exp.id}`}
                          className="px-2 py-1 rounded border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 text-[11px] transition-colors"
                          title="Execute reproducible run with exact locked seed"
                        >
                          Reproduce
                        </button>
                      )}

                      <button
                        onClick={() => handleViewDetails(exp.id)}
                        className="px-2 py-1 rounded border border-border hover:bg-muted text-[11px] text-foreground transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Experiment Details Modal */}
      {details && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-3xl p-6 shadow-2xl relative max-h-[85vh] flex flex-col space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-foreground">{details.experiment.name}</h3>
                <span className="text-xs text-muted-foreground font-mono">
                  ID: {details.experiment.id} | Status: {details.experiment.status}
                </span>
              </div>
              <button
                onClick={() => setDetails(null)}
                className="px-3 py-1 rounded-lg bg-muted text-xs text-foreground"
              >
                Close
              </button>
            </div>

            {/* Reproducibility Manifest Badge */}
            <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-cyan-400" />
                <span className="font-semibold text-cyan-300">Reproducibility Lock Hash:</span>
              </div>
              <span className="font-mono text-[11px] text-cyan-200">
                {details.reproducibility_manifest?.manifest_sha256}
              </span>
            </div>

            {/* Loss History Steps */}
            <div className="flex-1 overflow-y-auto space-y-2 border border-border rounded-lg p-3 bg-muted/20">
              <h4 className="text-xs font-semibold text-foreground mb-2">Step Loss & Perplexity Trajectory:</h4>
              <div className="grid grid-cols-5 gap-2 text-[10px] font-semibold text-muted-foreground uppercase px-2">
                <span>Step</span>
                <span>Train Loss</span>
                <span>Val Loss</span>
                <span>Perplexity</span>
                <span>Learning Rate</span>
              </div>
              {details.experiment.loss_history?.map((step: any, idx: number) => (
                <div
                  key={idx}
                  className="grid grid-cols-5 gap-2 p-2 rounded bg-card border border-border/40 font-mono text-xs items-center"
                >
                  <span className="text-muted-foreground">#{step.step}</span>
                  <span className="text-foreground">{step.train_loss.toFixed(4)}</span>
                  <span className="text-emerald-400 font-semibold">{step.val_loss.toFixed(4)}</span>
                  <span className="text-cyan-400 font-semibold">{step.perplexity.toFixed(2)}</span>
                  <span className="text-muted-foreground">{step.lr}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

