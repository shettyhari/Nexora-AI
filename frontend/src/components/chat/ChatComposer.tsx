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
  Video as VideoIcon,
  Bot,
  Eye,
  Loader2,
} from "lucide-react";
import { ModelConfig } from "@/types/chat";
import { ModelSelector } from "./ModelSelector";
import { VoiceModeModal } from "@/components/modals/VoiceModeModal";
import { FilePreviewModal } from "@/components/modals/FilePreviewModal";
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
  onToggleAgentDrawer?: () => void;
  initialValue?: string;
}

interface LocalAttachment {
  id: string;
  name: string;
  type: string;
  url?: string;
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
  onToggleAgentDrawer,
  initialValue = "",
}) => {
  const [content, setContent] = useState(initialValue);
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState<LocalAttachment | null>(null);

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
        const mime = file.type || "";
        const fileType = mime.startsWith("image/")
          ? "image"
          : mime.startsWith("video/")
          ? "video"
          : "document";

        setAttachments((prev) => [
          ...prev,
          {
            id: uploaded.id,
            name: uploaded.file_name,
            type: fileType,
            url: URL.createObjectURL(file),
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

  const openPreview = (att: LocalAttachment) => {
    setPreviewAttachment(att);
    setPreviewModalOpen(true);
  };

  const handleVoiceTranscription = (text: string) => {
    setContent((prev) => (prev ? `${prev} ${text}` : text));
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4">
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
              ) : att.type === "video" ? (
                <VideoIcon className="w-3.5 h-3.5 text-amber-500" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-indigo-500" />
              )}
              <span className="truncate max-w-[140px] font-medium">{att.name}</span>
              <button
                onClick={() => openPreview(att)}
                className="p-0.5 rounded text-muted-foreground hover:text-foreground"
                title="Preview"
              >
                <Eye className="w-3 h-3" />
              </button>
              <button
                onClick={() => removeAttachment(att.id)}
                className="p-0.5 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                title="Remove"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Main Composer Box */}
      <div className="relative rounded-2xl border border-slate-200 dark:border-slate-800/80 bg-white/95 dark:bg-[#0e1628]/95 backdrop-blur-md shadow-xl transition-all focus-within:border-cyan-500/50 focus-within:ring-2 focus-within:ring-cyan-500/20">
        {/* Hidden file input supporting all multimodal types */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          multiple
          className="hidden"
          accept="image/*,video/*,.pdf,.docx,.xlsx,.csv,.pptx,.txt,.md,.json,.py,.ts,.tsx,.js"
        />

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message NEXORA, ask to research, analyze files, or write code... (Shift + Enter for new line)"
          rows={1}
          className="w-full pt-3.5 pb-2 px-4 bg-transparent text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 text-sm md:text-base focus:outline-none resize-none max-h-52 leading-relaxed"
        />

        {/* Controls Toolbar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          {/* Left Controls: Model, Attach, Research, Reason, Voice, Agent Drawer */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <ModelSelector
              models={models}
              selectedModelKey={selectedModel}
              onSelectModel={onSelectModel}
              disabled={isGenerating}
            />

            {/* Multimodal Attachment Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || isGenerating}
              aria-label="Attach file"
              title="Attach images, documents, audio, or video"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors disabled:opacity-50"
            >
              {uploading ? <Loader2 className="w-4 h-4 animate-spin text-cyan-500" /> : <Paperclip className="w-4 h-4" />}
            </button>

            {/* Web Research Toggle */}
            <button
              onClick={() => onToggleWebSearch(!webSearchEnabled)}
              disabled={isGenerating}
              aria-label="Web research mode"
              title={webSearchEnabled ? "Research Mode Active (Verified Citations)" : "Enable Web Research Mode"}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
                webSearchEnabled
                  ? "bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/30 shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent"
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Research</span>
            </button>

            {/* Deep Reasoning Toggle */}
            <button
              onClick={() => onToggleReasoning(!reasoningMode)}
              disabled={isGenerating}
              aria-label="Deep reasoning"
              title={reasoningMode ? "Deep Reasoning Active" : "Enable Deep Reasoning"}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
                reasoningMode
                  ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 border border-indigo-500/30 shadow-sm"
                  : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent"
              }`}
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Reason</span>
            </button>

            {/* Multi-Agent Orchestrator Drawer Toggle */}
            {onToggleAgentDrawer && (
              <button
                onClick={onToggleAgentDrawer}
                aria-label="Multi-agent activity"
                title="Open Autonomous Multi-Agent Workspace"
                className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-purple-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent transition-all"
              >
                <Bot className="w-3.5 h-3.5 text-purple-400" />
                <span className="hidden md:inline">Agents</span>
              </button>
            )}

            {/* Voice Mode Button */}
            <button
              onClick={() => setVoiceModalOpen(true)}
              aria-label="Voice input"
              title="Speak with Voice Intelligence"
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
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

      {/* Real Voice Mode Modal */}
      <VoiceModeModal
        isOpen={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
        onTranscribeComplete={handleVoiceTranscription}
      />

      {/* Multimodal File Preview Modal */}
      {previewAttachment && (
        <FilePreviewModal
          isOpen={previewModalOpen}
          onClose={() => setPreviewModalOpen(false)}
          fileName={previewAttachment.name}
          fileType={previewAttachment.type as any}
          fileUrl={previewAttachment.url}
        />
      )}
    </div>
  );
};
