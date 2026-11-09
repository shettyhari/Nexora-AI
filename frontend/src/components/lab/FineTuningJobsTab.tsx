"use client";

import React, { useState, useEffect } from "react";
import { LabDataset, LabModel, LabTrainingJob, LicenseVerificationResult } from "@/types/lab";
import {
  Play,
  Pause,
  RotateCcw,
  Square,
  Terminal,
  ShieldCheck,
  AlertCircle,
  Cpu,
  Plus,
  RefreshCw,
  CheckCircle2
} from "lucide-react";
import { api } from "@/lib/api";

interface FineTuningJobsTabProps {
  models: LabModel[];
  datasets: LabDataset[];
  jobs: LabTrainingJob[];
  onRefresh: () => void;
}

export const FineTuningJobsTab: React.FC<FineTuningJobsTabProps> = ({
  models,
  datasets,
  jobs,
  onRefresh
}) => {
  const [name, setName] = useState("");
  const [baseModelId, setBaseModelId] = useState(models[0]?.id || "nexora-nano-v1");
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || "");
  const [trainingMethod, setTrainingMethod] = useState("lora");
  const [framework, setFramework] = useState("trl");
  const [intendedUse, setIntendedUse] = useState("research");
  const [maxSteps, setMaxSteps] = useState("8");
  const [lr, setLr] = useState("0.0005");
  const [loraRank, setLoraRank] = useState("4");
  const [autoStart, setAutoStart] = useState(true);

  const [licenseStatus, setLicenseStatus] = useState<LicenseVerificationResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedLogs, setSelectedLogs] = useState<{ jobId: string; status: string; logs: string } | null>(null);
  const [selectedJobMetrics, setSelectedJobMetrics] = useState<LabTrainingJob | null>(null);

  const selectedModel = models.find((m) => m.id === baseModelId);
  const selectedDataset = datasets.find((d) => d.id === datasetId);

  useEffect(() => {
    const checkLicense = async () => {
      try {
        const res = await api.verifyLabLicense({
          base_model_license: selectedModel?.license || "Apache-2.0",
          dataset_license: selectedDataset?.license || "Apache-2.0",
          intended_use: intendedUse,
          training_method: trainingMethod,
        });
        setLicenseStatus(res);
      } catch {
        // Ignore transient verification errors
      }
    };
    checkLicense();
  }, [selectedModel, selectedDataset, intendedUse, trainingMethod]);

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createLabTrainingJob({
        name: name || `${trainingMethod.toUpperCase()} - ${selectedModel?.name || "NEXORA"}`,
        base_model_id: baseModelId,
        dataset_id: datasetId || undefined,
        training_method: trainingMethod,
        framework,
        intended_use: intendedUse,
        hyperparameters: {
          max_steps: Number(maxSteps),
          learning_rate: Number(lr),
          batch_size: 2,
          grad_accum_steps: 1,
          seed: 42,
        },
        lora_config:
          trainingMethod === "lora" || trainingMethod === "qlora"
            ? {
                r: Number(loraRank),
                lora_alpha: Number(loraRank) * 2,
                lora_dropout: 0.05,
                target_modules: ["q_proj", "v_proj"],
                quantization_bits: trainingMethod === "qlora" ? 4 : null,
              }
            : undefined,
        auto_start: autoStart,
      });
      setName("");
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Failed to create training job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (
    action: "start" | "pause" | "resume" | "recover" | "cancel",
    jobId: string
  ) => {
    try {
      if (action === "start") await api.startLabTrainingJob(jobId);
      if (action === "pause") await api.pauseLabTrainingJob(jobId);
      if (action === "resume") await api.resumeLabTrainingJob(jobId);
      if (action === "recover") await api.recoverLabTrainingJob(jobId);
      if (action === "cancel") await api.cancelLabTrainingJob(jobId);
      onRefresh();
    } catch (err: any) {
      alert(`Job ${action} failed: ${err.message}`);
    }
  };

  const handleViewLogs = async (jobId: string) => {
    try {
      const res = await api.getLabTrainingJobLogs(jobId, 250);
      setSelectedLogs({ jobId, status: res.status, logs: res.logs });
    } catch (err: any) {
      alert(`Failed to load logs: ${err.message}`);
    }
  };

  const activeJobs = jobs.filter((j) => ["running", "queued", "scheduled", "paused"].includes(j.status));
  const completedJobs = jobs.filter((j) => j.status === "completed");
  const failedJobs = jobs.filter((j) => ["failed", "cancelled"].includes(j.status));

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Fine-Tuning Pipeline & Isolated Worker Jobs
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Launch authentic isolated PyTorch/Transformers/PEFT/TRL jobs (SFT, Instruction, LoRA, QLoRA, DPO, GRPO) with license enforcement and checkpoint validation.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            Active/Paused: {activeJobs.length}
          </span>
          <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Completed: {completedJobs.length}
          </span>
          <span className="px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20">
            Failed/Cancelled: {failedJobs.length}
          </span>
        </div>
      </div>

      {/* Job Creation Form */}
      <form onSubmit={handleCreateJob} className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Plus className="w-4 h-4 text-cyan-400" />
            Configure Fine-Tuning Run
          </h3>
          {licenseStatus && (
            <span
              className={`text-[11px] font-medium px-2.5 py-1 rounded-full border flex items-center gap-1.5 ${
                licenseStatus.approved
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/30"
              }`}
            >
              {licenseStatus.approved ? (
                <ShieldCheck className="w-3.5 h-3.5" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5" />
              )}
              {licenseStatus.approved ? "License Compatible" : "License Incompatible"}
            </span>
          )}
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {licenseStatus && !licenseStatus.approved && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            <strong>License Guard Blocked:</strong> {licenseStatus.errors.join(" ")}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="font-medium text-foreground block mb-1">Job Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., NEXORA NANO LoRA Instruct v1"
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            />
          </div>

          <div>
            <label className="font-medium text-foreground block mb-1">Authorized Base Model</label>
            <select
              value={baseModelId}
              onChange={(e) => setBaseModelId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.license})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="font-medium text-foreground block mb-1">Licensed Dataset</label>
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              {datasets.length === 0 ? (
                <option value="">Built-in Licensed Research Corpus (Apache-2.0)</option>
              ) : (
                datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} v{d.version} ({d.license})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-xs">
          <div>
            <label className="text-muted-foreground block mb-1">Training Method</label>
            <select
              value={trainingMethod}
              onChange={(e) => setTrainingMethod(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 outline-none uppercase font-semibold"
            >
              <option value="sft">SFT (Supervised)</option>
              <option value="instruction">Instruction Tuning</option>
              <option value="lora">LoRA (PEFT)</option>
              <option value="qlora">QLoRA (4-bit PEFT)</option>
              <option value="dpo">DPO (Preference)</option>
              <option value="grpo">GRPO (Policy RL)</option>
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Framework Stack</label>
            <select
              value={framework}
              onChange={(e) => setFramework(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="trl">TRL + Transformers</option>
              <option value="peft">PEFT + Accelerate</option>
              <option value="deepspeed">DeepSpeed ZeRO-2</option>
              <option value="nemo">NVIDIA NeMo</option>
              <option value="pytorch">PyTorch Native</option>
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Intended Use</label>
            <select
              value={intendedUse}
              onChange={(e) => setIntendedUse(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="research">Research / Academic</option>
              <option value="internal">Internal Enterprise</option>
              <option value="commercial">Commercial Deployment</option>
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Max Steps</label>
            <input
              type="number"
              min={1}
              max={200}
              value={maxSteps}
              onChange={(e) => setMaxSteps(e.target.value)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            />
          </div>

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
            <label className="text-muted-foreground block mb-1">LoRA Rank (r)</label>
            <input
              type="number"
              min={2}
              max={64}
              value={loraRank}
              onChange={(e) => setLoraRank(e.target.value)}
              disabled={!["lora", "qlora"].includes(trainingMethod)}
              className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none disabled:opacity-40"
            />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-border/40">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={autoStart}
              onChange={(e) => setAutoStart(e.target.checked)}
              className="accent-cyan-500"
            />
            <span>Immediately spawn isolated worker subprocess after validation</span>
          </label>

          <button
            type="submit"
            disabled={submitting || (licenseStatus != null && !licenseStatus.approved)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-semibold transition-colors disabled:opacity-40"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{submitting ? "Dispatching Worker..." : "Create & Schedule Fine-Tuning Job"}</span>
          </button>
        </div>
      </form>

      {/* Jobs Table */}
      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-muted/30">
          <h3 className="text-xs font-bold uppercase text-muted-foreground">Orchestration Queue & Execution History</h3>
          <button
            onClick={onRefresh}
            className="flex items-center gap-1 text-[11px] text-cyan-400 hover:underline"
          >
            <RefreshCw className="w-3 h-3" /> Sync Workers
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground font-semibold border-b border-border">
              <tr>
                <th className="px-4 py-2.5">Job & Method</th>
                <th className="px-4 py-2.5">Status & Worker</th>
                <th className="px-4 py-2.5">Progress</th>
                <th className="px-4 py-2.5">Train / Val Loss</th>
                <th className="px-4 py-2.5">Checkpoint Gate</th>
                <th className="px-4 py-2.5 text-right">Controls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-muted-foreground">
                    No training jobs scheduled yet. Configure a run above to launch an isolated training worker.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-foreground">{job.name}</div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        {job.training_method.toUpperCase()} / {job.framework} | {job.base_model_name}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium capitalize border ${
                          job.status === "completed"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : job.status === "running"
                            ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                            : job.status === "failed"
                            ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                        }`}
                      >
                        {job.status}
                      </span>
                      <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                        PID: {job.worker_pid || "—"} | {job.device_type.toUpperCase()}
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono">
                      <div>
                        {job.current_step} / {job.total_steps} steps
                      </div>
                      <div className="text-[10px] text-cyan-400">
                        {job.tokens_per_sec > 0 ? `${job.tokens_per_sec} tok/s` : `${job.tokens_processed} tok`}
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono">
                      <div>
                        {job.current_train_loss != null ? job.current_train_loss.toFixed(4) : "—"} /{" "}
                        <span className="text-emerald-400">
                          {job.current_val_loss != null ? job.current_val_loss.toFixed(4) : "—"}
                        </span>
                      </div>
                      {job.error_message && (
                        <div className="text-[10px] text-rose-400 truncate max-w-[180px]" title={job.error_message}>
                          {job.error_message}
                        </div>
                      )}
                    </td>

                    <td className="px-4 py-3">
                      {job.checkpoint_validated ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Validated
                        </span>
                      ) : (
                        <span className="text-[11px] text-muted-foreground">Pending</span>
                      )}
                    </td>

                    <td className="px-4 py-3 text-right space-x-1 whitespace-nowrap">
                      {job.status === "queued" && (
                        <button
                          onClick={() => handleAction("start", job.id)}
                          className="px-2 py-1 rounded bg-cyan-500 hover:bg-cyan-600 text-white text-[11px]"
                        >
                          Start
                        </button>
                      )}
                      {job.status === "running" && (
                        <>
                          <button
                            onClick={() => handleAction("pause", job.id)}
                            className="px-2 py-1 rounded border border-amber-500/30 text-amber-400 text-[11px]"
                          >
                            <Pause className="w-3 h-3 inline mr-0.5" /> Pause
                          </button>
                          <button
                            onClick={() => handleAction("cancel", job.id)}
                            className="px-2 py-1 rounded border border-rose-500/30 text-rose-400 text-[11px]"
                          >
                            <Square className="w-3 h-3 inline mr-0.5" /> Cancel
                          </button>
                        </>
                      )}
                      {job.status === "paused" && (
                        <button
                          onClick={() => handleAction("resume", job.id)}
                          className="px-2 py-1 rounded bg-emerald-500 hover:bg-emerald-600 text-white text-[11px]"
                        >
                          Resume
                        </button>
                      )}
                      {job.status === "failed" && (
                        <button
                          onClick={() => handleAction("recover", job.id)}
                          className="px-2 py-1 rounded bg-amber-500 hover:bg-amber-600 text-white text-[11px]"
                        >
                          <RotateCcw className="w-3 h-3 inline mr-0.5" /> Recover
                        </button>
                      )}
                      <button
                        onClick={() => setSelectedJobMetrics(job)}
                        className="px-2 py-1 rounded border border-border hover:bg-muted text-[11px]"
                      >
                        Metrics
                      </button>
                      <button
                        onClick={() => handleViewLogs(job.id)}
                        className="px-2 py-1 rounded border border-border hover:bg-muted text-[11px]"
                      >
                        <Terminal className="w-3 h-3 inline mr-0.5" /> Logs
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Worker Logs Modal */}
      {selectedLogs && (
        <div className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-3xl p-5 shadow-2xl space-y-3 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground font-mono">
                Isolated Worker Logs — {selectedLogs.jobId.slice(0, 8)} ({selectedLogs.status})
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleViewLogs(selectedLogs.jobId)}
                  className="px-2.5 py-1 rounded bg-cyan-500/15 text-cyan-400 text-xs"
                >
                  Refresh
                </button>
                <button
                  onClick={() => setSelectedLogs(null)}
                  className="px-2.5 py-1 rounded bg-muted text-xs"
                >
                  Close
                </button>
              </div>
            </div>
            <pre className="flex-1 overflow-y-auto p-3 rounded-lg bg-zinc-950 text-emerald-300 font-mono text-[11px] whitespace-pre-wrap border border-border">
              {selectedLogs.logs || "No log lines emitted yet..."}
            </pre>
          </div>
        </div>
      )}

      {/* Step Metrics Modal */}
      {selectedJobMetrics && (
        <div className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-2xl p-5 shadow-2xl space-y-3 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">{selectedJobMetrics.name} — Step Metrics</h3>
              <button onClick={() => setSelectedJobMetrics(null)} className="px-2.5 py-1 rounded bg-muted text-xs">
                Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1.5 font-mono text-xs">
              {(selectedJobMetrics.loss_history || []).map((pt, idx) => (
                <div
                  key={idx}
                  className="grid grid-cols-5 gap-2 p-2 rounded bg-muted/30 border border-border/50"
                >
                  <span>Step #{pt.step}</span>
                  <span>Train: {pt.train_loss.toFixed(4)}</span>
                  <span className="text-emerald-400">Val: {pt.val_loss.toFixed(4)}</span>
                  <span className="text-cyan-400">{pt.tokens_per_sec || 0} tok/s</span>
                  <span className="text-muted-foreground">lr {Number(pt.lr).toExponential(1)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

