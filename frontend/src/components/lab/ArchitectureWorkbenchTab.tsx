"use client";

import React, { useState, useEffect } from "react";
import { ArchitectureConfig, ArchitectureAnalysis } from "@/types/lab";
import { Cpu, Zap, HardDrive, Calculator, Check, ArrowRight, Layers, Sliders } from "lucide-react";
import { api } from "@/lib/api";

export const ArchitectureWorkbenchTab: React.FC = () => {
  const [config, setConfig] = useState<ArchitectureConfig>({
    vocab_size: 32000,
    d_model: 512,
    n_layers: 8,
    n_heads: 8,
    n_kv_heads: 4,
    max_seq_len: 2048,
    norm_type: "rmsnorm",
    activation: "swiglu",
    rotary_base: 10000.0,
    tie_word_embeddings: false,
    precision: "fp32"
  });

  const [analysis, setAnalysis] = useState<ArchitectureAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  // Auto-recalculate on change
  useEffect(() => {
    let active = true;
    const fetchAnalysis = async () => {
      setLoading(true);
      try {
        const res = await api.analyzeArchitecture(config);
        if (active) setAnalysis(res);
      } catch (err) {
        console.error("Architecture analysis error:", err);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchAnalysis();
    return () => {
      active = false;
    };
  }, [config]);

  const loadPreset = (preset: "nano" | "core" | "pro") => {
    if (preset === "nano") {
      setConfig({
        vocab_size: 32000,
        d_model: 512,
        n_layers: 8,
        n_heads: 8,
        n_kv_heads: 4,
        max_seq_len: 2048,
        norm_type: "rmsnorm",
        activation: "swiglu",
        rotary_base: 10000.0,
        tie_word_embeddings: false,
        precision: "fp32"
      });
    } else if (preset === "core") {
      setConfig({
        vocab_size: 50000,
        d_model: 2048,
        n_layers: 24,
        n_heads: 16,
        n_kv_heads: 8,
        max_seq_len: 4096,
        norm_type: "rmsnorm",
        activation: "swiglu",
        rotary_base: 50000.0,
        tie_word_embeddings: false,
        precision: "bf16"
      });
    } else {
      setConfig({
        vocab_size: 64000,
        d_model: 4096,
        n_layers: 36,
        n_heads: 32,
        n_kv_heads: 8,
        max_seq_len: 8192,
        norm_type: "rmsnorm",
        activation: "swiglu",
        rotary_base: 500000.0,
        tie_word_embeddings: false,
        precision: "bf16"
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Presets */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Transformer Architectural Workbench & FLOPs Calculator
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure RoPE, Multi-Query/Grouped-Query Attention (GQA), SwiGLU FFN dimensions, and compute exact analytical parameter scaling.
          </p>
        </div>

        {/* Roadmap Presets */}
        <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-xl border border-border">
          <button
            onClick={() => loadPreset("nano")}
            className="px-2.5 py-1 rounded-lg text-xs font-medium hover:bg-card hover:text-cyan-400 transition-colors"
          >
            NANO Preset
          </button>
          <button
            onClick={() => loadPreset("core")}
            className="px-2.5 py-1 rounded-lg text-xs font-medium hover:bg-card hover:text-indigo-400 transition-colors"
          >
            CORE Preset
          </button>
          <button
            onClick={() => loadPreset("pro")}
            className="px-2.5 py-1 rounded-lg text-xs font-medium hover:bg-card hover:text-purple-400 transition-colors"
          >
            PRO Preset
          </button>
        </div>
      </div>

      {/* Main Grid: Controls (1 col) + Analytics Display (2 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls Column */}
        <div className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            Hyperparameters
          </h3>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Hidden Dim (d_model)</span>
              <span className="font-mono font-bold text-foreground">{config.d_model}</span>
            </div>
            <input
              type="range"
              min="128"
              max="4096"
              step="128"
              value={config.d_model}
              onChange={(e) => setConfig({ ...config, d_model: Number(e.target.value) })}
              className="w-full accent-cyan-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Layers (n_layers)</span>
              <span className="font-mono font-bold text-foreground">{config.n_layers}</span>
            </div>
            <input
              type="range"
              min="2"
              max="48"
              step="2"
              value={config.n_layers}
              onChange={(e) => setConfig({ ...config, n_layers: Number(e.target.value) })}
              className="w-full accent-cyan-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Query Heads</label>
              <select
                value={config.n_heads}
                onChange={(e) => setConfig({ ...config, n_heads: Number(e.target.value) })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
              >
                <option value={4}>4 Heads</option>
                <option value={8}>8 Heads</option>
                <option value={16}>16 Heads</option>
                <option value={32}>32 Heads</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">KV Heads (GQA)</label>
              <select
                value={config.n_kv_heads}
                onChange={(e) => setConfig({ ...config, n_kv_heads: Number(e.target.value) })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
              >
                <option value={1}>1 (MQA)</option>
                <option value={2}>2 Heads</option>
                <option value={4}>4 Heads</option>
                <option value={8}>8 Heads</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Vocab Size</label>
              <input
                type="number"
                value={config.vocab_size}
                onChange={(e) => setConfig({ ...config, vocab_size: Number(e.target.value) })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Context Length</label>
              <input
                type="number"
                value={config.max_seq_len}
                onChange={(e) => setConfig({ ...config, max_seq_len: Number(e.target.value) })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Activation</label>
              <select
                value={config.activation}
                onChange={(e) => setConfig({ ...config, activation: e.target.value as any })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none uppercase font-semibold"
              >
                <option value="swiglu">SwiGLU</option>
                <option value="gelu">GELU</option>
                <option value="silu">SiLU</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Normalization</label>
              <select
                value={config.norm_type}
                onChange={(e) => setConfig({ ...config, norm_type: e.target.value as any })}
                className="w-full px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none uppercase font-semibold"
              >
                <option value="rmsnorm">RMSNorm</option>
                <option value="layernorm">LayerNorm</option>
              </select>
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
              <input
                type="checkbox"
                checked={config.tie_word_embeddings}
                onChange={(e) => setConfig({ ...config, tie_word_embeddings: e.target.checked })}
                className="rounded border-border text-cyan-500 focus:ring-0"
              />
              <span>Tie Input Embeddings & LM Head</span>
            </label>
          </div>
        </div>

        {/* Analytics Display Column (2 cols) */}
        <div className="lg:col-span-2 space-y-5">
          {/* Top Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="border border-border rounded-xl bg-card p-4 shadow-sm">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                Total Parameter Count
              </span>
              <span className="font-mono font-bold text-2xl text-cyan-400 mt-1 block">
                {analysis?.total_parameters_formatted || "Calculating..."}
              </span>
              <span className="text-[11px] text-muted-foreground font-mono mt-0.5 block">
                {analysis?.total_parameters.toLocaleString()} exact params
              </span>
            </div>

            <div className="border border-border rounded-xl bg-card p-4 shadow-sm">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                Non-Embedding Parameters
              </span>
              <span className="font-mono font-bold text-2xl text-indigo-400 mt-1 block">
                {analysis?.non_embedding_formatted || "..."}
              </span>
              <span className="text-[11px] text-muted-foreground mt-0.5 block">Transformer core layers</span>
            </div>

            <div className="border border-border rounded-xl bg-card p-4 shadow-sm">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                Model Weights Footprint
              </span>
              <span className="font-mono font-bold text-2xl text-emerald-400 mt-1 block">
                {analysis?.memory.weights_gb ? `${analysis.memory.weights_gb} GB` : "..."}
              </span>
              <span className="text-[11px] text-muted-foreground mt-0.5 block">
                {analysis?.memory.precision.toUpperCase()} storage footprint
              </span>
            </div>
          </div>

          {/* Component Breakdown Card */}
          <div className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Layer-by-Layer Architectural Breakdown
            </h3>

            {analysis && (
              <div className="space-y-3">
                {/* Visual Ratio Bar */}
                <div className="w-full h-3 rounded-full bg-muted overflow-hidden flex">
                  <div
                    style={{
                      width: `${(analysis.breakdown.token_embeddings / analysis.total_parameters) * 100}%`
                    }}
                    className="bg-cyan-500"
                    title="Embeddings"
                  />
                  <div
                    style={{
                      width: `${(analysis.breakdown.attention_all_layers / analysis.total_parameters) * 100}%`
                    }}
                    className="bg-indigo-500"
                    title="Attention"
                  />
                  <div
                    style={{
                      width: `${(analysis.breakdown.ffn_all_layers / analysis.total_parameters) * 100}%`
                    }}
                    className="bg-purple-500"
                    title="Feed-Forward"
                  />
                  {!config.tie_word_embeddings && (
                    <div
                      style={{
                        width: `${(analysis.breakdown.lm_head / analysis.total_parameters) * 100}%`
                      }}
                      className="bg-emerald-500"
                      title="LM Head"
                    />
                  )}
                </div>

                {/* Table Breakdown */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-2">
                  <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-cyan-400 font-semibold block">Token Embeddings</span>
                    <span className="font-mono font-bold text-foreground text-sm">
                      {(analysis.breakdown.token_embeddings / 1e6).toFixed(2)}M
                    </span>
                    <span className="text-[10px] text-muted-foreground block">
                      {((analysis.breakdown.token_embeddings / analysis.total_parameters) * 100).toFixed(1)}% of model
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-indigo-400 font-semibold block">Attention Layers</span>
                    <span className="font-mono font-bold text-foreground text-sm">
                      {(analysis.breakdown.attention_all_layers / 1e6).toFixed(2)}M
                    </span>
                    <span className="text-[10px] text-muted-foreground block">
                      Across {config.n_layers} blocks
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-purple-400 font-semibold block">SwiGLU FFN</span>
                    <span className="font-mono font-bold text-foreground text-sm">
                      {(analysis.breakdown.ffn_all_layers / 1e6).toFixed(2)}M
                    </span>
                    <span className="text-[10px] text-muted-foreground block">3-projection Swish</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                    <span className="text-emerald-400 font-semibold block">LM Output Head</span>
                    <span className="font-mono font-bold text-foreground text-sm">
                      {analysis.breakdown.lm_head > 0
                        ? `${(analysis.breakdown.lm_head / 1e6).toFixed(2)}M`
                        : "Tied (0M)"}
                    </span>
                    <span className="text-[10px] text-muted-foreground block">
                      {config.tie_word_embeddings ? "Shared with input" : "Dedicated projection"}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* FLOPs & Scaling Estimates */}
          {analysis && (
            <div className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Calculator className="w-4 h-4 text-cyan-400" />
                Training FLOPs & Scaling Law Estimates
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-muted/40">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Training FLOPs / Token
                  </span>
                  <span className="font-mono font-bold text-foreground text-sm">
                    {(analysis.flops.training_flops_per_token / 1e9).toFixed(2)} GFLOPs
                  </span>
                  <span className="text-[10px] text-muted-foreground block">~6 * Params per token</span>
                </div>

                <div className="p-3 rounded-lg bg-muted/40">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Chinchilla Optimal Budget
                  </span>
                  <span className="font-mono font-bold text-foreground text-sm">
                    {(analysis.flops.chinchilla_recommended_tokens / 1e9).toFixed(2)}B Tokens
                  </span>
                  <span className="text-[10px] text-muted-foreground block">20 tokens per param</span>
                </div>

                <div className="p-3 rounded-lg bg-muted/40">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Chinchilla Training Compute
                  </span>
                  <span className="font-mono font-bold text-foreground text-sm">
                    {analysis.flops.chinchilla_training_petaflops.toLocaleString()} PetaFLOPs
                  </span>
                  <span className="text-[10px] text-muted-foreground block">Total optimal pretraining FLOPs</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
