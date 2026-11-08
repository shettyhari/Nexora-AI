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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const API_PREFIX = "/api/v1";

class ApiClient {
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
    const url = `${API_BASE}${API_PREFIX}${endpoint}`;
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
          const refreshResp = await fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
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
    const url = `${API_BASE}${API_PREFIX}/messages`;
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
    const url = `${API_BASE}${API_PREFIX}/messages/${messageId}/regenerate`;
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
    const url = `${API_BASE}${API_PREFIX}/attachments/upload`;
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
}

export const api = new ApiClient();

