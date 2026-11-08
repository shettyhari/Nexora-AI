"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { ConversationDetail, ConversationSummary, Message, ModelConfig, StreamEvent } from "@/types/chat";
import { api } from "@/lib/api";

export function useChat(initialConversationId?: string) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("nexora-pro");
  const [reasoningMode, setReasoningMode] = useState<boolean>(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [searchStatus, setSearchStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load models catalog
  useEffect(() => {
    api.listModels().then(setModels).catch(console.error);
  }, []);

  // Fetch conversation summaries
  const refreshConversations = useCallback(async () => {
    try {
      const data = await api.listConversations();
      setConversations(data);
    } catch (err: any) {
      console.error("Failed to load conversations:", err);
    }
  }, []);

  // Load specific conversation
  const loadConversation = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const detail = await api.getConversation(id);
      setActiveConversation(detail);
      setMessages(detail.messages || []);
      setSelectedModel(detail.model_id || "nexora-pro");
      setReasoningMode(detail.reasoning_mode || false);
      setWebSearchEnabled(detail.web_search_enabled || false);
    } catch (err: any) {
      setError(err.message || "Failed to load conversation");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshConversations();
    if (initialConversationId) {
      loadConversation(initialConversationId);
    } else {
      setActiveConversation(null);
      setMessages([]);
      setLoading(false);
    }
  }, [initialConversationId, refreshConversations, loadConversation]);

  // Send message with streaming
  const sendMessage = async (
    content: string,
    attachmentIds?: string[]
  ) => {
    if (!content.trim() || isGenerating) return;

    setError(null);
    setIsGenerating(true);
    setSearchStatus(null);

    const tempUserMsgId = `temp_user_${Date.now()}`;
    const tempAsstMsgId = `temp_asst_${Date.now()}`;
    const nowIso = new Date().toISOString();

    const userMsg: Message = {
      id: tempUserMsgId,
      conversation_id: activeConversation?.id || "",
      role: "user",
      content,
      tokens_used: 0,
      is_edited: false,
      created_at: nowIso,
      updated_at: nowIso,
    };

    const asstMsg: Message = {
      id: tempAsstMsgId,
      conversation_id: activeConversation?.id || "",
      role: "assistant",
      content: "",
      reasoning_content: "",
      tokens_used: 0,
      is_edited: false,
      model: selectedModel,
      created_at: nowIso,
      updated_at: nowIso,
    };

    setMessages((prev) => [...prev, userMsg, asstMsg]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let resolvedConversationId = activeConversation?.id;

      await api.sendMessageStream(
        {
          content,
          conversation_id: resolvedConversationId,
          model: selectedModel,
          reasoning_mode: reasoningMode,
          web_search: webSearchEnabled,
          attachment_ids: attachmentIds,
        },
        (chunk: StreamEvent) => {
          if (chunk.type === "start" && chunk.conversation_id) {
            resolvedConversationId = chunk.conversation_id;
            if (!activeConversation) {
              refreshConversations();
            }
          } else if (chunk.type === "search_status") {
            setSearchStatus(chunk.content || "Searching the web...");
          } else if (chunk.type === "reasoning") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAsstMsgId
                  ? { ...m, reasoning_content: (m.reasoning_content || "") + (chunk.content || "") }
                  : m
              )
            );
          } else if (chunk.type === "token") {
            setSearchStatus(null);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAsstMsgId
                  ? { ...m, content: m.content + (chunk.content || "") }
                  : m
              )
            );
          } else if (chunk.type === "usage" && chunk.usage) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAsstMsgId
                  ? { ...m, tokens_used: chunk.usage?.total_tokens || 0 }
                  : m
              )
            );
          } else if (chunk.type === "error") {
            setError(chunk.content || "An error occurred during generation");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempAsstMsgId
                  ? { ...m, error: chunk.content, content: m.content || "Generation failed." }
                  : m
              )
            );
          }
        },
        controller.signal
      );

      // Refresh list to update message previews and titles
      await refreshConversations();
      if (resolvedConversationId && !activeConversation) {
        window.history.replaceState(null, "", `/c/${resolvedConversationId}`);
        await loadConversation(resolvedConversationId);
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setError(err.message || "Failed to communicate with AI service");
      }
    } finally {
      setIsGenerating(false);
      setSearchStatus(null);
      abortControllerRef.current = null;
    }
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsGenerating(false);
      setSearchStatus(null);
    }
  };

  const editMessage = async (messageId: string, newContent: string) => {
    try {
      const updated = await api.editMessage(messageId, newContent);
      setMessages((prev) => prev.map((m) => (m.id === messageId ? updated : m)));
    } catch (err: any) {
      setError(err.message || "Failed to edit message");
    }
  };

  const regenerateResponse = async (messageId: string) => {
    if (isGenerating) return;

    setIsGenerating(true);
    setError(null);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Clear target assistant content for real-time stream
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, content: "", reasoning_content: "" } : m))
    );

    try {
      await api.regenerateMessage(
        messageId,
        (chunk: StreamEvent) => {
          if (chunk.type === "reasoning") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === messageId
                  ? { ...m, reasoning_content: (m.reasoning_content || "") + (chunk.content || "") }
                  : m
              )
            );
          } else if (chunk.type === "token") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === messageId ? { ...m, content: m.content + (chunk.content || "") } : m
              )
            );
          } else if (chunk.type === "error") {
            setError(chunk.content || "Failed to regenerate");
          }
        },
        controller.signal
      );
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setError(err.message || "Regeneration failed");
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const submitFeedback = async (messageId: string, rating: "like" | "dislike", comment?: string) => {
    try {
      const fb = await api.submitFeedback(messageId, rating, comment);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, feedback: [fb] } : m
        )
      );
    } catch (err: any) {
      console.error("Failed to submit feedback:", err);
    }
  };

  const deleteConversation = async (id: string) => {
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversation?.id === id) {
      setActiveConversation(null);
      setMessages([]);
      window.location.href = "/";
    }
  };

  const togglePin = async (id: string) => {
    const updated = await api.togglePin(id);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, is_pinned: updated.is_pinned } : c))
    );
  };

  const toggleArchive = async (id: string) => {
    const updated = await api.toggleArchive(id);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, is_archived: updated.is_archived } : c))
    );
  };

  const renameConversation = async (id: string, title: string) => {
    const updated = await api.updateConversation(id, { title });
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: updated.title } : c))
    );
    if (activeConversation?.id === id) {
      setActiveConversation((prev) => (prev ? { ...prev, title: updated.title } : null));
    }
  };

  return {
    conversations,
    activeConversation,
    messages,
    models,
    selectedModel,
    setSelectedModel,
    reasoningMode,
    setReasoningMode,
    webSearchEnabled,
    setWebSearchEnabled,
    isGenerating,
    searchStatus,
    loading,
    error,
    sendMessage,
    stopGeneration,
    editMessage,
    regenerateResponse,
    submitFeedback,
    deleteConversation,
    togglePin,
    toggleArchive,
    renameConversation,
    refreshConversations,
    loadConversation,
  };
}
