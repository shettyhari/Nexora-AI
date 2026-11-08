"use client";

import React, { useState, useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { MessageItem } from "@/components/chat/MessageItem";
import { EmptyChatState } from "@/components/chat/EmptyChatState";
import { SearchModal } from "@/components/modals/SearchModal";
import { ShortcutsModal } from "@/components/modals/ShortcutsModal";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { Menu, Plus, Command, AlertCircle, Globe } from "lucide-react";

export default function ChatPage() {
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
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [composerInput, setComposerInput] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + K: Open Search
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      // Ctrl/Cmd + Shift + O: New Chat
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        window.location.href = "/";
      }
      // Ctrl/Cmd + /: Shortcuts cheatsheet
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        setShortcutsOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-[#080c14]">
      {/* Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeId={activeConversation?.id}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenShortcuts={() => setShortcutsOpen(true)}
        onDeleteConversation={deleteConversation}
        onTogglePin={togglePin}
        onToggleArchive={toggleArchive}
        onRenameConversation={renameConversation}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        {/* Top Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-slate-200/60 dark:border-slate-800/60 bg-white/60 dark:bg-[#090d18]/60 backdrop-blur-md z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60 md:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="md:hidden">
              <NexoraWordmark logoSize={24} />
            </div>
          </div>

          <div className="flex items-center gap-2">
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

        {/* Global Error Banner if any */}
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

        {/* Message Feed or Empty State */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col">
          {messages.length === 0 ? (
            <EmptyChatState onSelectPrompt={(prompt) => setComposerInput(prompt)} />
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
          initialValue={composerInput}
        />
      </div>

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

