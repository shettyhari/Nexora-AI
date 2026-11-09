"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { DeveloperApiKey, DeveloperUsageResponse } from "@/types/ecosystem";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { copyToClipboard } from "@/lib/utils";
import {
  ArrowLeft,
  Check,
  Copy,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  Activity,
  Terminal,
  AlertCircle,
} from "lucide-react";

export default function DeveloperPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [keys, setKeys] = useState<DeveloperApiKey[]>([]);
  const [usage, setUsage] = useState<DeveloperUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdSecret, setCreatedSecret] = useState<DeveloperApiKey | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDeveloper = useCallback(async () => {
    try {
      const [kRes, uRes] = await Promise.all([
        api.getDeveloperKeys(),
        api.getDeveloperUsage(),
      ]);
      setKeys(kRes);
      setUsage(uRes);
    } catch (err: any) {
      setError(err.message || "Failed to load developer data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    } else if (user) {
      loadDeveloper();
    }
  }, [authLoading, user, router, loadDeveloper]);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setBusy(true);
    setError(null);
    setCreatedSecret(null);
    try {
      const created = await api.createDeveloperKey({ name: newKeyName.trim() });
      setCreatedSecret(created);
      setNewKeyName("");
      await loadDeveloper();
    } catch (err: any) {
      setError(err.message || "Failed to create API key");
    } finally {
      setBusy(false);
    }
  };

  const handleRotate = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const rotated = await api.rotateDeveloperKey(id);
      setCreatedSecret(rotated);
      await loadDeveloper();
    } catch (err: any) {
      setError(err.message || "Failed to rotate key");
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (id: string) => {
    if (!window.confirm("Revoke this API key immediately? Existing integrations using it will fail.")) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.revokeDeveloperKey(id);
      await loadDeveloper();
    } catch (err: any) {
      setError(err.message || "Failed to revoke key");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#080c14]">
        <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
      </div>
    );
  }

  const apiEnabled = usage?.api_access_enabled ?? false;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#080c14] text-slate-900 dark:text-slate-100 p-4 md:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Top Bar */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <NexoraWordmark logoSize={28} />
            <span className="hidden sm:inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Developer API Platform
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/billing"
              className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Manage Plan ({usage?.plan_tier?.toUpperCase()})
            </Link>
            <ThemeToggle />
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!apiEnabled && (
          <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-bold">Commercial API Key Creation Locked on Free Tier</p>
                <p className="opacity-90">
                  Upgrade to NEXORA Pro or Enterprise to generate <code className="font-mono">nex_live_...</code> keys for OpenAI-compatible endpoints.
                </p>
              </div>
            </div>
            <Link
              href="/billing"
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold whitespace-nowrap text-center"
            >
              Upgrade Plan
            </Link>
          </div>
        )}

        {/* Newly minted / rotated secret warning box */}
        {createdSecret?.plaintext_key && (
          <div className="p-5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-400">
                Save your secret API key now — it will never be displayed again
              </span>
              <button
                onClick={async () => {
                  const ok = await copyToClipboard(createdSecret.plaintext_key || "");
                  if (ok) {
                    setCopiedSecret(true);
                    setTimeout(() => setCopiedSecret(false), 2000);
                  }
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-500 text-slate-950 font-bold text-xs"
              >
                {copiedSecret ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedSecret ? "Copied!" : "Copy Key"}</span>
              </button>
            </div>
            <code className="block p-3 rounded-xl bg-slate-950 text-emerald-300 font-mono text-xs break-all border border-emerald-500/20">
              {createdSecret.plaintext_key}
            </code>
          </div>
        )}

        {/* KPI Strip */}
        {usage && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
              <div className="text-[11px] text-slate-400">API Requests</div>
              <div className="text-xl font-extrabold font-mono mt-1">{usage.summary.total_requests.toLocaleString()}</div>
            </div>
            <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
              <div className="text-[11px] text-slate-400">Total Tokens Billed</div>
              <div className="text-xl font-extrabold font-mono text-cyan-500 mt-1">{usage.summary.total_tokens.toLocaleString()}</div>
            </div>
            <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
              <div className="text-[11px] text-slate-400">Cumulative Cost</div>
              <div className="text-xl font-extrabold font-mono text-emerald-500 mt-1">${usage.summary.total_cost_usd.toFixed(4)}</div>
            </div>
            <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
              <div className="text-[11px] text-slate-400">Mean Latency</div>
              <div className="text-xl font-extrabold font-mono text-indigo-400 mt-1">{usage.summary.avg_latency_ms} ms</div>
            </div>
          </div>
        )}

        {/* Create Key + Keys Table */}
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-xl space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <h2 className="text-base font-bold flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-cyan-500" />
              Developer Secret Keys (<code className="font-mono text-xs">SHA-256 hashed at rest</code>)
            </h2>
            <form onSubmit={handleCreateKey} className="flex items-center gap-2">
              <input
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="Key label (e.g., prod-backend)"
                required
                disabled={!apiEnabled || busy}
                className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs focus:outline-none focus:border-cyan-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!apiEnabled || busy || !newKeyName.trim()}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs disabled:opacity-40"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Key</span>
              </button>
            </form>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Name</th>
                  <th className="py-2.5 pr-4">Secret Prefix</th>
                  <th className="py-2.5 pr-4">Requests</th>
                  <th className="py-2.5 pr-4">Tokens</th>
                  <th className="py-2.5 pr-4">Status</th>
                  <th className="py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {keys.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-400">
                      No API keys generated yet.
                    </td>
                  </tr>
                ) : (
                  keys.map((k) => (
                    <tr key={k.id}>
                      <td className="py-3 pr-4 font-semibold">{k.name}</td>
                      <td className="py-3 pr-4 font-mono text-slate-400">{k.masked_key || `${k.key_prefix}••••`}</td>
                      <td className="py-3 pr-4 font-mono">{k.total_requests}</td>
                      <td className="py-3 pr-4 font-mono">{k.total_tokens.toLocaleString()}</td>
                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            k.is_revoked
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          }`}
                        >
                          {k.is_revoked ? "Revoked" : "Active"}
                        </span>
                      </td>
                      <td className="py-3 text-right space-x-2">
                        {!k.is_revoked && (
                          <>
                            <button
                              onClick={() => handleRotate(k.id)}
                              disabled={busy}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
                            >
                              <RefreshCw className="w-3 h-3" /> Rotate
                            </button>
                            <button
                              onClick={() => handleRevoke(k.id)}
                              disabled={busy}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                            >
                              <Trash2 className="w-3 h-3" /> Revoke
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* OpenAI SDK Quickstart */}
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-xl space-y-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Terminal className="w-5 h-5 text-indigo-400" />
            OpenAI-Compatible SDK Integration (<code className="font-mono text-xs">/v1/*</code>)
          </h2>
          <pre className="p-4 rounded-2xl bg-slate-950 text-cyan-300 font-mono text-xs overflow-x-auto border border-slate-800">
{`curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer nex_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "nexora-flagship",
    "messages": [{"role": "user", "content": "Explain hybrid RAG ranking."}],
    "stream": false
  }'`}
          </pre>
        </div>

        {/* Recent Usage Logs */}
        {usage && usage.recent_logs.length > 0 && (
          <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-xl space-y-4">
            <h2 className="text-base font-bold flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-400" />
              Recent API Telemetry Logs
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">Endpoint</th>
                    <th className="py-2 pr-4">Model / Provider</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Tokens</th>
                    <th className="py-2 pr-4">Latency</th>
                    <th className="py-2">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                  {usage.recent_logs.slice(0, 15).map((log) => (
                    <tr key={log.id}>
                      <td className="py-2 pr-4">{log.method} {log.endpoint}</td>
                      <td className="py-2 pr-4">{log.model || "—"} ({log.provider || "nexora"})</td>
                      <td className="py-2 pr-4">{log.status_code}</td>
                      <td className="py-2 pr-4">{log.total_tokens}</td>
                      <td className="py-2 pr-4">{log.latency_ms} ms</td>
                      <td className="py-2">${log.cost_usd.toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
