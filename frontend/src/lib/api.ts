import { STORAGE_KEYS } from "./constants";
import {
  ConversationDetail,
  ConversationSummary,
  Feedback,
  Message,
  ModelConfig,
  StreamEvent,
  Attachment
} from "@/types/chat";
import { User, Profile, UserPreference } from "@/types/user";
import {
  BillingInvoice,
  DeveloperApiKey,
  DeveloperUsageResponse,
  SubscriptionPlan,
  SubscriptionResponse,
} from "@/types/ecosystem";

const API_PREFIX = "/api/v1";

class ApiClient {
  /**
   * Resolves the target base URL.
   * - Server-side (Node.js runtime in Next.js Server Components, Actions, SSR):
   *   Reads Vercel's injected service binding `BACKEND_URL`, falling back to `NEXT_PUBLIC_API_URL` or local dev.
   * - Client-side (Browser):
   *   Uses relative URL (empty base) so browser requests route through Vercel's top-level `/api/(.*)` rewrite,
   *   or uses explicit `NEXT_PUBLIC_API_URL` if configured.
   */
  public getBaseUrl(): string {
    if (typeof window === "undefined") {
      const bindingUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      return bindingUrl.replace(/\/$/, "");
    }
    return (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  }

  public getApiUrl(endpoint: string): string {
    const base = this.getBaseUrl();
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    if (cleanEndpoint.startsWith("/api/")) {
      return `${base}${cleanEndpoint}`;
    }
    return `${base}${API_PREFIX}${cleanEndpoint}`;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(STORAGE_KEYS.TOKEN);
  }

  private setTokens(access: string, refresh?: string) {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE_KEYS.TOKEN, access);
    if (refresh) {
      localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refresh);
    }
  }

  public clearTokens() {
    if (typeof window === "undefined") return;
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = this.getApiUrl(endpoint);
    const token = this.getToken();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Try refresh token
      const refreshToken = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) : null;
      if (refreshToken && endpoint !== "/auth/login" && endpoint !== "/auth/refresh") {
        try {
          const refreshResp = await fetch(this.getApiUrl("/auth/refresh"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (refreshResp.ok) {
            const data = await refreshResp.json();
            this.setTokens(data.access_token, data.refresh_token);
            // Retry original request
            headers["Authorization"] = `Bearer ${data.access_token}`;
            const retryResp = await fetch(url, { ...options, headers });
            if (!retryResp.ok) {
              const err = await retryResp.json().catch(() => ({ detail: "Request failed" }));
              throw new Error(err.detail || "Request failed");
            }
            return retryResp.json();
          }
        } catch {
          this.clearTokens();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
        }
      }
      this.clearTokens();
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: `HTTP ${response.status} Error` }));
      throw new Error(err.detail || "An error occurred");
    }

    return response.json();
  }

  // --- Auth Endpoints ---
  async register(data: { email: string; username: string; password: string; display_name?: string }) {
    const res = await this.request<{ access_token: string; refresh_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
    this.setTokens(res.access_token, res.refresh_token);
    return res;
  }

  async login(data: { login: string; password: string }) {
    const res = await this.request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
    this.setTokens(res.access_token, res.refresh_token);
    return res;
  }

  async logout() {
    try {
      await this.request("/auth/logout", { method: "POST" });
    } finally {
      this.clearTokens();
    }
  }

  async requestPasswordReset(email: string) {
    return this.request<{ message: string }>("/auth/password-reset-request", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  }

  async confirmPasswordReset(token: string, new_password: string) {
    return this.request<{ message: string }>("/auth/password-reset-confirm", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    });
  }

  // --- User Profile Endpoints ---
  async getMe(): Promise<User> {
    return this.request<User>("/users/me");
  }

  async updateProfile(data: Partial<Profile>): Promise<Profile> {
    return this.request<Profile>("/users/me/profile", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async updatePreferences(data: Partial<UserPreference>): Promise<UserPreference> {
    return this.request<UserPreference>("/users/me/preferences", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async changePassword(current_password: string, new_password: string) {
    return this.request<{ message: string }>("/users/me/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    });
  }

  async deleteMyAccount(): Promise<{ message: string }> {
    return this.request<{ message: string }>("/users/me", { method: "DELETE" });
  }

  // --- Conversations ---
  async listConversations(params?: { archived?: boolean; search?: string }): Promise<ConversationSummary[]> {
    const query = new URLSearchParams();
    if (params?.archived !== undefined) query.set("archived", String(params.archived));
    if (params?.search) query.set("search", params.search);
    const qs = query.toString();
    return this.request<ConversationSummary[]>(`/conversations${qs ? `?${qs}` : ""}`);
  }

  async createConversation(data?: {
    title?: string;
    model_id?: string;
    reasoning_mode?: boolean;
    web_search_enabled?: boolean;
  }): Promise<ConversationDetail> {
    return this.request<ConversationDetail>("/conversations", {
      method: "POST",
      body: JSON.stringify(data || {}),
    });
  }

  async getConversation(id: string): Promise<ConversationDetail> {
    return this.request<ConversationDetail>(`/conversations/${id}`);
  }

  async updateConversation(
    id: string,
    data: { title?: string; is_pinned?: boolean; is_archived?: boolean; model_id?: string }
  ): Promise<ConversationDetail> {
    return this.request<ConversationDetail>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async togglePin(id: string): Promise<ConversationDetail> {
    return this.request<ConversationDetail>(`/conversations/${id}/pin`, { method: "POST" });
  }

  async toggleArchive(id: string): Promise<ConversationDetail> {
    return this.request<ConversationDetail>(`/conversations/${id}/archive`, { method: "POST" });
  }

  async deleteConversation(id: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/conversations/${id}`, { method: "DELETE" });
  }

  // --- Messages & Streaming ---
  async sendMessageStream(
    data: {
      content: string;
      conversation_id?: string;
      model?: string;
      reasoning_mode?: boolean;
      web_search?: boolean;
      attachment_ids?: string[];
      parent_id?: string;
    },
    onChunk: (event: StreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const url = this.getApiUrl("/messages");
    const token = this.getToken();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
      signal,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to send message" }));
      throw new Error(err.detail || "Failed to send message");
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body available for streaming");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          const raw = trimmed.slice(6);
          try {
            const event: StreamEvent = JSON.parse(raw);
            onChunk(event);
          } catch {
            // Ignored malformed event
          }
        }
      }
    }
  }

  async editMessage(messageId: string, content: string, regenerate = true): Promise<Message> {
    return this.request<Message>(`/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({ content, regenerate }),
    });
  }

  async regenerateMessage(
    messageId: string,
    onChunk: (event: StreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const url = this.getApiUrl(`/messages/${messageId}/regenerate`);
    const token = this.getToken();

    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      signal,
    });

    if (!response.ok) {
      throw new Error("Failed to regenerate response");
    }

    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          try {
            const event: StreamEvent = JSON.parse(trimmed.slice(6));
            onChunk(event);
          } catch {
            // ignore
          }
        }
      }
    }
  }

  async deleteMessage(messageId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/messages/${messageId}`, { method: "DELETE" });
  }

  // --- Feedback ---
  async submitFeedback(messageId: string, rating: "like" | "dislike", comment?: string): Promise<Feedback> {
    return this.request<Feedback>(`/feedback/messages/${messageId}`, {
      method: "POST",
      body: JSON.stringify({ rating, comment }),
    });
  }

  // --- Models ---
  async listModels(): Promise<ModelConfig[]> {
    return this.request<ModelConfig[]>("/models");
  }

  // --- Memories ---
  async listMemories(category?: string, project_id?: string) {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (project_id) params.append("project_id", project_id);
    return this.request<any[]>(`/memories?${params.toString()}`);
  }

  async createMemory(content: string, memory_type = "long_term", category = "fact") {
    return this.request<any>("/memories", {
      method: "POST",
      body: JSON.stringify({ content, memory_type, category }),
    });
  }

  async deleteMemory(memoryId: string) {
    return this.request<{ message: string }>(`/memories/${memoryId}`, { method: "DELETE" });
  }

  // --- RAG Knowledge Base ---
  async listRAGCollections(project_id?: string) {
    const params = project_id ? `?project_id=${project_id}` : "";
    return this.request<any[]>(`/rag/collections${params}`);
  }

  async createRAGCollection(name: string, description?: string) {
    return this.request<any>("/rag/collections", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    });
  }

  async ingestRAGDocument(collectionId: string, title: string, content: string) {
    return this.request<any>(`/rag/collections/${collectionId}/documents`, {
      method: "POST",
      body: JSON.stringify({ title, content }),
    });
  }

  // --- Router & Gateway Health ---
  async evaluateRoute(prompt: string, requested_model_id = "nexora-auto") {
    return this.request<any>("/router/evaluate", {
      method: "POST",
      body: JSON.stringify({ prompt, requested_model_id }),
    });
  }

  async getGatewayHealth() {
    return this.request<Record<string, any>>("/gateway/health");
  }

  // --- Attachments ---
  async uploadAttachment(file: File): Promise<Attachment> {
    const url = this.getApiUrl("/attachments/upload");
    const token = this.getToken();

    const formData = new FormData();
    formData.append("file", file);

    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "File upload failed" }));
      throw new Error(err.detail || "Upload failed");
    }

    return response.json();
  }

  // --- Generic HTTP Methods & Multimodal / Voice / Agent helpers ---
  async post<T = any>(endpoint: string, body?: any, customOptions: any = {}): Promise<{ data: T }> {
    const url = this.getApiUrl(endpoint);
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    let payload: any = body;
    if (!(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: payload,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || "Request failed");
    }

    if (customOptions?.responseType === "blob") {
      const blob = await response.blob();
      return { data: blob as any };
    }

    const json = await response.json();
    return { data: json };
  }

  async synthesizeVoice(text: string, voice = "alloy"): Promise<Blob> {
    const res = await this.post("/voice/synthesize", { text, voice }, { responseType: "blob" });
    return res.data;
  }

  async transcribeVoice(fileBlob: Blob): Promise<string> {
    const formData = new FormData();
    formData.append("file", fileBlob, "voice.webm");
    const res = await this.post<any>("/voice/transcribe", formData);
    return res.data?.data?.text || "";
  }

  async runAgentWorkflow(goal: string, context?: any) {
    return this.post<any>("/agents/run", { goal, context });
  }

  async getAgentsList() {
    return this.request<any>("/agents");
  }

  async listTools() {
    return this.request<any>("/tools");
  }

  // --- Model Lab Endpoints ---
  async getLabDashboard(): Promise<any> {
    return this.request<any>("/lab/dashboard");
  }

  async getLabModels(): Promise<any[]> {
    return this.request<any[]>("/lab/models");
  }

  async registerLabModel(data: any): Promise<any> {
    return this.request<any>("/lab/models", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async analyzeArchitecture(config: any): Promise<any> {
    return this.request<any>("/lab/models/analyze-architecture", {
      method: "POST",
      body: JSON.stringify(config),
    });
  }

  async getLabDatasets(): Promise<any[]> {
    return this.request<any[]>("/lab/datasets");
  }

  async uploadLabDataset(formData: FormData): Promise<any> {
    const url = this.getApiUrl("/lab/datasets/upload");
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Dataset upload failed" }));
      throw new Error(err.detail || "Dataset upload failed");
    }
    return resp.json();
  }

  async cleanLabDataset(datasetId: string, options: { redact_pii?: boolean; seed?: number } = {}): Promise<any> {
    return this.request<any>(`/lab/datasets/${datasetId}/clean`, {
      method: "POST",
      body: JSON.stringify(options),
    });
  }

  async getLabDatasetDetails(datasetId: string): Promise<any> {
    return this.request<any>(`/lab/datasets/${datasetId}`);
  }

  async getLabTokenizers(): Promise<any[]> {
    return this.request<any[]>("/lab/tokenizers");
  }

  async trainLabTokenizer(data: any): Promise<any> {
    return this.request<any>("/lab/tokenizers/train", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async evaluateLabTokenizer(data: { test_text: string; tokenizer_id?: string }) {
    return this.request<any>("/lab/tokenizers/evaluate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getLabExperiments(): Promise<any[]> {
    return this.request<any[]>("/lab/experiments");
  }

  async createLabExperiment(data: any): Promise<any> {
    return this.request<any>("/lab/experiments", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async startLabExperiment(experimentId: string): Promise<any> {
    return this.request<any>(`/lab/experiments/${experimentId}/start`, {
      method: "POST",
    });
  }

  async getLabExperimentDetails(experimentId: string): Promise<any> {
    return this.request<any>(`/lab/experiments/${experimentId}`);
  }

  async reproduceLabExperiment(experimentId: string): Promise<any> {
    return this.request<any>(`/lab/experiments/${experimentId}/reproduce`, {
      method: "POST",
    });
  }

  async getLabCheckpoints(): Promise<any[]> {
    return this.request<any[]>("/lab/checkpoints");
  }

  async getLabEvaluations(): Promise<any[]> {
    return this.request<any[]>("/lab/evaluations");
  }

  async runLabEvaluation(data: any): Promise<any> {
    return this.request<any>("/lab/evaluations/run", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Prompt 5: Training Jobs, Telemetry, Optimization, Checkpoints & Serving ---
  async getLabTelemetry(): Promise<any> {
    return this.request<any>("/lab/telemetry");
  }

  async getLabFrameworks(): Promise<any> {
    return this.request<any>("/lab/frameworks");
  }

  async verifyLabLicense(data: {
    base_model_license: string;
    dataset_license: string;
    intended_use: string;
    training_method: string;
  }): Promise<any> {
    return this.request<any>("/lab/licenses/verify", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getLabTrainingJobs(): Promise<any[]> {
    return this.request<any[]>("/lab/jobs");
  }

  async createLabTrainingJob(data: any): Promise<any> {
    return this.request<any>("/lab/jobs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async startLabTrainingJob(jobId: string): Promise<any> {
    return this.request<any>(`/lab/jobs/${jobId}/start`, { method: "POST" });
  }

  async pauseLabTrainingJob(jobId: string): Promise<any> {
    return this.request<any>(`/lab/jobs/${jobId}/pause`, { method: "POST" });
  }

  async resumeLabTrainingJob(jobId: string): Promise<any> {
    return this.request<any>(`/lab/jobs/${jobId}/resume`, { method: "POST" });
  }

  async recoverLabTrainingJob(jobId: string): Promise<any> {
    return this.request<any>(`/lab/jobs/${jobId}/recover`, { method: "POST" });
  }

  async cancelLabTrainingJob(jobId: string): Promise<any> {
    return this.request<any>(`/lab/jobs/${jobId}/cancel`, { method: "POST" });
  }

  async getLabTrainingJobLogs(jobId: string, tail = 200): Promise<{ job_id: string; status: string; logs: string }> {
    return this.request<any>(`/lab/jobs/${jobId}/logs?tail=${tail}`);
  }

  async validateLabCheckpoint(checkpointId: string): Promise<any> {
    return this.request<any>(`/lab/checkpoints/${checkpointId}/validate`, { method: "POST" });
  }

  async exportLabCheckpoint(checkpointId: string, format = "safetensors"): Promise<any> {
    return this.request<any>(`/lab/checkpoints/${checkpointId}/export?target_format=${format}`, { method: "POST" });
  }

  async rollbackLabCheckpoint(checkpointId: string, target_model_id?: string, reason?: string): Promise<any> {
    return this.request<any>(`/lab/checkpoints/${checkpointId}/rollback`, {
      method: "POST",
      body: JSON.stringify({ target_model_id, reason }),
    });
  }

  async getLabBenchmarks(): Promise<any[]> {
    return this.request<any[]>("/lab/benchmarks");
  }

  async runLabComparativeBenchmark(data: any): Promise<any> {
    return this.request<any>("/lab/benchmarks/compare", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async submitLabHumanRating(suiteId: string, data: any): Promise<any> {
    return this.request<any>(`/lab/benchmarks/${suiteId}/human-rating`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getLabOptimizations(): Promise<any[]> {
    return this.request<any[]>("/lab/optimizations");
  }

  async runLabOptimization(data: any): Promise<any> {
    return this.request<any>("/lab/optimizations/run", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getLabDeployments(): Promise<{ engines: any; deployments: any[] }> {
    return this.request<any>("/lab/deployments");
  }

  async deployLabCheckpoint(data: any): Promise<any> {
    return this.request<any>("/lab/deployments", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async stopLabDeployment(deploymentId: string): Promise<any> {
    return this.request<any>(`/lab/deployments/${deploymentId}/stop`, { method: "POST" });
  }

  async invokeOpenAIChatCompletion(model: string, prompt: string): Promise<any> {
    return this.request<any>("/inference/v1/chat/completions", {
      method: "POST",
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 48,
        temperature: 0.7,
        stream: false,
      }),
    });
  }

  async publishLabCheckpoint(
    checkpointId: string,
    data: {
      model_id: string;
      display_name: string;
      description?: string;
      min_plan_tier?: string;
      input_price_per_million?: number;
      output_price_per_million?: number;
    }
  ): Promise<any> {
    return this.request<any>(`/lab/checkpoints/${checkpointId}/publish`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Prompt 6: Billing & Subscriptions ---
  async getBillingPlans(): Promise<SubscriptionPlan[]> {
    return this.request<SubscriptionPlan[]>("/billing/plans");
  }

  async getMySubscription(): Promise<SubscriptionResponse> {
    return this.request<SubscriptionResponse>("/billing/subscription");
  }

  async subscribeToPlan(
    tier: string,
    billing_cycle: "monthly" | "annual" = "monthly",
    payment_method_summary = "Card ****4242"
  ): Promise<any> {
    return this.request<any>("/billing/subscribe", {
      method: "POST",
      body: JSON.stringify({ tier, billing_cycle, payment_method_summary }),
    });
  }

  async cancelSubscription(immediate = false): Promise<any> {
    return this.request<any>("/billing/cancel", {
      method: "POST",
      body: JSON.stringify({ immediate }),
    });
  }

  async getInvoices(): Promise<BillingInvoice[]> {
    return this.request<BillingInvoice[]>("/billing/invoices");
  }

  // --- Prompt 6: Developer Ecosystem & API Keys ---
  async getDeveloperKeys(): Promise<DeveloperApiKey[]> {
    return this.request<DeveloperApiKey[]>("/developer/keys");
  }

  async createDeveloperKey(data: {
    name: string;
    scopes?: string[];
    expires_in_days?: number;
  }): Promise<DeveloperApiKey> {
    return this.request<DeveloperApiKey>("/developer/keys", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async revokeDeveloperKey(keyId: string): Promise<any> {
    return this.request<any>(`/developer/keys/${keyId}/revoke`, { method: "POST" });
  }

  async rotateDeveloperKey(keyId: string): Promise<DeveloperApiKey> {
    return this.request<DeveloperApiKey>(`/developer/keys/${keyId}/rotate`, { method: "POST" });
  }

  async getDeveloperUsage(): Promise<DeveloperUsageResponse> {
    return this.request<DeveloperUsageResponse>("/developer/usage");
  }

  // --- Prompt 6: Admin Control Center ---
  async getAdminOverview(): Promise<any> {
    return this.request<any>("/admin/overview");
  }

  async getAdminUsers(): Promise<any[]> {
    return this.request<any[]>("/admin/users");
  }

  async updateAdminUser(userId: string, data: any): Promise<any> {
    return this.request<any>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async getAdminPlans(): Promise<SubscriptionPlan[]> {
    return this.request<SubscriptionPlan[]>("/admin/plans");
  }

  async updateAdminPlan(planId: string, data: any): Promise<SubscriptionPlan> {
    return this.request<SubscriptionPlan>(`/admin/plans/${planId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async getAdminModels(): Promise<any[]> {
    return this.request<any[]>("/admin/models");
  }

  async updateAdminModel(modelId: string, data: any): Promise<any> {
    return this.request<any>(`/admin/models/${modelId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async publishCheckpointAsAdmin(data: {
    checkpoint_id: string;
    model_id: string;
    display_name: string;
    description?: string;
    min_plan_tier?: string;
    input_price_per_million?: number;
    output_price_per_million?: number;
  }): Promise<any> {
    return this.request<any>("/admin/models/publish-checkpoint", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getAdminProviders(): Promise<any> {
    return this.request<any>("/admin/providers");
  }

  async getAdminAnalytics(): Promise<any> {
    return this.request<any>("/admin/analytics");
  }

  async getAdminTrainingAndGpu(): Promise<any> {
    return this.request<any>("/admin/training-and-gpu");
  }

  async getAdminAgentActivity(): Promise<any> {
    return this.request<any>("/admin/agent-activity");
  }

  async getAdminSecurityEvents(): Promise<any[]> {
    return this.request<any[]>("/admin/security-events");
  }

  async getAdminAuditLogs(): Promise<any[]> {
    return this.request<any[]>("/admin/audit-logs");
  }

  async getAdminSystemHealth(): Promise<any> {
    return this.request<any>("/admin/system-health");
  }
}

export const api = new ApiClient();

