"use client";

import React, { useState } from "react";
import { LabModel } from "@/types/lab";
import { Layers, Plus, Cpu, ShieldCheck, CheckCircle2, Clock, Box, Sparkles, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface ModelRegistryTabProps {
  models: LabModel[];
  onRefresh: () => void;
}

export const ModelRegistryTab: React.FC<ModelRegistryTabProps> = ({ models, onRefresh }) => {
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [family, setFamily] = useState<"nano" | "core" | "pro" | "custom">("custom");
  const [description, setDescription] = useState("");
  const [dModel, setDModel] = useState(512);
  const [nLayers, setNLayers] = useState(8);
  const [nHeads, setNHeads] = useState(8);
  const [nKvHeads, setNKvHeads] = useState(4);
  const [vocabSize, setVocabSize] = useState(32000);
  const [maxSeqLen, setMaxSeqLen] = useState(2048);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.registerLabModel({
        name,
        version: "0.1.0-research",
        model_family: family,
        architecture_type: "decoder-only",
        base_model: "scratch",
        license: "Proprietary-Research",
        description,
        architecture_config: {
          vocab_size: Number(vocabSize),
          d_model: Number(dModel),
          n_layers: Number(nLayers),
          n_heads: Number(nHeads),
          n_kv_heads: Number(nKvHeads),
          max_seq_len: Number(maxSeqLen),
          norm_type: "rmsnorm",
          activation: "swiglu",
          rotary_base: 10000.0,
          tie_word_embeddings: false,
          precision: "fp32"
        }
      });
      setShowModal(false);
      setName("");
      setDescription("");
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Failed to register model");
    } finally {
      setLoading(false);
    }
  };

  const getFamilyBadge = (fam: string) => {
    switch (fam) {
      case "nano":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "core":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
      case "pro":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      default:
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    }
  };

  return (
    <div className="space-y-6">
      {/* Top action row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            Proprietary Foundation Model Catalog
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Roadmap families and independently registered research decoder-only Transformer targets.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Register Research Model</span>
        </button>
      </div>

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {models.map((model) => {
          const cfg = model.architecture_config || {};
          const isRoadmap = ["nano", "core", "pro"].includes(model.model_family);

          return (
            <div
              key={model.id}
              className="rounded-xl border border-border bg-card p-5 flex flex-col justify-between hover:border-cyan-500/30 transition-all shadow-sm group"
            >
              <div>
                {/* Header */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span
                      className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${getFamilyBadge(
                        model.model_family
                      )}`}
                    >
                      NEXORA {model.model_family.toUpperCase()}
                    </span>
                    <h3 className="font-bold text-base text-foreground mt-1.5 group-hover:text-cyan-400 transition-colors">
                      {model.name}
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    v{model.version}
                  </span>
                </div>

                <p className="text-xs text-muted-foreground mt-2 line-clamp-3">
                  {model.description || "Proprietary decoder-only Transformer research architecture."}
                </p>

                {/* Architecture Metrics Grid */}
                <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-border/50 text-xs">
                  <div className="bg-muted/40 p-2 rounded-lg">
                    <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                      Parameters
                    </span>
                    <span className="font-mono font-bold text-foreground">
                      {model.parameter_count >= 1e9
                        ? `${(model.parameter_count / 1e9).toFixed(2)}B`
                        : model.parameter_count >= 1e6
                        ? `${(model.parameter_count / 1e6).toFixed(1)}M`
                        : `${model.parameter_count.toLocaleString()}`}
                    </span>
                  </div>

                  <div className="bg-muted/40 p-2 rounded-lg">
                    <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                      Context Length
                    </span>
                    <span className="font-mono font-bold text-foreground">
                      {(cfg.max_seq_len || 2048).toLocaleString()} tokens
                    </span>
                  </div>

                  <div className="bg-muted/40 p-2 rounded-lg">
                    <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                      Hidden Width
                    </span>
                    <span className="font-mono font-bold text-foreground">d_model = {cfg.d_model || 512}</span>
                  </div>

                  <div className="bg-muted/40 p-2 rounded-lg">
                    <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                      Layers & Heads
                    </span>
                    <span className="font-mono font-bold text-foreground">
                      {cfg.n_layers || 8}L / {cfg.n_heads || 8}H
                    </span>
                  </div>
                </div>

                {/* Technical Features Tags */}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    Norm: {cfg.norm_type || "rmsnorm"}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    Act: {cfg.activation || "swiglu"}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    GQA: {cfg.n_kv_heads ? `${cfg.n_heads / cfg.n_kv_heads}:1` : "MHA"}
                  </span>
                </div>
              </div>

              {/* Footer */}
              <div className="mt-5 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5 capitalize">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      model.deployment_status === "registered"
                        ? "bg-cyan-500"
                        : model.deployment_status === "deployed"
                        ? "bg-emerald-500"
                        : "bg-amber-500"
                    }`}
                  />
                  <span>{model.deployment_status}</span>
                </span>
                <span className="text-[11px] truncate max-w-[140px]">{model.license}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Registration Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-foreground mb-1">Register New Foundation Model</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Define architectural hyperparameters for a new decoder-only Transformer target.
            </p>

            {error && (
              <div className="p-3 mb-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleRegister} className="space-y-3.5">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Model Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., NEXORA NANO v2-Math"
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Model Family</label>
                  <select
                    value={family}
                    onChange={(e) => setFamily(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  >
                    <option value="nano">NEXORA NANO</option>
                    <option value="core">NEXORA CORE</option>
                    <option value="pro">NEXORA PRO</option>
                    <option value="custom">Custom Research</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Vocabulary Size</label>
                  <input
                    type="number"
                    value={vocabSize}
                    onChange={(e) => setVocabSize(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Hidden Dim (d_model)</label>
                  <input
                    type="number"
                    value={dModel}
                    onChange={(e) => setDModel(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Transformer Layers</label>
                  <input
                    type="number"
                    value={nLayers}
                    onChange={(e) => setNLayers(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Q Heads</label>
                  <input
                    type="number"
                    value={nHeads}
                    onChange={(e) => setNHeads(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">KV Heads (GQA)</label>
                  <input
                    type="number"
                    value={nKvHeads}
                    onChange={(e) => setNKvHeads(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Context Length</label>
                  <input
                    type="number"
                    value={maxSeqLen}
                    onChange={(e) => setMaxSeqLen(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Research Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Goals, target domains, and intended benchmarks..."
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none resize-none"
                />
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
                  {loading ? "Registering..." : "Register Model"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
