"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConversationSummary } from "@/types/chat";
import { useAuth } from "@/hooks/useAuth";
import { NexoraWordmark } from "@/components/branding/NexoraWordmark";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { formatDateGroup } from "@/lib/utils";
import {
  Plus,
  Search,
  Pin,
  Archive,
  Trash2,
  Edit2,
  Check,
  X,
  User,
  LogOut,
  MoreVertical,
  SlidersHorizontal,
  ChevronLeft,
} from "lucide-react";

interface ChatSidebarProps {
  conversations: ConversationSummary[];
  activeId?: string;
  isOpen: boolean;
  onClose: () => void;
  onOpenSearch: () => void;
  onOpenShortcuts: () => void;
  onDeleteConversation: (id: string) => Promise<void>;
  onTogglePin: (id: string) => Promise<void>;
  onToggleArchive: (id: string) => Promise<void>;
  onRenameConversation: (id: string, newTitle: string) => Promise<void>;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  conversations,
  activeId,
  isOpen,
  onClose,
  onOpenSearch,
  onOpenShortcuts,
  onDeleteConversation,
  onTogglePin,
  onToggleArchive,
  onRenameConversation,
}) => {
  const router = useRouter();
  const { user, logout } = useAuth();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  // Filter conversations
  const filtered = conversations.filter((c) => (showArchived ? c.is_archived : !c.is_archived));
  const pinnedList = filtered.filter((c) => c.is_pinned);
  const unpinnedList = filtered.filter((c) => !c.is_pinned);

  // Group unpinned conversations by date
  const groups: Record<string, ConversationSummary[]> = {};
  unpinnedList.forEach((conv) => {
    const groupName = formatDateGroup(conv.updated_at);
    if (!groups[groupName]) groups[groupName] = [];
    groups[groupName].push(conv);
  });

  const handleStartRename = (conv: ConversationSummary) => {
    setEditingId(conv.id);
    setEditTitle(conv.title);
    setActiveMenuId(null);
  };

  const handleSaveRename = async (id: string) => {
    if (editTitle.trim()) {
      await onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleDelete = async (id: string) => {
    if (window.confirm("Are you sure you want to delete this conversation? This action cannot be undone.")) {
      await onDeleteConversation(id);
    }
    setActiveMenuId(null);
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 w-72 md:w-64 bg-slate-50 dark:bg-[#090d18] border-r border-slate-200 dark:border-slate-800/80 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Header Branding & Close */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200/60 dark:border-slate-800/60">
          <NexoraWordmark logoSize={26} />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white md:hidden"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Action Controls: New Chat & Search */}
        <div className="p-3 space-y-2">
          <button
            onClick={() => {
              router.push("/");
              onClose();
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-medium text-sm shadow-md transition-all duration-200 hover:scale-[1.02]"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>New Chat</span>
          </button>

          <button
            onClick={() => {
              onOpenSearch();
              onClose();
            }}
            className="w-full flex items-center justify-between py-2 px-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:border-slate-300 dark:hover:border-slate-700 text-xs transition-colors shadow-sm"
          >
            <div className="flex items-center gap-2">
              <Search className="w-3.5 h-3.5" />
              <span>Search chats...</span>
            </div>
            <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[10px] font-mono">
              ⌘K
            </kbd>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4 text-xs">
          {/* Pinned section */}
          {pinnedList.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 px-2 mb-1.5 text-[11px] font-semibold text-cyan-600 dark:text-cyan-400 uppercase tracking-wider">
                <Pin className="w-3 h-3 rotate-45" />
                <span>Pinned</span>
              </div>
              <div className="space-y-1">
                {pinnedList.map((conv) => renderItem(conv))}
              </div>
            </div>
          )}

          {/* Date groups */}
          {Object.entries(groups).map(([groupTitle, list]) => (
            <div key={groupTitle}>
              <div className="px-2 mb-1.5 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                {groupTitle}
              </div>
              <div className="space-y-1">
                {list.map((conv) => renderItem(conv))}
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="text-center py-8 text-slate-400 dark:text-slate-500 text-xs">
              {showArchived ? "No archived conversations" : "No conversations yet"}
            </div>
          )}
        </div>

        {/* Footer: Archive toggle & User Profile */}
        <div className="p-3 border-t border-slate-200/60 dark:border-slate-800/60 space-y-2">
          {/* Archive filter button */}
          <button
            onClick={() => setShowArchived(!showArchived)}
            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
              showArchived
                ? "bg-indigo-500/10 text-indigo-500 border border-indigo-500/20"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-900"
            }`}
          >
            <div className="flex items-center gap-2">
              <Archive className="w-3.5 h-3.5" />
              <span>{showArchived ? "Viewing Archive" : "Archived Chats"}</span>
            </div>
            {showArchived && <span className="text-[10px] font-bold">Active</span>}
          </button>

          {/* User Account / Profile button */}
          {user ? (
            <div className="flex items-center justify-between p-2 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800">
              <Link
                href="/profile"
                className="flex items-center gap-2.5 flex-1 min-w-0 hover:opacity-80 transition-opacity"
              >
                <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shadow-sm">
                  {user.username.slice(0, 1).toUpperCase()}
                </div>
                <div className="truncate">
                  <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                    {user.profile?.display_name || user.username}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">{user.email}</div>
                </div>
              </Link>
              <button
                onClick={logout}
                title="Log out"
                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Link
                href="/login"
                className="flex-1 text-center py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs font-semibold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
              >
                Log In
              </Link>
              <Link
                href="/register"
                className="flex-1 text-center py-2 rounded-xl bg-cyan-600 text-white text-xs font-semibold hover:bg-cyan-500 transition-colors"
              >
                Sign Up
              </Link>
            </div>
          )}
        </div>
      </aside>
    </>
  );

  function renderItem(conv: ConversationSummary) {
    const isActive = activeId === conv.id;
    const isEditing = editingId === conv.id;
    const isMenuOpen = activeMenuId === conv.id;

    if (isEditing) {
      return (
        <div key={conv.id} className="flex items-center gap-1 p-1 bg-white dark:bg-slate-900 rounded-xl border border-cyan-500 shadow-sm">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSaveRename(conv.id);
              if (e.key === "Escape") setEditingId(null);
            }}
            autoFocus
            className="flex-1 px-2 py-1 text-xs bg-transparent text-slate-900 dark:text-white focus:outline-none"
          />
          <button
            onClick={() => handleSaveRename(conv.id)}
            className="p-1 text-emerald-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setEditingId(null)}
            className="p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      );
    }

    return (
      <div key={conv.id} className="relative group">
        <Link
          href={`/c/${conv.id}`}
          onClick={onClose}
          className={`flex items-center justify-between w-full px-3 py-2 rounded-xl text-left transition-all ${
            isActive
              ? "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 font-semibold border border-cyan-500/30"
              : "text-slate-700 dark:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-800/60 border border-transparent"
          }`}
        >
          <span className="truncate pr-4 text-xs">{conv.title}</span>
          {conv.is_pinned && <Pin className="w-3 h-3 text-cyan-400 flex-shrink-0 rotate-45" />}
        </Link>

        {/* Options 3-dot trigger */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setActiveMenuId(isMenuOpen ? null : conv.id);
          }}
          className={`absolute right-2 top-2 p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-white transition-opacity ${
            isMenuOpen ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
        >
          <MoreVertical className="w-3.5 h-3.5" />
        </button>

        {/* Popover Menu */}
        {isMenuOpen && (
          <div className="absolute right-0 top-8 w-44 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xl p-1 z-30 animate-in fade-in zoom-in-95">
            <button
              onClick={() => handleStartRename(conv)}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-left"
            >
              <Edit2 className="w-3.5 h-3.5 text-slate-400" />
              <span>Rename</span>
            </button>
            <button
              onClick={() => {
                onTogglePin(conv.id);
                setActiveMenuId(null);
              }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-left"
            >
              <Pin className="w-3.5 h-3.5 text-slate-400" />
              <span>{conv.is_pinned ? "Unpin chat" : "Pin chat"}</span>
            </button>
            <button
              onClick={() => {
                onToggleArchive(conv.id);
                setActiveMenuId(null);
              }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-left"
            >
              <Archive className="w-3.5 h-3.5 text-slate-400" />
              <span>{conv.is_archived ? "Unarchive" : "Archive"}</span>
            </button>
            <div className="my-1 border-t border-slate-100 dark:border-slate-800" />
            <button
              onClick={() => handleDelete(conv.id)}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg text-left"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete</span>
            </button>
          </div>
        )}
      </div>
    );
  }
};

