"use client";

import React from "react";
import { LabCheckpoint } from "@/types/lab";
import { HardDrive, CheckCircle2, ShieldCheck, Download, Award } from "lucide-react";

interface CheckpointBrowserTabProps {
  checkpoints: LabCheckpoint[];
}

export const CheckpointBrowserTab: React.FC<CheckpointBrowserTabProps> = ({ checkpoints }) => {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-cyan-400" />
          Model Checkpoint Browser & Weight Artifacts
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Inspect saved training steps, validation perplexity milestones, and cryptographically verified weights SHA-256 digests.
        </p>
      </div>

      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
              <tr>
                <th className="px-4 py-3">Step & Epoch</th>
                <th className="px-4 py-3">Milestone</th>
                <th className="px-4 py-3">Train Loss</th>
                <th className="px-4 py-3">Val Loss</th>
                <th className="px-4 py-3">Perplexity</th>
                <th className="px-4 py-3">Weights SHA-256 Digest</th>
                <th className="px-4 py-3 text-right">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {checkpoints.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    No checkpoints saved yet. Checkpoints are automatically logged when validation loss improves during training runs.
                  </td>
                </tr>
              ) : (
                checkpoints.map((ckpt) => (
                  <tr key={ckpt.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono">
                      <span className="font-bold text-foreground">Step #{ckpt.step}</span>
                      <span className="text-[10px] text-muted-foreground block">Epoch {ckpt.epoch}</span>
                    </td>

                    <td className="px-4 py-3">
                      {ckpt.is_best ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                          <Award className="w-3 h-3" />
                          Best Val Loss
                        </span>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">Periodic Checkpoint</span>
                      )}
                    </td>

                    <td className="px-4 py-3 font-mono">{ckpt.train_loss.toFixed(4)}</td>
                    <td className="px-4 py-3 font-mono font-semibold text-emerald-400">
                      {ckpt.val_loss.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-cyan-400">
                      {ckpt.perplexity.toFixed(2)}
                    </td>

                    <td className="px-4 py-3 font-mono text-[11px] text-muted-foreground">
                      <span className="truncate max-w-[180px] inline-block" title={ckpt.weights_sha256}>
                        {ckpt.weights_sha256 ? `${ckpt.weights_sha256.slice(0, 16)}...` : "—"}
                      </span>
                    </td>

                    <td className="px-4 py-3 text-right text-muted-foreground text-[11px]">
                      {new Date(ckpt.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
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
