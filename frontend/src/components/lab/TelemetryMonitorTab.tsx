"use client";

import React, { useState, useEffect, useCallback } from "react";
import { HardwareTelemetry, LabTrainingJob } from "@/types/lab";
import { Cpu, Activity, HardDrive, Thermometer, RefreshCw, AlertTriangle, CheckCircle2, Layers } from "lucide-react";
import { api } from "@/lib/api";

export const TelemetryMonitorTab: React.FC = () => {
  const [telemetry, setTelemetry] = useState<{
    hardware: HardwareTelemetry;
    active_jobs: any[];
    recent_jobs: any[];
  } | null>(null);
  const [frameworks, setFrameworks] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [telRes, fwRes] = await Promise.allSettled([
        api.getLabTelemetry(),
        api.getLabFrameworks(),
      ]);
      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (fwRes.status === "fulfilled") setFrameworks(fwRes.value);
    } catch (err) {
      console.error("Failed to fetch telemetry:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    if (!autoRefresh) return;
    const timer = setInterval(loadData, 4000);
    return () => clearInterval(timer);
  }, [loadData, autoRefresh]);

  if (loading && !telemetry) {
    return (
      <div className="py-16 text-center text-xs text-muted-foreground font-mono">
        Querying real hardware telemetry & framework runtimes...
      </div>
    );
  }

  const hw = telemetry?.hardware;
  const fwMap = frameworks?.frameworks || {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            Real-Time GPU, Hardware & Framework Telemetry
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Authentic hardware metrics probed from host NVML/CUDA/CPU/Memory. Missing accelerators are reported honestly without simulation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer px-2.5 py-1.5 rounded-lg border border-border bg-card">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-cyan-500"
            />
            <span>Live Poll (4s)</span>
          </label>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-medium transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* GPU Hardware Panel */}
      {hw && (
        <div
          className={`border rounded-xl p-5 ${
            hw.gpu_available
              ? "border-emerald-500/30 bg-emerald-500/5"
              : "border-amber-500/30 bg-amber-500/5"
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              {hw.gpu_available ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
              )}
              <div>
                <h3 className="text-sm font-bold text-foreground">{hw.gpu_status}</h3>
                <p className="text-[11px] text-muted-foreground font-mono">
                  Platform: {hw.platform} | Accelerator: {hw.accelerator.toUpperCase()}
                  {hw.cuda_version ? ` | CUDA ${hw.cuda_version}` : ""}
                </p>
              </div>
            </div>
            <span
              className={`text-[11px] font-mono px-2.5 py-1 rounded-full border self-start sm:self-center ${
                hw.gpu_available
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/15 text-amber-300 border-amber-500/30"
              }`}
            >
              {hw.gpu_available ? `${hw.gpu_count} GPU(s) Active` : "GPU Unavailable (CPU Fallback)"}
            </span>
          </div>

          {hw.gpus && hw.gpus.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              {hw.gpus.map((gpu) => (
                <div key={gpu.index} className="rounded-xl border border-border bg-card p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-foreground">
                      GPU #{gpu.index}: {gpu.name}
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground uppercase">
                      {gpu.backend}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="p-2 rounded bg-muted/40">
                      <span className="text-[10px] text-muted-foreground block">GPU Util</span>
                      <span className="font-mono font-bold text-cyan-400">
                        {gpu.gpu_utilization_pct != null ? `${gpu.gpu_utilization_pct}%` : "N/A"}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-muted/40">
                      <span className="text-[10px] text-muted-foreground block">VRAM Used</span>
                      <span className="font-mono font-bold text-emerald-400">
                        {gpu.memory_used_mb != null && gpu.memory_total_mb != null
                          ? `${gpu.memory_used_mb} / ${gpu.memory_total_mb} MB`
                          : "N/A"}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-muted/40">
                      <span className="text-[10px] text-muted-foreground block flex items-center gap-1">
                        <Thermometer className="w-3 h-3" /> Temp
                      </span>
                      <span className="font-mono font-bold text-foreground">
                        {gpu.temperature_c != null ? `${gpu.temperature_c} °C` : "N/A"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Host CPU, RAM & Disk Telemetry */}
      {hw && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border border-border rounded-xl bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-semibold flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-cyan-400" /> CPU Utilization
              </span>
              <span className="font-mono">{hw.cpu.cores_logical} Threads</span>
            </div>
            <div className="text-2xl font-mono font-bold text-foreground">
              {hw.cpu.utilization_pct.toFixed(1)}%
            </div>
            <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-cyan-500 transition-all"
                style={{ width: `${Math.min(100, hw.cpu.utilization_pct)}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground font-mono">
              Physical cores: {hw.cpu.cores_physical}
              {hw.cpu.frequency_mhz ? ` | ${hw.cpu.frequency_mhz} MHz` : ""}
            </p>
          </div>

          <div className="border border-border rounded-xl bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-semibold flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-400" /> System Memory (RAM)
              </span>
              <span className="font-mono">{hw.memory.ram_total_gb} GB Total</span>
            </div>
            <div className="text-2xl font-mono font-bold text-foreground">
              {hw.memory.ram_used_gb} GB ({hw.memory.ram_utilization_pct.toFixed(1)}%)
            </div>
            <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all"
                style={{ width: `${Math.min(100, hw.memory.ram_utilization_pct)}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground font-mono">
              Available: {hw.memory.ram_available_gb} GB
            </p>
          </div>

          <div className="border border-border rounded-xl bg-card p-5 space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-semibold flex items-center gap-1.5">
                <HardDrive className="w-4 h-4 text-emerald-400" /> Checkpoint Storage
              </span>
              <span className="font-mono">{hw.disk.total_gb} GB</span>
            </div>
            <div className="text-2xl font-mono font-bold text-foreground">
              {hw.disk.free_gb} GB Free
            </div>
            <p className="text-[11px] text-muted-foreground">
              Dedicated local volume for SafeTensors checkpoints, PEFT adapters, logs & exported bundles.
            </p>
          </div>
        </div>
      )}

      {/* Training & Serving Frameworks Matrix */}
      <div className="border border-border rounded-xl bg-card p-5 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-foreground">
            Integrated Training & Distributed Execution Stack
          </h3>
          <p className="text-xs text-muted-foreground">
            Live inspection of installed Python frameworks and cluster configuration adapters.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.values(fwMap).map((fw: any) => (
            <div
              key={fw.name}
              className="p-3 rounded-lg border border-border/70 bg-muted/20 flex items-start justify-between gap-2"
            >
              <div>
                <div className="font-mono font-bold text-xs text-foreground">{fw.name}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{fw.description}</div>
              </div>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border shrink-0 ${
                  fw.installed
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : fw.mode === "config_adapter"
                    ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                    : "bg-muted text-muted-foreground border-border"
                }`}
              >
                {fw.installed ? `v${fw.version || "ok"}` : fw.mode === "config_adapter" ? "Config Ready" : "Not Installed"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Training Metrics Snapshot */}
      {telemetry?.recent_jobs && telemetry.recent_jobs.length > 0 && (
        <div className="border border-border rounded-xl bg-card p-5 space-y-3">
          <h3 className="text-sm font-bold text-foreground">Worker Training Metrics Snapshot</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground font-semibold">
                <tr>
                  <th className="px-3 py-2">Job</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Device</th>
                  <th className="px-3 py-2">Step Progress</th>
                  <th className="px-3 py-2">Train / Val Loss</th>
                  <th className="px-3 py-2">LR</th>
                  <th className="px-3 py-2 text-right">Throughput</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {telemetry.recent_jobs.map((j: any) => (
                  <tr key={j.id}>
                    <td className="px-3 py-2 font-medium text-foreground">{j.name}</td>
                    <td className="px-3 py-2 capitalize font-mono">{j.status}</td>
                    <td className="px-3 py-2 uppercase font-mono text-muted-foreground">{j.device_type}</td>
                    <td className="px-3 py-2 font-mono">
                      {j.current_step} / {j.total_steps}
                    </td>
                    <td className="px-3 py-2 font-mono">
                      {j.current_train_loss != null ? j.current_train_loss.toFixed(4) : "—"} /{" "}
                      <span className="text-emerald-400">
                        {j.current_val_loss != null ? j.current_val_loss.toFixed(4) : "—"}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">
                      {j.current_lr != null ? Number(j.current_lr).toExponential(1) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-cyan-400">
                      {j.tokens_per_sec ? `${j.tokens_per_sec} tok/s` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

