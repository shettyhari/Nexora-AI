"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { useChat } from "@/hooks/useChat";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { MessageItem } from "@/components/chat/MessageItem";
import { SearchModal } from "@/components/modals/SearchModal";
import { ShortcutsModal } from "@/components/modals/ShortcutsModal";
import { AgentActivityDrawer } from "@/components/chat/AgentActivityDrawer";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { Menu, Command, AlertCircle, Globe, Loader2, Bot } from "lucide-react";
import { AgentWorkflowInfo } from "@/types/chat";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params?.id as string;

  const {
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
  } = useChat(conversationId);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [agentDrawerOpen, setAgentDrawerOpen] = useState(false);
  const [activeWorkflow, setActiveWorkflow] = useState<AgentWorkflowInfo | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-[#080d1a]">
      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeId={conversationId}
        onDeleteConversation={deleteConversation}
        onTogglePin={togglePin}
        onToggleArchive={toggleArchive}
        onRenameConversation={renameConversation}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenShortcuts={() => setShortcutsOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full min-w-0 relative">
        {/* Top Navbar */}
        <header className="h-14 border-b border-slate-100 dark:border-slate-800/60 px-4 flex items-center justify-between bg-white/70 dark:bg-[#080d1a]/70 backdrop-blur-md z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 -ml-2 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="md:hidden">
              <NexoraWordmark logoSize={24} />
            </div>
            {activeConversation && (
              <span className="hidden md:inline font-medium text-xs text-slate-700 dark:text-slate-300 truncate max-w-xs">
                {activeConversation.title}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setAgentDrawerOpen((prev) => !prev)}
              title="Toggle Multi-Agent Activity"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs font-medium transition-all ${
                agentDrawerOpen
                  ? "bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/30"
                  : "border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60"
              }`}
            >
              <Bot className="w-3.5 h-3.5 text-purple-400" />
              <span className="hidden sm:inline">Agents</span>
            </button>

            <button
              onClick={() => setShortcutsOpen(true)}
              title="Keyboard Shortcuts (⌘/)"
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60 text-xs transition-colors"
            >
              <Command className="w-3.5 h-3.5" />
              <span>Shortcuts</span>
            </button>
          </div>
        </header>

        {/* Global Error Banner */}
        {error && (
          <div className="px-4 py-2.5 bg-rose-500/10 border-b border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Web Search Status Pill */}
        {searchStatus && (
          <div className="px-4 py-2 bg-cyan-500/10 border-b border-cyan-500/20 text-cyan-600 dark:text-cyan-400 text-xs flex items-center gap-2 animate-pulse">
            <Globe className="w-3.5 h-3.5" />
            <span>{searchStatus}</span>
          </div>
        )}

        {/* Message Feed or Loading */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-cyan-500" />
            </div>
          ) : (
            <div className="flex-1 py-4">
              {messages.map((msg, idx) => (
                <MessageItem
                  key={msg.id || idx}
                  message={msg}
                  isStreaming={isGenerating && idx === messages.length - 1 && msg.role === "assistant"}
                  onEdit={editMessage}
                  onRegenerate={regenerateResponse}
                  onFeedback={submitFeedback}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat Composer */}
        <ChatComposer
          onSendMessage={sendMessage}
          onStop={stopGeneration}
          isGenerating={isGenerating}
          models={models}
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          reasoningMode={reasoningMode}
          onToggleReasoning={setReasoningMode}
          webSearchEnabled={webSearchEnabled}
          onToggleWebSearch={setWebSearchEnabled}
          onToggleAgentDrawer={() => setAgentDrawerOpen((prev) => !prev)}
        />
      </div>

      {/* Multi-Agent Activity Drawer */}
      <AgentActivityDrawer
        isOpen={agentDrawerOpen}
        onClose={() => setAgentDrawerOpen(false)}
        workflow={activeWorkflow}
      />

      {/* Modals */}
      <SearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        conversations={conversations}
      />
      <ShortcutsModal
        isOpen={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />
    </div>
  );
}
