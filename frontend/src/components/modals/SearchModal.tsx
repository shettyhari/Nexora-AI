"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ConversationSummary } from "@/types/chat";
import { Search, X, MessageSquare, ArrowRight } from "lucide-react";

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: ConversationSummary[];
}

export const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, conversations }) => {
  const router = useRouter();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = query.trim()
    ? conversations.filter(
        (c) =>
          c.title.toLowerCase().includes(query.toLowerCase()) ||
          (c.last_message_preview && c.last_message_preview.toLowerCase().includes(query.toLowerCase()))
      )
    : conversations.slice(0, 8);

  const handleSelect = (id: string) => {
    router.push(`/c/${id}`);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0d1322] shadow-2xl overflow-hidden">
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
          <Search className="w-5 h-5 text-cyan-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations by title or topic..."
            autoFocus
            className="flex-1 bg-transparent text-slate-900 dark:text-white placeholder-slate-400 text-sm focus:outline-none"
          />
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length > 0 ? (
            filtered.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleSelect(conv.id)}
                className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800/60 text-left transition-colors group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 group-hover:text-cyan-400 transition-colors">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div className="truncate">
                    <div className="text-sm font-medium text-slate-800 dark:text-slate-200 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 truncate">
                      {conv.title}
                    </div>
                    {conv.last_message_preview && (
                      <div className="text-xs text-slate-400 truncate mt-0.5">
                        {conv.last_message_preview}
                      </div>
                    )}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0" />
              </button>
            ))
          ) : (
            <div className="py-8 text-center text-xs text-slate-400">
              No conversations found matching &quot;{query}&quot;
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
