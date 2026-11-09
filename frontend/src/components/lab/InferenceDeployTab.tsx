"use client";

import React, { useState } from "react";
import { LabCheckpoint, LabInferenceDeployment } from "@/types/lab";
import { Server, Rocket, Square, Send, CheckCircle2, AlertCircle, Cpu } from "lucide-react";
import { api } from "@/lib/api";

interface InferenceDeployTabProps {
  deploymentsData: { engines: any; deployments: LabInferenceDeployment[] } | null;
  checkpoints: LabCheckpoint[];
  onRefresh: () => void;
}

export const InferenceDeployTab: React.FC<InferenceDeployTabProps> = ({
  deploymentsData,
  checkpoints,
  onRefresh,
}) => {
  const validatedCkpts = checkpoints.filter((c) => c.validated);
  const [modelAlias, setModelAlias] = useState("nexora-nano-ft-v1");
  const [checkpointId, setCheckpointId] = useState(validatedCkpts[0]?.id || checkpoints[0]?.id || "");
  const [engine, setEngine] = useState("transformers");
  const [quantization, setQuantization] = useState("none");
  const [maxModelLen, setMaxModelLen] = useState("2048");
  const [maxConcurrent, setMaxConcurrent] = useState("8");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // OpenAI Inference Test Playground
  const deployments = deploymentsData?.deployments || [];
  const healthyDeployments = deployments.filter((d) => d.status === "healthy");
  const [testAlias, setTestAlias] = useState(healthyDeployments[0]?.model_alias || "");
  const [testPrompt, setTestPrompt] = useState("Explain how RMSNorm and GQA improve LLM inference latency.");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);

  const handleDeploy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!checkpointId) {
      setError("Select a checkpoint first. Unvalidated checkpoints are rejected by the serving gate.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const dep = await api.deployLabCheckpoint({
        model_alias: modelAlias.trim(),
        checkpoint_id: checkpointId,
        engine,
        quantization,
        max_model_len: Number(maxModelLen),
        max_concurrent_requests: Number(maxConcurrent),
      });
      setTestAlias(dep.model_alias);
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Deployment failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async (deploymentId: string) => {
    try {
      await api.stopLabDeployment(deploymentId);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to stop deployment: ${err.message}`);
    }
  };

  const handleTestInference = async (e: React.FormEvent) => {
    e.preventDefault();
    const targetModel = testAlias || healthyDeployments[0]?.model_alias;
    if (!targetModel) {
      alert("Deploy a healthy model endpoint first.");
      return;
    }
    setTesting(true);
    try {
      const res = await api.invokeOpenAIChatCompletion(targetModel, testPrompt);
      setTestResult(res);
      onRefresh();
    } catch (err: any) {
      setTestResult({ error: err.message || "Inference request failed" });
    } finally {
      setTesting(false);
    }
  };

  const engines = deploymentsData?.engines || {};

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Server className="w-5 h-5 text-cyan-400" />
          Independent OpenAI-Compatible Inference Server & Model Deployments
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Serve validated checkpoints via isolated OpenAI-compatible endpoints (<code className="font-mono">/v1/chat/completions</code>, <code className="font-mono">/v1/models</code>, <code className="font-mono">/v1/health</code>) with concurrency queues and token usage telemetry.
        </p>
      </div>

      {/* Engine Capabilities Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        {["vllm", "transformers", "pytorch_native"].map((engKey) => {
          const cap = engines[engKey] || {};
          return (
            <div key={engKey} className="border border-border rounded-xl bg-card p-4 flex items-start justify-between gap-2">
              <div>
                <div className="font-mono font-bold uppercase text-foreground">{engKey.replace("_", " ")}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">
                  {cap.reason || (cap.ready ? `Device: ${(cap.device || "cpu").toUpperCase()}` : "Runtime check pending")}
                </div>
              </div>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full border shrink-0 ${
                  cap.ready
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/10 text-amber-300 border-amber-500/30"
                }`}
              >
                {cap.ready ? "READY" : "CUDA ONLY"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Deploy Form */}
      <form onSubmit={handleDeploy} className="border border-border rounded-xl bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
            <Rocket className="w-4 h-4 text-cyan-400" />
            Deploy Validated Checkpoint Endpoint
          </h3>
          <span className="text-[11px] text-muted-foreground">
            Strict SHA-256 &amp; forward-pass validation gate enforced
          </span>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="text-muted-foreground block mb-1">Serving Model Alias</label>
            <input
              type="text"
              value={modelAlias}
              onChange={(e) => setModelAlias(e.target.value)}
              required
              placeholder="e.g., nexora-nano-sft-v1"
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            />
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Trained Checkpoint</label>
            <select
              value={checkpointId}
              onChange={(e) => setCheckpointId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="">Select checkpoint...</option>
              {checkpoints.map((c) => (
                <option key={c.id} value={c.id}>
                  Step {c.step} (v{c.version}) — {c.validated ? "Validated" : "Needs Validation"}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-muted-foreground block mb-1">Inference Runtime</label>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
            >
              <option value="transformers">Transformers + PyTorch Native</option>
              <option value="vllm">vLLM PagedAttention (auto-fallback if CPU)</option>
              <option value="pytorch_native">PyTorch Native Generation</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end">
          <div>
            <label className="text-muted-foreground block mb-1">Quantization</label>
            <select
              value={quantization}
              onChange={(e) => setQuantization(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            >
              <option value="none">None (Native)</option>
              <option value="int8_dynamic">INT8 Dynamic</option>
              <option value="fp16">FP16</option>
              <option value="bf16">BF16</option>
            </select>
          </div>
          <div>
            <label className="text-muted-foreground block mb-1">Max Context Length</label>
            <input
              type="number"
              value={maxModelLen}
              onChange={(e) => setMaxModelLen(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            />
          </div>
          <div>
            <label className="text-muted-foreground block mb-1">Concurrency Queue Limit</label>
            <input
              type="number"
              min={1}
              max={64}
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white font-semibold disabled:opacity-50"
          >
            <Rocket className="w-3.5 h-3.5" />
            <span>{submitting ? "Deploying..." : "Deploy Serving Endpoint"}</span>
          </button>
        </div>
      </form>

      {/* Active Deployments Table */}
      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase text-muted-foreground">Active &amp; Historical Endpoints</h3>
          <span className="text-[11px] font-mono text-muted-foreground">
            OpenAI Base URL: <code className="text-cyan-400">/v1</code>
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground font-semibold border-b border-border">
              <tr>
                <th className="px-4 py-2.5">Model Alias</th>
                <th className="px-4 py-2.5">Engine &amp; Device</th>
                <th className="px-4 py-2.5">Health</th>
                <th className="px-4 py-2.5">Requests / Queue</th>
                <th className="px-4 py-2.5">Tokens (In / Out)</th>
                <th className="px-4 py-2.5">Avg Latency</th>
                <th className="px-4 py-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {deployments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    No active OpenAI-compatible serving deployments yet. Deploy a validated checkpoint above.
                  </td>
                </tr>
              ) : (
                deployments.map((dep) => (
                  <tr key={dep.id} className="hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="font-mono font-bold text-foreground">{dep.model_alias}</div>
                      <div className="text-[10px] text-muted-foreground">{dep.model_name}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px]">
                      {dep.engine} ({dep.quantization}) / {dep.device.toUpperCase()}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                          dep.status === "healthy"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                            : "bg-muted text-muted-foreground border border-border"
                        }`}
                      >
                        {dep.status === "healthy" && <CheckCircle2 className="w-3 h-3" />}
                        {dep.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono">
                      {dep.requests_served} reqs / q={dep.active_queue_depth}/{dep.max_concurrent_requests}
                    </td>
                    <td className="px-4 py-3 font-mono text-muted-foreground">
                      {dep.total_prompt_tokens} / {dep.total_completion_tokens}
                    </td>
                    <td className="px-4 py-3 font-mono text-cyan-400">{dep.avg_latency_ms.toFixed(1)} ms</td>
                    <td className="px-4 py-3 text-right">
                      {dep.status === "healthy" && (
                        <button
                          type="button"
                          onClick={() => handleStop(dep.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 text-[11px]"
                        >
                          <Square className="w-3 h-3" /> Stop
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Inference Test Console */}
      <div className="border border-border rounded-xl bg-card p-5 space-y-3">
        <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
          <Cpu className="w-4 h-4 text-cyan-400" />
          OpenAI Endpoint Live Verification (<code className="font-mono text-xs">POST /v1/chat/completions</code>)
        </h3>
        <form onSubmit={handleTestInference} className="space-y-3 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <select
                value={testAlias || healthyDeployments[0]?.model_alias || ""}
                onChange={(e) => setTestAlias(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 font-mono outline-none"
              >
                {healthyDeployments.length === 0 ? (
                  <option value="">No healthy deployment</option>
                ) : (
                  healthyDeployments.map((d) => (
                    <option key={d.id} value={d.model_alias}>
                      {d.model_alias}
                    </option>
                  ))
                )}
              </select>
            </div>
            <div className="md:col-span-2">
              <input
                type="text"
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={testing || healthyDeployments.length === 0}
              className="flex items-center justify-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white font-semibold disabled:opacity-40"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{testing ? "Generating..." : "Test Inference"}</span>
            </button>
          </div>
        </form>

        {testResult && (
          <pre className="p-3 rounded-lg bg-zinc-950 text-emerald-300 font-mono text-[11px] overflow-x-auto border border-border">
            {JSON.stringify(testResult, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};

