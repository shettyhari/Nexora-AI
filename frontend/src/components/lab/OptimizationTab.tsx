"use client";

import React, { useState } from "react";
import { LabCheckpoint, LabModel, LabOptimizationRun } from "@/types/lab";
import { Gauge, Zap, Layers, MemoryStick, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";

interface OptimizationTabProps {
  runs: LabOptimizationRun[];
  checkpoints: LabCheckpoint[];
  models: LabModel[];
  onRefresh: () => void;
}

export const OptimizationTab: React.FC<OptimizationTabProps> = ({
  runs,
  checkpoints,
  models,
  onRefresh,
}) => {
  const [checkpointId, setCheckpointId] = useState(checkpoints[0]?.id || "");
  const [modelName, setModelName] = useState(models[0]?.name || "NEXORA NANO");
  const [targetPrecision, setTargetPrecision] = useState("int8_dynamic");
  const [batchSize, setBatchSize] = useState("1");
  const [contextLength, setContextLength] = useState("128");
  const [kvCacheEnabled, setKvCacheEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const handleRunOptimization = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.runLabOptimization({
        checkpoint_id: checkpointId || undefined,
        model_name: modelName || "NEXORA NANO",
        target_precision: targetPrecision,
        batch_size: Number(batchSize),
        context_length: Number(contextLength),
        kv_cache_enabled: kvCacheEnabled,
      });
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Optimization benchmark failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Gauge className="w-5 h-5 text-cyan-400" />
          Quantization, KV-Cache & Inference Performance Workbench
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Benchmark real PyTorch precision conversion (FP32, FP16, BF16, INT8 Dynamic, INT4 NF4) with Time-To-First-Token (TTFT), decode throughput, peak memory, context scaling, and batching sweeps.
        </p>
      </div>

      {/* Benchmark Configuration Form */}
      <form onSubmit={handleRunOptimization} className="border border-border rounded-xl bg-card p-5 space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="text-muted-foreground block mb-1">Target Checkpoint</label>
            <select
              value={checkpointId}
              onChange={(e) => setCheckpointId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="">Built-in NEXORA NANO Baseline</option>
              {checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  Step {c.step} (v{c.version}) — {c.format}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Model Label</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            />
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Target Precision / Quantization</label>
            <select
              value={targetPrecision}
              onChange={(e) => setTargetPrecision(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none font-mono"
            >
              <option value="int8_dynamic">INT8 Dynamic Quantization (PyTorch)</option>
              <option value="fp16">FP16 Half Precision</option>
              <option value="bf16">BF16 Brain Float</option>
              <option value="int4_nf4">INT4 NF4 (4-bit Target)</option>
              <option value="fp32">FP32 Full Precision Baseline</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end">
          <div>
            <label className="text-muted-foreground block mb-1">Batch Size</label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            >
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="4">4</option>
              <option value="8">8</option>
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Context Length (Tokens)</label>
            <select
              value={contextLength}
              onChange={(e) => setContextLength(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            >
              <option value="64">64</option>
              <option value="128">128</option>
              <option value="256">256</option>
              <option value="512">512</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer py-2">
            <input
              type="checkbox"
              checked={kvCacheEnabled}
              onChange={(e) => setKvCacheEnabled(e.target.checked)}
              className="accent-cyan-500"
            />
            <span>Enable KV-Cache Reuse</span>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-semibold disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>{submitting ? "Benchmarking..." : "Quantize & Benchmark"}</span>
          </button>
        </div>
      </form>

      {/* Results List */}
      <div className="space-y-4">
        {runs.length === 0 ? (
          <div className="border border-border rounded-xl bg-card p-8 text-center text-xs text-muted-foreground">
            No optimization benchmarks executed yet. Run INT8 dynamic or BF16 benchmarking above to inspect real compression ratios, TTFT, and scaling behavior.
          </div>
        ) : (
          runs.map((run) => {
            const expanded = expandedRunId === run.id;
            return (
              <div key={run.id} className="border border-border rounded-xl bg-card p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-foreground">{run.model_name}</span>
                      <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                        {run.target_precision}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">
                        KV-Cache: {run.kv_cache_enabled ? "ON" : "OFF"}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                      Artifact: {run.artifact_path || "in-memory"} | Batch={run.batch_size}, Ctx={run.context_length}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => setExpandedRunId(expanded ? null : run.id)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded border border-border hover:bg-muted text-xs"
                  >
                    {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    <span>{expanded ? "Hide Scaling Sweeps" : "Scaling Sweeps"}</span>
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-[10px] text-muted-foreground block">Weight Compression</span>
                    <span className="font-mono font-bold text-emerald-400 text-sm">
                      {run.compression_ratio.toFixed(2)}x
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono block">
                      {run.original_size_mb.toFixed(2)} → {run.optimized_size_mb.toFixed(2)} MB
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-[10px] text-muted-foreground block">Time-To-First-Token</span>
                    <span className="font-mono font-bold text-cyan-400 text-sm">{run.ttft_ms.toFixed(2)} ms</span>
                    <span className="text-[10px] text-muted-foreground block">Prefill latency</span>
                  </div>

                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-[10px] text-muted-foreground block">Decode Throughput</span>
                    <span className="font-mono font-bold text-foreground text-sm">
                      {run.tokens_per_sec.toFixed(1)} tok/s
                    </span>
                    <span className="text-[10px] text-muted-foreground block">Autoregressive steps</span>
                  </div>

                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-[10px] text-muted-foreground block flex items-center gap-1">
                      <MemoryStick className="w-3 h-3" /> Peak Memory
                    </span>
                    <span className="font-mono font-bold text-indigo-300 text-sm">
                      {run.peak_memory_mb.toFixed(2)} MB
                    </span>
                    <span className="text-[10px] text-muted-foreground block">Weights + traced alloc</span>
                  </div>

                  <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-[10px] text-muted-foreground block flex items-center gap-1">
                      <Layers className="w-3 h-3" /> Status
                    </span>
                    <span className="font-mono font-bold text-emerald-400 capitalize text-sm">{run.status}</span>
                    <span className="text-[10px] text-muted-foreground block">
                      {new Date(run.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                {expanded && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-border/50 text-xs">
                    <div>
                      <h4 className="font-semibold text-foreground mb-2">Context Length Prefill Scaling</h4>
                      <div className="border border-border/60 rounded-lg overflow-hidden">
                        <table className="w-full text-left font-mono text-[11px]">
                          <thead className="bg-muted/40 text-muted-foreground">
                            <tr>
                              <th className="px-3 py-1.5">Seq Len</th>
                              <th className="px-3 py-1.5">Prefill (ms)</th>
                              <th className="px-3 py-1.5 text-right">Throughput</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/40">
                            {(run.context_scaling_results || []).map((row, idx) => (
                              <tr key={idx}>
                                <td className="px-3 py-1.5">{row.seq_len} tok</td>
                                <td className="px-3 py-1.5">{row.prefill_latency_ms} ms</td>
                                <td className="px-3 py-1.5 text-right text-cyan-400">{row.prefill_tok_per_sec} tok/s</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-semibold text-foreground mb-2">Dynamic Batch Scaling</h4>
                      <div className="border border-border/60 rounded-lg overflow-hidden">
                        <table className="w-full text-left font-mono text-[11px]">
                          <thead className="bg-muted/40 text-muted-foreground">
                            <tr>
                              <th className="px-3 py-1.5">Batch Size</th>
                              <th className="px-3 py-1.5">Latency (ms)</th>
                              <th className="px-3 py-1.5 text-right">Throughput</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/40">
                            {(run.batch_scaling_results || []).map((row, idx) => (
                              <tr key={idx}>
                                <td className="px-3 py-1.5">B={row.batch_size}</td>
                                <td className="px-3 py-1.5">{row.latency_ms} ms</td>
                                <td className="px-3 py-1.5 text-right text-emerald-400">
                                  {row.throughput_tok_per_sec} tok/s
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

