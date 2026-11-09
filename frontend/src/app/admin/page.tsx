"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  Cpu,
  CreditCard,
  Database,
  Layers,
  Loader2,
  Rocket,
  Server,
  ShieldAlert,
  ShieldCheck,
  Users,
  AlertCircle,
} from "lucide-react";

type AdminTab =
  | "overview"
  | "users"
  | "plans"
  | "models"
  | "analytics"
  | "infra"
  | "security";

export default function AdminControlCenterPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [overview, setOverview] = useState<any>(null);
  const [sysHealth, setSysHealth] = useState<any>(null);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [plansList, setPlansList] = useState<any[]>([]);
  const [modelsList, setModelsList] = useState<any[]>([]);
  const [providersData, setProvidersData] = useState<any>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [trainingGpuData, setTrainingGpuData] = useState<any>(null);
  const [agentActivity, setAgentActivity] = useState<any>(null);
  const [securityEvents, setSecurityEvents] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);

  // Publish checkpoint bridge form
  const [pubCkptId, setPubCkptId] = useState("");
  const [pubModelId, setPubModelId] = useState("nexora-ft-v1");
  const [pubDisplayName, setPubDisplayName] = useState("NEXORA Proprietary Fine-Tuned");
  const [pubMinTier, setPubMinTier] = useState("free");

  // Plan edit drafts
  const [planDrafts, setPlanDrafts] = useState<Record<string, any>>({});

  const [loading, setLoading] = useState(true);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAdminData = useCallback(async () => {
    try {
      const [
        ovRes,
        shRes,
        uRes,
        pRes,
        mRes,
        prRes,
        anRes,
        tgRes,
        agRes,
        seRes,
        alRes,
        ckRes,
      ] = await Promise.allSettled([
        api.getAdminOverview(),
        api.getAdminSystemHealth(),
        api.getAdminUsers(),
        api.getAdminPlans(),
        api.getAdminModels(),
        api.getAdminProviders(),
        api.getAdminAnalytics(),
        api.getAdminTrainingAndGpu(),
        api.getAdminAgentActivity(),
        api.getAdminSecurityEvents(),
        api.getAdminAuditLogs(),
        api.getLabCheckpoints(),
      ]);

      if (ovRes.status === "fulfilled") setOverview(ovRes.value);
      if (shRes.status === "fulfilled") setSysHealth(shRes.value);
      if (uRes.status === "fulfilled") setUsersList(uRes.value);
      if (pRes.status === "fulfilled") {
        setPlansList(pRes.value);
        const drafts: Record<string, any> = {};
        pRes.value.forEach((p: any) => {
          drafts[p.id] = {
            monthly_price_usd: p.monthly_price_usd,
            monthly_token_quota: p.monthly_token_quota,
            rate_limit_rpm: p.rate_limit_rpm,
            max_file_size_mb: p.max_file_size_mb,
            api_access_enabled: p.api_access_enabled,
          };
        });
        setPlanDrafts(drafts);
      }
      if (mRes.status === "fulfilled") setModelsList(mRes.value);
      if (prRes.status === "fulfilled") setProvidersData(prRes.value);
      if (anRes.status === "fulfilled") setAnalyticsData(anRes.value);
      if (tgRes.status === "fulfilled") setTrainingGpuData(tgRes.value);
      if (agRes.status === "fulfilled") setAgentActivity(agRes.value);
      if (seRes.status === "fulfilled") setSecurityEvents(seRes.value);
      if (alRes.status === "fulfilled") setAuditLogs(alRes.value);
      if (ckRes.status === "fulfilled") {
        setCheckpoints(ckRes.value);
        if (ckRes.value.length > 0 && !pubCkptId) {
          const valid = ckRes.value.find((c: any) => c.validated) || ckRes.value[0];
          if (valid) setPubCkptId(valid.id);
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to load admin telemetry");
    } finally {
      setLoading(false);
    }
  }, [pubCkptId]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    } else if (user && user.role === "admin") {
      loadAdminData();
    } else if (user) {
      setLoading(false);
    }
  }, [authLoading, user, router, loadAdminData]);

  const handleUpdateUser = async (userId: string, patch: any) => {
    setError(null);
    setStatusMsg(null);
    try {
      await api.updateAdminUser(userId, patch);
      setStatusMsg("User configuration updated cleanly.");
      await loadAdminData();
    } catch (err: any) {
      setError(err.message || "Failed to update user");
    }
  };

  const handleSavePlan = async (planId: string) => {
    setError(null);
    setStatusMsg(null);
    try {
      const draft = planDrafts[planId];
      await api.updateAdminPlan(planId, {
        monthly_price_usd: Number(draft.monthly_price_usd),
        monthly_token_quota: Number(draft.monthly_token_quota),
        rate_limit_rpm: Number(draft.rate_limit_rpm),
        max_file_size_mb: Number(draft.max_file_size_mb),
        api_access_enabled: Boolean(draft.api_access_enabled),
      });
      setStatusMsg("Subscription plan pricing and limits updated.");
      await loadAdminData();
    } catch (err: any) {
      setError(err.message || "Failed to update plan");
    }
  };

  const handleToggleModel = async (model: any) => {
    setError(null);
    setStatusMsg(null);
    try {
      await api.updateAdminModel(model.id, { is_enabled: !model.is_enabled });
      setStatusMsg(`Model '${model.id}' ${!model.is_enabled ? "enabled" : "disabled"}.`);
      await loadAdminData();
    } catch (err: any) {
      setError(err.message || "Failed to update model status");
    }
  };

  const handlePublishCheckpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pubCkptId) return;
    setError(null);
    setStatusMsg(null);
    try {
      await api.publishCheckpointAsAdmin({
        checkpoint_id: pubCkptId,
        model_id: pubModelId.trim(),
        display_name: pubDisplayName.trim(),
        min_plan_tier: pubMinTier,
      });
      setStatusMsg(`Checkpoint published cleanly as commercial model '${pubModelId}'.`);
      await loadAdminData();
    } catch (err: any) {
      setError(err.message || "Failed to publish checkpoint");
    }
  };

  if (authLoading || loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#080c14]">
        <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
      </div>
    );
  }

  if (user.role !== "admin") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#080c14] p-6">
        <div className="max-w-md w-full p-8 rounded-3xl border border-rose-500/30 bg-white dark:bg-[#0d1322] text-center space-y-4 shadow-xl">
          <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto" />
          <h1 className="text-lg font-bold">403 — Administrator Privileges Required</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Your account role is <code className="font-mono font-bold">{user.role}</code>. Only platform administrators may access NEXORA Control Center.
          </p>
          <Link
            href="/"
            className="inline-block px-5 py-2 rounded-xl bg-cyan-600 text-white text-xs font-bold"
          >
            Return to Chat
          </Link>
        </div>
      </div>
    );
  }

  const tabs: Array<{ id: AdminTab; label: string; icon: any }> = [
    { id: "overview", label: "Overview & Health", icon: Activity },
    { id: "users", label: "Users & RBAC", icon: Users },
    { id: "plans", label: "Plans & Pricing", icon: CreditCard },
    { id: "models", label: "Models & Providers", icon: Layers },
    { id: "analytics", label: "Usage & Agents", icon: Bot },
    { id: "infra", label: "Training & GPU", icon: Cpu },
    { id: "security", label: "Security & Audit", icon: ShieldCheck },
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#080c14] text-slate-900 dark:text-slate-100">
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-[#0d1322]/90 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <NexoraWordmark logoSize={28} />
              <span className="text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
                Admin Control Center
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/lab"
                className="px-3 py-1.5 rounded-xl border border-cyan-500/30 text-cyan-400 text-xs font-semibold hover:bg-cyan-500/10"
              >
                Open Model Lab
              </Link>
              <ThemeToggle />
            </div>
          </div>

          <nav className="flex items-center gap-1 mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/60 overflow-x-auto">
            {tabs.map((t) => {
              const Icon = t.icon;
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                    active
                      ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                      : "text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        {statusMsg && (
          <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
            <Check className="w-4 h-4 shrink-0" />
            <span>{statusMsg}</span>
          </div>
        )}
        {error && (
          <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* TAB 1: OVERVIEW & HEALTH */}
        {activeTab === "overview" && overview && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
                <div className="text-xs text-slate-400">Platform Users</div>
                <div className="text-2xl font-extrabold font-mono mt-1">{overview.users.total}</div>
                <div className="text-[11px] text-emerald-400 mt-1">{overview.users.active} active</div>
              </div>
              <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
                <div className="text-xs text-slate-400">Billed Revenue (Paid)</div>
                <div className="text-2xl font-extrabold font-mono text-emerald-400 mt-1">${overview.billing.total_revenue_usd}</div>
                <div className="text-[11px] text-slate-400 mt-1">{overview.api.active_api_keys} active keys</div>
              </div>
              <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
                <div className="text-xs text-slate-400">Total API Tokens / Req</div>
                <div className="text-2xl font-extrabold font-mono text-cyan-400 mt-1">{overview.api.total_tokens.toLocaleString()}</div>
                <div className="text-[11px] text-slate-400 mt-1">{overview.api.total_requests} reqs · avg {overview.api.avg_latency_ms} ms</div>
              </div>
              <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
                <div className="text-xs text-slate-400">Security &amp; Lab Status</div>
                <div className="text-2xl font-extrabold font-mono text-amber-400 mt-1">{overview.security.total_security_events} events</div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Accelerator: {overview.lab.accelerator.toUpperCase()} · {overview.lab.healthy_deployments} endpoints
                </div>
              </div>
            </div>

            {sysHealth && (
              <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-4">
                <h2 className="text-base font-bold flex items-center gap-2">
                  <Database className="w-5 h-5 text-cyan-400" />
                  Production Infrastructure Health ({sysHealth.environment})
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
                  <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
                    <div className="text-slate-400">PostgreSQL / SQLite DB</div>
                    <div className={`font-bold mt-1 ${sysHealth.database.connected ? "text-emerald-400" : "text-rose-400"}`}>
                      {sysHealth.database.connected ? `Connected (${sysHealth.database.latency_ms} ms)` : "Disconnected"}
                    </div>
                  </div>
                  <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
                    <div className="text-slate-400">Cache &amp; Rate Store</div>
                    <div className="font-bold mt-1 text-cyan-400">{sysHealth.cache.backend}</div>
                  </div>
                  <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
                    <div className="text-slate-400">Object Storage</div>
                    <div className="font-bold mt-1">{sysHealth.storage.backend} ({sysHealth.storage.status})</div>
                  </div>
                  <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800">
                    <div className="text-slate-400">Host Compute</div>
                    <div className="font-bold mt-1 font-mono">
                      CPU {sysHealth.hardware.cpu_utilization_pct}% · RAM {sysHealth.hardware.ram_used_pct}%
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: USERS & RBAC */}
        {activeTab === "users" && (
          <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-4">
            <h2 className="text-base font-bold">User Directory, Roles &amp; Tier Overrides</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2.5 pr-4">User</th>
                    <th className="py-2.5 pr-4">Role</th>
                    <th className="py-2.5 pr-4">Plan Tier</th>
                    <th className="py-2.5 pr-4">Tokens Period</th>
                    <th className="py-2.5 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {usersList.map((u) => (
                    <tr key={u.id}>
                      <td className="py-3 pr-4">
                        <div className="font-semibold">{u.username}</div>
                        <div className="text-[11px] text-slate-400">{u.email}</div>
                      </td>
                      <td className="py-3 pr-4">
                        <select
                          value={u.role}
                          onChange={(e) => handleUpdateUser(u.id, { role: e.target.value })}
                          className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                        >
                          <option value="user">user</option>
                          <option value="researcher">researcher</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td className="py-3 pr-4">
                        <select
                          value={u.subscription?.plan_tier || "free"}
                          onChange={(e) => handleUpdateUser(u.id, { plan_tier: e.target.value })}
                          className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                        >
                          <option value="free">free</option>
                          <option value="pro">pro</option>
                          <option value="enterprise">enterprise</option>
                        </select>
                      </td>
                      <td className="py-3 pr-4 font-mono">
                        {(u.subscription?.tokens_used_period || 0).toLocaleString()}
                      </td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => handleUpdateUser(u.id, { is_active: !u.is_active })}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border ${
                            u.is_active
                              ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                              : "border-rose-500/30 text-rose-400 bg-rose-500/10"
                          }`}
                        >
                          {u.is_active ? "Active" : "Suspended"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: PLANS & PRICING */}
        {activeTab === "plans" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {plansList.map((plan) => {
              const d = planDrafts[plan.id] || {};
              return (
                <div key={plan.id} className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-4 text-xs">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-sm">{plan.name}</h3>
                    <span className="font-mono uppercase text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">{plan.tier}</span>
                  </div>
                  <div className="space-y-2.5">
                    <div>
                      <label className="text-slate-400 block mb-1">Monthly Price (USD)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={d.monthly_price_usd ?? 0}
                        onChange={(e) =>
                          setPlanDrafts((prev) => ({ ...prev, [plan.id]: { ...prev[plan.id], monthly_price_usd: e.target.value } }))
                        }
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-400 block mb-1">Monthly Token Quota</label>
                      <input
                        type="number"
                        value={d.monthly_token_quota ?? 0}
                        onChange={(e) =>
                          setPlanDrafts((prev) => ({ ...prev, [plan.id]: { ...prev[plan.id], monthly_token_quota: e.target.value } }))
                        }
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-slate-400 block mb-1">Rate Limit (RPM)</label>
                        <input
                          type="number"
                          value={d.rate_limit_rpm ?? 20}
                          onChange={(e) =>
                            setPlanDrafts((prev) => ({ ...prev, [plan.id]: { ...prev[plan.id], rate_limit_rpm: e.target.value } }))
                          }
                          className="w-full px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-1">Max File (MB)</label>
                        <input
                          type="number"
                          value={d.max_file_size_mb ?? 10}
                          onChange={(e) =>
                            setPlanDrafts((prev) => ({ ...prev, [plan.id]: { ...prev[plan.id], max_file_size_mb: e.target.value } }))
                          }
                          className="w-full px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 pt-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(d.api_access_enabled)}
                        onChange={(e) =>
                          setPlanDrafts((prev) => ({ ...prev, [plan.id]: { ...prev[plan.id], api_access_enabled: e.target.checked } }))
                        }
                      />
                      <span>Enable Developer API Key Access (/v1/*)</span>
                    </label>
                  </div>
                  <button
                    onClick={() => handleSavePlan(plan.id)}
                    className="w-full py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold"
                  >
                    Save Plan Limits
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* TAB 4: MODELS, PROVIDERS & CHECKPOINT PUBLISH */}
        {activeTab === "models" && (
          <div className="space-y-6">
            {/* Publish Model Lab Checkpoint Form */}
            <form onSubmit={handlePublishCheckpoint} className="p-6 rounded-3xl border border-cyan-500/30 bg-white dark:bg-[#0d1322] space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold flex items-center gap-2">
                  <Rocket className="w-4 h-4 text-cyan-400" />
                  Promote Model Lab Checkpoint to Commercial Catalog
                </h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <select
                  value={pubCkptId}
                  onChange={(e) => setPubCkptId(e.target.value)}
                  className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900"
                >
                  <option value="">Select checkpoint...</option>
                  {checkpoints.map((c) => (
                    <option key={c.id} value={c.id}>
                      Step #{c.step} v{c.version} ({c.validated ? "Validated" : "Unvalidated"})
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={pubModelId}
                  onChange={(e) => setPubModelId(e.target.value)}
                  placeholder="Model ID (e.g., nexora-legal-v1)"
                  required
                  className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono"
                />
                <input
                  type="text"
                  value={pubDisplayName}
                  onChange={(e) => setPubDisplayName(e.target.value)}
                  placeholder="Display Name"
                  required
                  className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900"
                />
                <div className="flex gap-2">
                  <select
                    value={pubMinTier}
                    onChange={(e) => setPubMinTier(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900"
                  >
                    <option value="free">Free+</option>
                    <option value="pro">Pro+</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                  <button
                    type="submit"
                    disabled={!pubCkptId}
                    className="flex-1 px-3 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold disabled:opacity-40"
                  >
                    Publish
                  </button>
                </div>
              </div>
            </form>

            {/* Providers Health Grid */}
            {providersData && (
              <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-3">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Server className="w-4 h-4 text-indigo-400" />
                  Gateway Provider Health (Credentials Masked)
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                  {Object.entries(providersData.providers || {}).map(([key, info]: [string, any]) => (
                    <div key={key} className="p-3.5 rounded-2xl border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                      <div>
                        <div className="font-bold uppercase font-mono">{key}</div>
                        <div className="text-[11px] text-slate-400">{info.latency_ms} ms</div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          info.status === "online"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        }`}
                      >
                        {info.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Catalog Models Table */}
            <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322]">
              <h3 className="text-sm font-bold mb-3">Live Model Catalog</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                    <tr>
                      <th className="py-2 pr-4">Model ID</th>
                      <th className="py-2 pr-4">Provider</th>
                      <th className="py-2 pr-4">Min Tier</th>
                      <th className="py-2 pr-4">Type</th>
                      <th className="py-2 text-right">Enabled</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {modelsList.map((m) => (
                      <tr key={m.id}>
                        <td className="py-2.5 pr-4 font-mono font-semibold">{m.id}</td>
                        <td className="py-2.5 pr-4 uppercase">{m.provider}</td>
                        <td className="py-2.5 pr-4 font-mono">{m.min_plan_tier}</td>
                        <td className="py-2.5 pr-4">{m.is_proprietary ? "NEXORA Proprietary" : "External / Adapter"}</td>
                        <td className="py-2.5 text-right">
                          <button
                            onClick={() => handleToggleModel(m)}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border ${
                              m.is_enabled
                                ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                                : "border-slate-600 text-slate-400"
                            }`}
                          >
                            {m.is_enabled ? "Enabled" : "Disabled"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: ANALYTICS & AGENT ACTIVITY */}
        {activeTab === "analytics" && (
          <div className="space-y-6">
            {analyticsData && (
              <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-3">
                <h2 className="text-base font-bold">Model Usage &amp; Cost Attribution</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                      <tr>
                        <th className="py-2 pr-4">Model</th>
                        <th className="py-2 pr-4">Provider</th>
                        <th className="py-2 pr-4">Requests</th>
                        <th className="py-2 pr-4">Tokens</th>
                        <th className="py-2 pr-4">Cost USD</th>
                        <th className="py-2">Avg Latency</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {(analyticsData.by_model || []).map((row: any, i: number) => (
                        <tr key={i}>
                          <td className="py-2 pr-4 font-bold">{row.model}</td>
                          <td className="py-2 pr-4">{row.provider}</td>
                          <td className="py-2 pr-4">{row.requests}</td>
                          <td className="py-2 pr-4">{row.total_tokens.toLocaleString()}</td>
                          <td className="py-2 pr-4 text-emerald-400">${row.cost_usd}</td>
                          <td className="py-2">{row.avg_latency_ms} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {agentActivity && (
              <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-3">
                <h2 className="text-base font-bold">Recent Multi-Agent Workflows &amp; Tool Executions</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div>
                    <h4 className="font-semibold text-slate-400 mb-2">Workflows ({agentActivity.workflows?.length || 0})</h4>
                    <div className="space-y-1.5">
                      {(agentActivity.workflows || []).slice(0, 8).map((w: any) => (
                        <div key={w.id} className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 flex justify-between gap-2">
                          <span className="truncate">{w.goal}</span>
                          <span className="font-mono text-cyan-400 shrink-0">{w.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-400 mb-2">Tool Executions ({agentActivity.tool_executions?.length || 0})</h4>
                    <div className="space-y-1.5">
                      {(agentActivity.tool_executions || []).slice(0, 8).map((t: any) => (
                        <div key={t.id} className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 flex justify-between gap-2 font-mono">
                          <span>{t.tool_name}</span>
                          <span className="text-emerald-400">{t.status} ({t.execution_time_ms} ms)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 6: TRAINING & GPU */}
        {activeTab === "infra" && trainingGpuData && (
          <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-4">
            <h2 className="text-base font-bold">Hardware Telemetry, Isolated Workers &amp; Serving Endpoints</h2>
            <div className="p-4 rounded-2xl bg-slate-950 text-cyan-300 font-mono text-xs border border-slate-800">
              Accelerator: {trainingGpuData.hardware.accelerator.toUpperCase()} · GPU Status: {trainingGpuData.hardware.gpu_status} · Cores: {trainingGpuData.hardware.cpu.cores_logical} · RAM: {trainingGpuData.hardware.memory.ram_used_gb}/{trainingGpuData.hardware.memory.ram_total_gb} GB
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2 pr-4">Job</th>
                    <th className="py-2 pr-4">Method / Framework</th>
                    <th className="py-2 pr-4">Steps</th>
                    <th className="py-2 pr-4">Loss</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {(trainingGpuData.training_jobs || []).map((j: any) => (
                    <tr key={j.id}>
                      <td className="py-2 pr-4 font-sans font-semibold">{j.name}</td>
                      <td className="py-2 pr-4">{j.training_method} / {j.framework}</td>
                      <td className="py-2 pr-4">{j.current_step}/{j.total_steps}</td>
                      <td className="py-2 pr-4">{j.current_train_loss ?? "—"}</td>
                      <td className="py-2 text-cyan-400">{j.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 7: SECURITY & AUDIT LOGS */}
        {activeTab === "security" && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-3">
              <h2 className="text-base font-bold flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                Security &amp; Abuse Telemetry Events ({securityEvents.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                    <tr>
                      <th className="py-2 pr-4">Severity</th>
                      <th className="py-2 pr-4">Event Type</th>
                      <th className="py-2 pr-4">Endpoint</th>
                      <th className="py-2 pr-4">IP</th>
                      <th className="py-2">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {securityEvents.map((ev) => (
                      <tr key={ev.id}>
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            ev.severity === "critical" || ev.severity === "high"
                              ? "bg-rose-500/15 text-rose-400"
                              : "bg-amber-500/15 text-amber-400"
                          }`}>
                            {ev.severity}
                          </span>
                        </td>
                        <td className="py-2 pr-4">{ev.event_type}</td>
                        <td className="py-2 pr-4">{ev.endpoint || "—"}</td>
                        <td className="py-2 pr-4">{ev.ip_address || "—"}</td>
                        <td className="py-2 text-slate-400">{new Date(ev.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] space-y-3">
              <h2 className="text-base font-bold">Immutable Admin &amp; Billing Audit Logs ({auditLogs.length})</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-400">
                    <tr>
                      <th className="py-2 pr-4">Action</th>
                      <th className="py-2 pr-4">Resource</th>
                      <th className="py-2 pr-4">Details</th>
                      <th className="py-2">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {auditLogs.slice(0, 30).map((log) => (
                      <tr key={log.id}>
                        <td className="py-2 pr-4 font-bold text-cyan-400">{log.action}</td>
                        <td className="py-2 pr-4">{log.resource_type} ({log.resource_id?.slice(0, 8) || "—"})</td>
                        <td className="py-2 pr-4 max-w-xs truncate">{log.details || "—"}</td>
                        <td className="py-2 text-slate-400">{new Date(log.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
