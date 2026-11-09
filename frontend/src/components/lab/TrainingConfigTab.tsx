"use client";

import React, { useState } from "react";
import { LabModel, LabDataset } from "@/types/lab";
import { Activity, Play, Sparkles, Sliders, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

interface TrainingConfigTabProps {
  models: LabModel[];
  datasets: LabDataset[];
  onExperimentStarted: () => void;
}

export const TrainingConfigTab: React.FC<TrainingConfigTabProps> = ({
  models,
  datasets,
  onExperimentStarted
}) => {
  const [name, setName] = useState("");
  const [selectedModelId, setSelectedModelId] = useState(models[0]?.id || "");
  const [selectedDatasetId, setSelectedDatasetId] = useState(datasets[0]?.id || "");
  const [lr, setLr] = useState("0.0003");
  const [optimizer, setOptimizer] = useState("AdamW");
  const [batchSize, setBatchSize] = useState("4");
  const [gradAccum, setGradAccum] = useState("2");
  const [maxSteps, setMaxSteps] = useState("20");
  const [seed, setSeed] = useState("42");
  const [weightDecay, setWeightDecay] = useState("0.1");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const selectedModel = models.find((m) => m.id === selectedModelId) || models[0];
      const modelName = selectedModel ? selectedModel.name : "NEXORA NANO";

      const exp = await api.createLabExperiment({
        name: name || `${modelName} Pretraining Run`,
        model_id: selectedModelId,
        model_name: modelName,
        dataset_id: selectedDatasetId || undefined,
        dataset_version: "1.0.0",
        hyperparameters: {
          learning_rate: Number(lr),
          optimizer,
          batch_size: Number(batchSize),
          grad_accum_steps: Number(gradAccum),
          max_steps: Number(maxSteps),
          seed: Number(seed),
          weight_decay: Number(weightDecay)
        },
        notes
      });

      // Automatically execute run
      await api.startLabExperiment(exp.id);
      onExperimentStarted();
    } catch (err: any) {
      alert(`Experiment launch failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          Training Configuration & Hyperparameter Optimization
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Configure learning rate schedules, gradient accumulation, optimizer states, and initiate authentic training runs.
        </p>
      </div>

      <form onSubmit={handleLaunch} className="border border-border rounded-xl bg-card p-6 shadow-sm space-y-5">
        <div>
          <label className="text-xs font-semibold text-foreground block mb-1">Experiment Name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., NEXORA NANO v1-CosineDecay-Step20"
            className="w-full px-3 py-2 rounded-lg border border-border bg-muted/40 text-xs outline-none"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-foreground block mb-1">Target Foundation Model</label>
            <select
              value={selectedModelId}
              onChange={(e) => setSelectedModelId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-muted/40 text-xs outline-none"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.model_family.toUpperCase()} - {m.parameter_count >= 1e6 ? `${(m.parameter_count / 1e6).toFixed(0)}M` : m.parameter_count})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-foreground block mb-1">Training Dataset</label>
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-muted/40 text-xs outline-none"
            >
              {datasets.length === 0 ? (
                <option value="">Default Research Corpus (Built-in)</option>
              ) : (
                datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.num_samples_cleaned} samples - {d.license})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        {/* Hyperparameters Grid */}
        <div className="pt-2 border-t border-border/50">
          <h3 className="text-xs font-bold uppercase text-muted-foreground mb-3 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            Optimizer & Scheduler Parameters
          </h3>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="text-muted-foreground block mb-1">Learning Rate</label>
              <input
                type="text"
                value={lr}
                onChange={(e) => setLr(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Optimizer</label>
              <select
                value={optimizer}
                onChange={(e) => setOptimizer(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              >
                <option value="AdamW">AdamW</option>
                <option value="Lion">Lion</option>
                <option value="SGD">SGD with Momentum</option>
              </select>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Batch Size</label>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Max Steps</label>
              <input
                type="number"
                value={maxSteps}
                onChange={(e) => setMaxSteps(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Grad Accumulation</label>
              <input
                type="number"
                value={gradAccum}
                onChange={(e) => setGradAccum(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Weight Decay</label>
              <input
                type="text"
                value={weightDecay}
                onChange={(e) => setWeightDecay(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Random Seed</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              />
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-foreground block mb-1">Experiment Research Notes</label>
          <textarea
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Hypotheses, architecture adjustments, or observations..."
            className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none resize-none"
          />
        </div>

        <div className="flex items-center justify-between pt-2">
          <span className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Deterministic execution & MLflow checkpoint logging enabled
          </span>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-semibold transition-colors disabled:opacity-50 shadow-md shadow-cyan-500/20"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>{loading ? "Starting Run..." : "Launch Training Experiment"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};

