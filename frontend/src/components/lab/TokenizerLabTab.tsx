"use client";

import React, { useState } from "react";
import { LabTokenizer } from "@/types/lab";
import { Sliders, Play, Plus, CheckCircle, BarChart3, Globe, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

interface TokenizerLabTabProps {
  tokenizers: LabTokenizer[];
  onRefresh: () => void;
}

export const TokenizerLabTab: React.FC<TokenizerLabTabProps> = ({ tokenizers, onRefresh }) => {
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [name, setName] = useState("");
  const [algorithm, setAlgorithm] = useState<"bpe" | "unigram_sentencepiece">("bpe");
  const [targetVocabSize, setTargetVocabSize] = useState(1000);
  const [sampleCorpus, setSampleCorpus] = useState("");
  const [loading, setLoading] = useState(false);

  // Evaluator state
  const [testText, setTestText] = useState(
    "NEXORA foundation models utilize Byte-Pair Encoding for compact and expressive subword tokenization."
  );
  const [evalResult, setEvalResult] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);

  const handleTrain = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.trainLabTokenizer({
        name,
        algorithm,
        vocab_size: Number(targetVocabSize),
        sample_text: sampleCorpus
      });
      setShowTrainModal(false);
      setName("");
      setSampleCorpus("");
      onRefresh();
    } catch (err: any) {
      alert(`Tokenizer training failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!testText.trim()) return;
    setEvaluating(true);
    try {
      const activeTokId = tokenizers[0]?.id;
      const res = await api.evaluateLabTokenizer({
        test_text: testText,
        tokenizer_id: activeTokId
      });
      setEvalResult(res);
    } catch (err: any) {
      alert(`Evaluation failed: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            Tokenizer Research & Subword Experimentation
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Train BPE and SentencePiece tokenizers, optimize vocabulary compression, and benchmark cross-lingual fertility.
          </p>
        </div>
        <button
          onClick={() => setShowTrainModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Train New Tokenizer</span>
        </button>
      </div>

      {/* Main Grid: Interactive Evaluator + Tokenizer List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Evaluator (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="border border-border rounded-xl bg-card p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Play className="w-4 h-4 text-cyan-400" />
                Live Subword Tokenizer Playground
              </h3>
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="px-3 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium disabled:opacity-50 transition-colors"
              >
                {evaluating ? "Evaluating..." : "Encode & Analyze"}
              </button>
            </div>

            <div>
              <label className="text-xs font-medium text-foreground block mb-1">Input Text</label>
              <textarea
                rows={3}
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-muted/40 text-xs outline-none resize-none font-mono"
              />
            </div>

            {/* Metrics Cards */}
            {evalResult?.metrics && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div className="bg-muted/40 p-3 rounded-lg border border-border/50">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Fertility</span>
                  <span className="font-mono font-bold text-base text-cyan-400">
                    {evalResult.metrics.fertility}
                  </span>
                  <span className="text-[10px] text-muted-foreground block">tokens / word</span>
                </div>

                <div className="bg-muted/40 p-3 rounded-lg border border-border/50">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                    Compression
                  </span>
                  <span className="font-mono font-bold text-base text-emerald-400">
                    {evalResult.metrics.compression_ratio}
                  </span>
                  <span className="text-[10px] text-muted-foreground block">bytes / token</span>
                </div>

                <div className="bg-muted/40 p-3 rounded-lg border border-border/50">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Total Tokens</span>
                  <span className="font-mono font-bold text-base text-foreground">
                    {evalResult.metrics.total_tokens}
                  </span>
                  <span className="text-[10px] text-muted-foreground block">from {evalResult.metrics.total_words} words</span>
                </div>

                <div className="bg-muted/40 p-3 rounded-lg border border-border/50">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">OOV / Unknown</span>
                  <span className="font-mono font-bold text-base text-foreground">
                    {(evalResult.metrics.unknown_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-muted-foreground block">&lt;unk&gt; fallback</span>
                </div>
              </div>
            )}

            {/* Token ID sequence preview */}
            {evalResult?.metrics?.token_ids_preview && (
              <div className="pt-2">
                <span className="text-xs font-semibold text-foreground block mb-2">Token Sequence Stream:</span>
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 rounded-lg bg-muted/40 border border-border/40 font-mono text-[11px]">
                  {evalResult.metrics.token_ids_preview.map((id: number, idx: number) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                    >
                      [{id}]
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Multilingual Benchmark */}
            {evalResult?.multilingual_benchmarks && (
              <div className="pt-2 border-t border-border/50">
                <span className="text-xs font-semibold text-foreground block mb-2 flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-cyan-400" />
                  Multilingual Compression Benchmarks
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {Object.entries(evalResult.multilingual_benchmarks).map(([lang, data]: any) => (
                    <div key={lang} className="p-2 rounded bg-muted/30 border border-border/40">
                      <span className="font-medium capitalize text-foreground block">{lang}</span>
                      <span className="text-muted-foreground text-[11px]">
                        Fertility: <span className="font-mono text-cyan-400 font-semibold">{data.fertility}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tokenizers List (1 col) */}
        <div className="space-y-4">
          <h3 className="text-sm font-bold text-foreground">Research Tokenizers ({tokenizers.length})</h3>
          <div className="space-y-3">
            {tokenizers.length === 0 ? (
              <div className="border border-border rounded-xl p-6 text-center text-xs text-muted-foreground bg-card">
                No tokenizers trained yet.
              </div>
            ) : (
              tokenizers.map((tok) => (
                <div key={tok.id} className="border border-border rounded-xl p-4 bg-card shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-foreground">{tok.name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">
                      v{tok.version}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center justify-between">
                    <span>Algorithm: <strong className="uppercase text-foreground">{tok.algorithm}</strong></span>
                    <span>Vocab: <strong className="font-mono text-foreground">{tok.vocab_size.toLocaleString()}</strong></span>
                  </div>
                  {tok.evaluation_metrics && (
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/40 text-[11px]">
                      <div>
                        Fertility: <strong className="font-mono text-cyan-400">{tok.evaluation_metrics.fertility}</strong>
                      </div>
                      <div>
                        Compression: <strong className="font-mono text-emerald-400">{tok.evaluation_metrics.compression_ratio}</strong>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Train Modal */}
      {showTrainModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-foreground mb-1">Train Research Tokenizer</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Iteratively learns subword merges using Byte-Pair Encoding.
            </p>

            <form onSubmit={handleTrain} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Tokenizer Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., nexora-bpe-32k"
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Algorithm</label>
                  <select
                    value={algorithm}
                    onChange={(e) => setAlgorithm(e.target.value as any)}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  >
                    <option value="bpe">BPE (Byte-Pair Encoding)</option>
                    <option value="unigram_sentencepiece">SentencePiece Unigram</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Target Vocab Size</label>
                  <input
                    type="number"
                    value={targetVocabSize}
                    onChange={(e) => setTargetVocabSize(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Training Corpus Text</label>
                <textarea
                  rows={4}
                  value={sampleCorpus}
                  onChange={(e) => setSampleCorpus(e.target.value)}
                  placeholder="Paste domain text or training documents to learn BPE merge rules..."
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none resize-none font-mono text-[11px]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium disabled:opacity-50"
                >
                  {loading ? "Training..." : "Start Training"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
