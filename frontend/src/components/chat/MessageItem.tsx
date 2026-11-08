"use client";

import React, { useState } from "react";
import { Message } from "@/types/chat";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { ThinkingBlock } from "./ThinkingBlock";
import { NexoraLogo } from "@/components/branding/NexoraLogo";
import {
  Copy,
  Check,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Edit2,
  FileText,
  User as UserIcon,
} from "lucide-react";
import { copyToClipboard } from "@/lib/utils";

interface MessageItemProps {
  message: Message;
  isStreaming?: boolean;
  onEdit?: (messageId: string, newContent: string) => Promise<void>;
  onRegenerate?: (messageId: string) => void;
  onFeedback?: (messageId: string, rating: "like" | "dislike") => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isStreaming,
  onEdit,
  onRegenerate,
  onFeedback,
}) => {
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [submittingEdit, setSubmittingEdit] = useState(false);

  const isUser = message.role === "user";
  const userFeedback = message.feedback?.[0]?.rating;

  const handleCopy = async () => {
    const ok = await copyToClipboard(message.content);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSaveEdit = async () => {
    if (!editContent.trim() || !onEdit) return;
    setSubmittingEdit(true);
    try {
      await onEdit(message.id, editContent);
      setIsEditing(false);
    } finally {
      setSubmittingEdit(false);
    }
  };

  return (
    <div
      className={`group w-full py-5 px-4 md:px-6 transition-colors ${
        isUser
          ? "bg-transparent"
          : "bg-slate-50/70 dark:bg-[#0c1220]/60 border-y border-slate-100 dark:border-slate-800/40"
      }`}
    >
      <div className="max-w-3xl mx-auto flex items-start gap-4">
        {/* Avatar */}
        <div className="flex-shrink-0 mt-0.5">
          {isUser ? (
            <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 shadow-sm">
              <UserIcon className="w-4 h-4" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-slate-900 dark:bg-slate-950 flex items-center justify-center ring-1 ring-cyan-500/30 shadow-md">
              <NexoraLogo size={20} />
            </div>
          )}
        </div>

        {/* Message Content Container */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-xs text-slate-900 dark:text-slate-200">
              {isUser ? "You" : "NEXORA"}
            </span>
            {message.tokens_used > 0 && !isUser && (
              <span className="text-[10px] text-slate-400 font-mono">
                {message.tokens_used} tokens
              </span>
            )}
          </div>

          {/* Reasoning / Thinking Accordion */}
          {!isUser && message.reasoning_content && (
            <ThinkingBlock reasoning={message.reasoning_content} isStreaming={isStreaming} />
          )}

          {/* Attachments preview */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {message.attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-300 shadow-sm"
                >
                  <FileText className="w-3.5 h-3.5 text-cyan-500" />
                  <span className="truncate max-w-[150px]">{att.file_name}</span>
                </div>
              ))}
            </div>
          )}

          {/* Message Body or Edit Mode */}
          {isEditing ? (
            <div className="mt-2 space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={3}
                className="w-full p-3 rounded-xl border border-cyan-500/50 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/20 font-sans resize-none"
              />
              <div className="flex items-center gap-2 justify-end">
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={submittingEdit || !editContent.trim()}
                  className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
                >
                  {submittingEdit ? "Saving..." : "Save & Submit"}
                </button>
              </div>
            </div>
          ) : (
            <MarkdownRenderer content={message.content} isStreaming={isStreaming} />
          )}

          {/* Edited indicator */}
          {message.is_edited && !isEditing && (
            <span className="inline-block mt-1 text-[11px] text-slate-400 italic">
              (edited)
            </span>
          )}

          {/* Action Bar */}
          {!isEditing && (
            <div className="flex items-center gap-1.5 mt-2.5 text-slate-400 dark:text-slate-500 opacity-90 group-hover:opacity-100 transition-opacity">
              <button
                onClick={handleCopy}
                aria-label="Copy message"
                title="Copy message"
                className="p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

              {isUser && onEdit && (
                <button
                  onClick={() => setIsEditing(true)}
                  aria-label="Edit message"
                  title="Edit message"
                  className="p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
              )}

              {!isUser && !isStreaming && onRegenerate && (
                <button
                  onClick={() => onRegenerate(message.id)}
                  aria-label="Regenerate response"
                  title="Regenerate response"
                  className="p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              )}

              {!isUser && !isStreaming && onFeedback && (
                <>
                  <button
                    onClick={() => onFeedback(message.id, "like")}
                    aria-label="Thumbs up"
                    title="Good response"
                    className={`p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors ${
                      userFeedback === "like" ? "text-cyan-500 dark:text-cyan-400" : "hover:text-slate-700 dark:hover:text-slate-200"
                    }`}
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onFeedback(message.id, "dislike")}
                    aria-label="Thumbs down"
                    title="Bad response"
                    className={`p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors ${
                      userFeedback === "dislike" ? "text-rose-500" : "hover:text-slate-700 dark:hover:text-slate-200"
                    }`}
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
