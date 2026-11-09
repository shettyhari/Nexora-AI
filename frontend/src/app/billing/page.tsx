"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import {
  BillingInvoice,
  SubscriptionPlan,
  SubscriptionResponse,
} from "@/types/ecosystem";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import {
  ArrowLeft,
  Check,
  CreditCard,
  Loader2,
  Receipt,
  Sparkles,
  Zap,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";

export default function BillingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [subData, setSubData] = useState<SubscriptionResponse | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(true);
  const [busyTier, setBusyTier] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBilling = useCallback(async () => {
    try {
      const [pRes, sRes, iRes] = await Promise.all([
        api.getBillingPlans(),
        api.getMySubscription(),
        api.getInvoices(),
      ]);
      setPlans(pRes);
      setSubData(sRes);
      setInvoices(iRes);
      if (sRes.subscription.billing_cycle === "annual") {
        setBillingCycle("annual");
      }
    } catch (err: any) {
      setError(err.message || "Failed to load billing details");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    } else if (user) {
      loadBilling();
    }
  }, [authLoading, user, router, loadBilling]);

  const handleSubscribe = async (tier: string) => {
    setBusyTier(tier);
    setMessage(null);
    setError(null);
    try {
      const res = await api.subscribeToPlan(tier, billingCycle, "Card ****4242");
      setMessage(res.message || `Switched subscription to ${tier}.`);
      await loadBilling();
    } catch (err: any) {
      setError(err.message || "Failed to update subscription");
    } finally {
      setBusyTier(null);
    }
  };

  const handleCancel = async (immediate = false) => {
    setBusyTier("cancel");
    setMessage(null);
    setError(null);
    try {
      const res = await api.cancelSubscription(immediate);
      setMessage(res.message || "Subscription updated.");
      await loadBilling();
    } catch (err: any) {
      setError(err.message || "Cancellation failed");
    } finally {
      setBusyTier(null);
    }
  };

  if (authLoading || loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#080c14]">
        <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
      </div>
    );
  }

  const activePlan = subData?.plan;
  const activeSub = subData?.subscription;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#080c14] text-slate-900 dark:text-slate-100 p-4 md:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Top Bar */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <NexoraWordmark logoSize={28} />
            <span className="hidden sm:inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
              Billing &amp; Quotas
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/developer"
              className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Developer API Keys
            </Link>
            <ThemeToggle />
          </div>
        </div>

        {message && (
          <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs flex items-center gap-2">
            <Check className="w-4 h-4 shrink-0" />
            <span>{message}</span>
          </div>
        )}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Active Plan Usage Banner */}
        {activePlan && activeSub && (
          <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-cyan-500" />
                  <h1 className="text-lg font-bold">Current Plan: {activePlan.name}</h1>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                    {activeSub.status} · {activeSub.billing_cycle}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Rate limit: <strong>{activePlan.rate_limit_rpm} req/min</strong> · Max Upload: <strong>{activePlan.max_file_size_mb} MB</strong> · Commercial API Access: <strong>{activePlan.api_access_enabled ? "Enabled" : "Disabled"}</strong>
                </p>
              </div>
              {activePlan.tier !== "free" && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCancel(false)}
                    disabled={busyTier !== null || activeSub.cancel_at_period_end}
                    className="px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
                  >
                    {activeSub.cancel_at_period_end ? "Cancelling at Period End" : "Cancel at Period End"}
                  </button>
                  <button
                    onClick={() => handleCancel(true)}
                    disabled={busyTier !== null}
                    className="px-3 py-1.5 rounded-xl border border-rose-500/30 text-rose-500 text-xs hover:bg-rose-500/10 disabled:opacity-50"
                  >
                    Downgrade to Free Now
                  </button>
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-slate-600 dark:text-slate-300">Monthly Token Quota Usage</span>
                <span className="font-mono text-cyan-500">
                  {activeSub.tokens_used_period.toLocaleString()} / {activePlan.monthly_token_quota.toLocaleString()} tokens ({activeSub.quota_utilization_pct}%)
                </span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(2, activeSub.quota_utilization_pct))}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Billing Cycle Toggle */}
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">Subscription Tiers</h2>
          <div className="inline-flex rounded-xl border border-slate-200 dark:border-slate-800 p-1 bg-white dark:bg-slate-900 text-xs">
            <button
              onClick={() => setBillingCycle("monthly")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                billingCycle === "monthly" ? "bg-cyan-600 text-white" : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle("annual")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                billingCycle === "annual" ? "bg-cyan-600 text-white" : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Annual (Save ~17%)
            </button>
          </div>
        </div>

        {/* Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {plans.map((plan) => {
            const isCurrent = activePlan?.tier === plan.tier;
            const price = billingCycle === "annual" ? plan.annual_price_usd : plan.monthly_price_usd;
            const isPro = plan.tier === "pro";

            return (
              <div
                key={plan.id}
                className={`p-6 rounded-3xl border flex flex-col justify-between transition-all ${
                  isPro
                    ? "border-cyan-500/60 bg-gradient-to-b from-cyan-500/5 to-white dark:to-[#0d1322] shadow-xl shadow-cyan-500/5"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-lg"
                }`}
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold flex items-center gap-1.5">
                      {plan.tier === "enterprise" ? (
                        <ShieldCheck className="w-4 h-4 text-amber-400" />
                      ) : plan.tier === "pro" ? (
                        <Sparkles className="w-4 h-4 text-cyan-400" />
                      ) : (
                        <Zap className="w-4 h-4 text-slate-400" />
                      )}
                      {plan.name}
                    </span>
                    {isCurrent && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <div>
                    <span className="text-3xl font-extrabold">${price}</span>
                    <span className="text-xs text-slate-400">
                      /{billingCycle === "annual" ? "year" : "month"}
                    </span>
                  </div>

                  <p className="text-xs text-slate-500 dark:text-slate-400 min-h-[36px]">
                    {plan.description}
                  </p>

                  <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300 pt-2 border-t border-slate-100 dark:border-slate-800/80">
                    <li className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-cyan-500 shrink-0" />
                      <span>{(plan.monthly_token_quota / 1000).toLocaleString()}k tokens / month</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-cyan-500 shrink-0" />
                      <span>{plan.rate_limit_rpm} requests / min rate limit</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-cyan-500 shrink-0" />
                      <span>Up to {plan.max_file_size_mb} MB file uploads</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-cyan-500 shrink-0" />
                      <span>
                        {plan.allowed_models.includes("*")
                          ? "All frontier & proprietary models"
                          : `${plan.allowed_models.length} starter models`}
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className={`w-3.5 h-3.5 shrink-0 ${plan.api_access_enabled ? "text-emerald-500" : "text-slate-500"}`} />
                      <span>{plan.api_access_enabled ? "Developer API Keys (/v1/*)" : "Web Workspace only"}</span>
                    </li>
                  </ul>
                </div>

                <button
                  onClick={() => handleSubscribe(plan.tier)}
                  disabled={busyTier !== null || isCurrent}
                  className={`mt-6 w-full py-2.5 rounded-xl text-xs font-bold transition-all disabled:opacity-50 ${
                    isCurrent
                      ? "bg-slate-200 dark:bg-slate-800 text-slate-500 cursor-default"
                      : isPro
                      ? "bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-md"
                      : "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:opacity-90"
                  }`}
                >
                  {busyTier === plan.tier ? "Processing..." : isCurrent ? "Current Plan" : `Switch to ${plan.name}`}
                </button>
              </div>
            );
          })}
        </div>

        {/* Invoices Table */}
        <div className="p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-xl space-y-4">
          <div className="flex items-center gap-2">
            <Receipt className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold">Billing Invoices &amp; Ledger</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 dark:border-slate-800 text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Invoice #</th>
                  <th className="py-2.5 pr-4">Reason</th>
                  <th className="py-2.5 pr-4">Method</th>
                  <th className="py-2.5 pr-4">Amount</th>
                  <th className="py-2.5 pr-4">Status</th>
                  <th className="py-2.5">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-400">
                      No billing invoices recorded yet.
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="py-3 pr-4 font-mono font-semibold">{inv.invoice_number}</td>
                      <td className="py-3 pr-4 capitalize">{inv.billing_reason.replace(/_/g, " ")}</td>
                      <td className="py-3 pr-4 text-slate-500">{inv.payment_method_summary || "Card"}</td>
                      <td className="py-3 pr-4 font-mono font-bold">
                        ${inv.amount_usd.toFixed(2)} {inv.currency}
                      </td>
                      <td className="py-3 pr-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          {inv.status}
                        </span>
                      </td>
                      <td className="py-3 text-slate-400 font-mono">
                        {new Date(inv.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
