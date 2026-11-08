"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  ArrowUp,
  Square,
  Paperclip,
  Globe,
  BrainCircuit,
  Mic,
  X,
  FileText,
  Image as ImageIcon,
} from "lucide-react";
import { ModelConfig } from "@/types/chat";
import { ModelSelector } from "./ModelSelector";
import { api } from "@/lib/api";

interface ChatComposerProps {
  onSendMessage: (content: string, attachmentIds?: string[]) => void;
  onStop: () => void;
  isGenerating: boolean;
  models: ModelConfig[];
  selectedModel: string;
  onSelectModel: (key: string) => void;
  reasoningMode: boolean;
  onToggleReasoning: (val: boolean) => void;
  webSearchEnabled: boolean;
  onToggleWebSearch: (val: boolean) => void;
  initialValue?: string;
}

interface LocalAttachment {
  id: string;
  name: string;
  type: string;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({
  onSendMessage,
  onStop,
  isGenerating,
  models,
  selectedModel,
  onSelectModel,
  reasoningMode,
  onToggleReasoning,
  webSearchEnabled,
  onToggleWebSearch,
  initialValue = "",
}) => {
  const [content, setContent] = useState(initialValue);
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialValue) {
      setContent(initialValue);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  }, [initialValue]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [content]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if ((!content.trim() && attachments.length === 0) || isGenerating) return;
    const attachmentIds = attachments.map((a) => a.id);
    onSendMessage(content, attachmentIds);
    setContent("");
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const uploaded = await api.uploadAttachment(file);
        setAttachments((prev) => [
          ...prev,
          {
            id: uploaded.id,
            name: uploaded.file_name,
            type: uploaded.file_type,
          },
        ]);
      }
    } catch (err: any) {
      alert(err.message || "Failed to upload file");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
      {/* Voice notice tooltip */}
      {voiceNotice && (
        <div className="mb-2 p-2 rounded-xl bg-slate-900 text-white text-xs text-center border border-slate-700 shadow-lg animate-in fade-in">
          Voice dictation integration is coming soon in NEXORA 2.0.
        </div>
      )}

      {/* Attachments preview tray */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 p-2 rounded-xl bg-slate-100/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
          {attachments.map((att) => (
            <div
              key={att.id}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-slate-800 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 shadow-sm"
            >
              {att.type === "image" ? (
                <ImageIcon className="w-3.5 h-3.5 text-cyan-500" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-indigo-500" />
              )}
              <span className="truncate max-w-[140px] font-medium">{att.name}</span>
              <button
                onClick={() => removeAttachment(att.id)}
                className="p-0.5 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative rounded-2xl border border-slate-200 dark:border-slate-800/80 bg-white/95 dark:bg-[#0e1628]/95 backdrop-blur-md shadow-xl transition-all focus-within:border-cyan-500/50 focus-within:ring-2 focus-within:ring-cyan-500/20">
        {/* Hidden file input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          multiple
          className="hidden"
          accept="image/*,.pdf,.txt,.md,.csv,.json,.py,.ts,.js"
        />

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message NEXORA... (Shift + Enter for new line)"
          rows={1}
          className="w-full pt-3.5 pb-2 px-4 bg-transparent text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm md:text-base focus:outline-none resize-none max-h-52 leading-relaxed"
        />

        {/* Controls Toolbar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          {/* Left Controls: Model, Attach, Search, Reason, Voice */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <ModelSelector
              models={models}
              selectedModelKey={selectedModel}
              onSelectModel={onSelectModel}
              disabled={isGenerating}
            />

            {/* Attachment Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || isGenerating}
              aria-label="Attach file"
              title="Attach files or images"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors disabled:opacity-50"
            >
              <Paperclip className="w-4 h-4" />
            </button>

            {/* Web Search Toggle */}
            <button
              onClick={() => onToggleWebSearch(!webSearchEnabled)}
              disabled={isGenerating}
              aria-label="Web search"
              title={webSearchEnabled ? "Web Search Active" : "Enable Web Search"}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
                webSearchEnabled
                  ? "bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/30"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent"
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Search</span>
            </button>

            {/* Deep Reasoning Toggle */}
            <button
              onClick={() => onToggleReasoning(!reasoningMode)}
              disabled={isGenerating}
              aria-label="Deep reasoning"
              title={reasoningMode ? "Deep Reasoning Active" : "Enable Deep Reasoning"}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
                reasoningMode
                  ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 border border-indigo-500/30"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent"
              }`}
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Reason</span>
            </button>

            {/* Voice Input Placeholder */}
            <button
              onClick={() => {
                setVoiceNotice(true);
                setTimeout(() => setVoiceNotice(false), 3000);
              }}
              aria-label="Voice input"
              title="Voice Input (Coming Soon)"
              className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
            >
              <Mic className="w-4 h-4" />
            </button>
          </div>

          {/* Right Controls: Send or Stop */}
          <div>
            {isGenerating ? (
              <button
                onClick={onStop}
                aria-label="Stop generation"
                title="Stop generation"
                className="p-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white shadow-md transition-all duration-200 hover:scale-105"
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!content.trim() && attachments.length === 0}
                aria-label="Send message"
                title="Send message"
                className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-md transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
