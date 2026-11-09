export interface SubscriptionPlan {
  id: string;
  tier: "free" | "pro" | "enterprise" | string;
  name: string;
  description?: string;
  monthly_price_usd: number;
  annual_price_usd: number;
  monthly_token_quota: number;
  rate_limit_rpm: number;
  max_file_size_mb: number;
  api_access_enabled: boolean;
  allowed_models: string[];
  allowed_features: string[];
  is_active: boolean;
}

export interface UserSubscriptionInfo {
  id: string;
  status: string;
  billing_cycle: "monthly" | "annual";
  tokens_used_period: number;
  requests_period: number;
  tokens_remaining: number;
  quota_utilization_pct: number;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  payment_provider: string;
}

export interface SubscriptionResponse {
  subscription: UserSubscriptionInfo;
  plan: SubscriptionPlan;
}

export interface BillingInvoice {
  id: string;
  invoice_number: string;
  amount_usd: number;
  currency: string;
  status: string;
  billing_reason: string;
  payment_method_summary?: string;
  created_at: string;
}

export interface DeveloperApiKey {
  id: string;
  name: string;
  key_prefix: string;
  masked_key?: string;
  plaintext_key?: string;
  scopes: string[];
  rate_limit_rpm?: number;
  is_revoked: boolean;
  total_requests: number;
  total_tokens: number;
  last_used_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  warning?: string;
}

export interface DeveloperUsageResponse {
  plan_tier: string;
  api_access_enabled: boolean;
  rate_limit_rpm: number;
  monthly_token_quota: number;
  tokens_used_period: number;
  summary: {
    total_requests: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_latency_ms: number;
  };
  recent_logs: Array<{
    id: string;
    endpoint: string;
    method: string;
    status_code: number;
    model?: string;
    provider?: string;
    total_tokens: number;
    cost_usd: number;
    latency_ms: number;
    created_at: string;
  }>;
}
