"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Check, Copy } from "lucide-react";
import { copyToClipboard } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

function isSafeHref(href?: string): boolean {
  if (!href) return false;
  const trimmed = href.trim();
  if (trimmed.startsWith("/") || trimmed.startsWith("#")) return true;
  try {
    const parsed = new URL(trimmed, "https://nexora.local");
    return parsed.protocol === "http:" || parsed.protocol === "https:" || parsed.protocol === "mailto:";
  } catch {
    return false;
  }
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, isStreaming }) => {
  return (
    <div className="prose dark:prose-invert prose-slate max-w-none text-sm md:text-base leading-relaxed break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            const language = match ? match[1] : "";
            const codeString = String(children).replace(/\n$/, "");

            if (!inline && language) {
              return <CodeBlock language={language} value={codeString} />;
            } else if (!inline) {
              return <CodeBlock language="text" value={codeString} />;
            }

            return (
              <code
                className="px-1.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800/80 text-cyan-700 dark:text-cyan-300 font-mono text-xs md:text-sm border border-slate-200 dark:border-slate-700/50"
                {...props}
              >
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <table className="w-full text-left text-sm border-collapse">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="bg-slate-100/80 dark:bg-slate-800/80 px-4 py-2.5 font-semibold text-slate-800 dark:text-slate-200 border-b border-slate-200 dark:border-slate-700">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="px-4 py-2 text-slate-700 dark:text-slate-300 border-b border-slate-100 dark:border-slate-800/60">
                {children}
              </td>
            );
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-3 pl-4 border-l-2 border-cyan-500 bg-cyan-50/30 dark:bg-cyan-950/20 py-1.5 pr-3 rounded-r-lg text-slate-700 dark:text-slate-300 italic">
                {children}
              </blockquote>
            );
          },
          a({ href, children }) {
            if (!isSafeHref(href)) {
              return (
                <span
                  title="Blocked unsafe URI scheme"
                  className="text-slate-400 underline decoration-dotted cursor-not-allowed"
                >
                  {children}
                </span>
              );
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-600 dark:text-cyan-400 hover:underline font-medium"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-1 bg-cyan-400 dark:bg-cyan-300 animate-pulse rounded-sm align-middle" />
      )}
    </div>
  );
};

const CodeBlock: React.FC<{ language: string; value: string }> = ({ language, value }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const ok = await copyToClipboard(value);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="relative my-4 rounded-xl border border-slate-200 dark:border-slate-800/80 bg-slate-950 text-slate-100 shadow-md overflow-hidden group">
      <div className="flex items-center justify-between px-4 py-1.5 bg-slate-900/90 border-b border-slate-800 text-xs text-slate-400 font-mono">
        <span className="uppercase tracking-wider font-semibold text-cyan-400">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-xs md:text-sm font-mono leading-relaxed">
        <code>{value}</code>
      </pre>
    </div>
  );
};

