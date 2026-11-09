"use client";

import React, { useState } from "react";
import { LabCheckpoint } from "@/types/lab";
import {
  HardDrive,
  CheckCircle2,
  ShieldCheck,
  Download,
  Award,
  RotateCcw,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";

interface CheckpointBrowserTabProps {
  checkpoints: LabCheckpoint[];
  onRefresh?: () => void;
}

export const CheckpointBrowserTab: React.FC<CheckpointBrowserTabProps> = ({
  checkpoints,
  onRefresh,
}) => {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: "ok" | "err"; message: string } | null>(null);

  const handleValidate = async (ckpt: LabCheckpoint) => {
    setBusyId(ckpt.id);
    setFeedback(null);
    try {
      const res = await api.validateLabCheckpoint(ckpt.id);
      const rep = res.validation_report || {};
      if (rep.validated) {
        setFeedback({
          type: "ok",
          message: `Checkpoint v${ckpt.version} (Step #${ckpt.step}) validated: ${rep.tensor_count} tensors, 0 NaN/Inf, SHA-256 verified.`,
        });
      } else {
        setFeedback({
          type: "err",
          message: `Checkpoint v${ckpt.version} validation failed: ${rep.error || "integrity mismatch"}`,
        });
      }
      onRefresh?.();
    } catch (err: any) {
      setFeedback({ type: "err", message: err.message || "Validation request failed" });
    } finally {
      setBusyId(null);
    }
  };

  const handleExport = async (ckpt: LabCheckpoint) => {
    setBusyId(ckpt.id);
    setFeedback(null);
    try {
      const res = await api.exportLabCheckpoint(ckpt.id, "safetensors");
      const exp = res.export || {};
      setFeedback({
        type: "ok",
        message: `Exported SafeTensors bundle for Step #${ckpt.step} to ${exp.export_dir} (${exp.files?.length || 0} files).`,
      });
      onRefresh?.();
    } catch (err: any) {
      setFeedback({ type: "err", message: err.message || "Export failed" });
    } finally {
      setBusyId(null);
    }
  };

  const handleRollback = async (ckpt: LabCheckpoint) => {
    setBusyId(ckpt.id);
    setFeedback(null);
    try {
      const res = await api.rollbackLabCheckpoint(ckpt.id, undefined, "Dashboard rollback action");
      setFeedback({
        type: "ok",
        message: `Active rollback target switched to checkpoint v${res.version} (${ckpt.id.slice(0, 8)}).`,
      });
      onRefresh?.();
    } catch (err: any) {
      setFeedback({ type: "err", message: err.message || "Rollback failed" });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-cyan-400" />
          Model Checkpoint Browser, Validation &amp; SafeTensors Export
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Inspect saved training steps, PEFT adapters, SHA-256 integrity digests, run strict weight reload validation, export release bundles, and rollback.
        </p>
      </div>

      {feedback && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
            feedback.type === "ok"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/30 text-rose-300"
          }`}
        >
          {feedback.type === "ok" ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
              <tr>
                <th className="px-4 py-3">Step &amp; Version</th>
                <th className="px-4 py-3">Artifact Type &amp; Milestone</th>
                <th className="px-4 py-3">Train / Val Loss</th>
                <th className="px-4 py-3">Perplexity</th>
                <th className="px-4 py-3">Validation &amp; SHA-256</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {checkpoints.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-muted-foreground">
                    No checkpoints saved yet. Checkpoints are automatically logged when training or fine-tuning runs save states.
                  </td>
                </tr>
              ) : (
                checkpoints.map((ckpt) => (
                  <tr key={ckpt.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono">
                      <span className="font-bold text-foreground">Step #{ckpt.step}</span>
                      <span className="text-[10px] text-cyan-400 block">
                        v{ckpt.version || "1.0.0"} · Epoch {ckpt.epoch}
                      </span>
                    </td>

                    <td className="px-4 py-3 space-y-1">
                      <div className="flex flex-wrap items-center gap-1">
                        {ckpt.is_best && (
                          <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                            <Award className="w-3 h-3" /> Best Val
                          </span>
                        )}
                        {ckpt.is_adapter_only && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                            PEFT Adapter
                          </span>
                        )}
                        {ckpt.is_active_rollback_target && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                            Active Rollback
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground">
                        {ckpt.format || "pytorch"}
                      </div>
                    </td>

                    <td className="px-4 py-3 font-mono">
                      <span>{ckpt.train_loss.toFixed(4)}</span> /{" "}
                      <span className="font-semibold text-emerald-400">{ckpt.val_loss.toFixed(4)}</span>
                    </td>

                    <td className="px-4 py-3 font-mono font-bold text-cyan-400">
                      {ckpt.perplexity.toFixed(2)}
                    </td>

                    <td className="px-4 py-3 space-y-1">
                      <div>
                        {ckpt.validated ? (
                          <span className="inline-flex items-center gap-1 text-emerald-400 text-[10px] font-semibold">
                            <ShieldCheck className="w-3.5 h-3.5" /> Verified Weights
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-400">Unvalidated</span>
                        )}
                      </div>
                      <div
                        className="font-mono text-[10px] text-muted-foreground truncate max-w-[160px]"
                        title={ckpt.weights_sha256}
                      >
                        {ckpt.weights_sha256 ? `${ckpt.weights_sha256.slice(0, 14)}...` : "—"}
                      </div>
                      {ckpt.export_path && (
                        <div className="text-[10px] text-cyan-400 font-mono truncate max-w-[160px]" title={ckpt.export_path}>
                          Exported Bundle
                        </div>
                      )}
                    </td>

                    <td className="px-4 py-3 text-right space-x-1 whitespace-nowrap">
                      <button
                        type="button"
                        disabled={busyId === ckpt.id}
                        onClick={() => handleValidate(ckpt)}
                        className="px-2 py-1 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 text-[11px] disabled:opacity-40"
                        title="Verify SHA-256, tensor reload & forward pass"
                      >
                        <ShieldCheck className="w-3 h-3 inline mr-0.5" /> Validate
                      </button>
                      <button
                        type="button"
                        disabled={busyId === ckpt.id}
                        onClick={() => handleExport(ckpt)}
                        className="px-2 py-1 rounded border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 text-[11px] disabled:opacity-40"
                        title="Export SafeTensors / HF bundle"
                      >
                        <Download className="w-3 h-3 inline mr-0.5" /> Export
                      </button>
                      <button
                        type="button"
                        disabled={busyId === ckpt.id}
                        onClick={() => handleRollback(ckpt)}
                        className="px-2 py-1 rounded border border-border hover:bg-muted text-[11px] disabled:opacity-40"
                        title="Promote this checkpoint as active rollback target"
                      >
                        <RotateCcw className="w-3 h-3 inline mr-0.5" /> Rollback
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
