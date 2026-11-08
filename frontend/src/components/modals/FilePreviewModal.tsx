"use client";

import React, { useState } from "react";
import { X, Play, Table, FileText, Video, Eye, Download, Copy, Check } from "lucide-react";
import { VideoSceneMarker, ExtractedTableInfo } from "@/types/chat";

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileUrl?: string;
  fileName: string;
  fileType: "image" | "video" | "document" | "table";
  tables?: ExtractedTableInfo[];
  videoMarkers?: VideoSceneMarker[];
  documentText?: string;
}

export const FilePreviewModal: React.FC<FilePreviewModalProps> = ({
  isOpen,
  onClose,
  fileUrl,
  fileName,
  fileType,
  tables = [],
  videoMarkers = [],
  documentText = "",
}) => {
  const [copied, setCopied] = useState(false);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const videoRef = React.useRef<HTMLVideoElement>(null);

  if (!isOpen) return null;

  const handleSeek = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
      setCurrentVideoTime(seconds);
    }
  };

  const handleCopy = () => {
    const textToCopy = tables.length > 0 ? tables.map((t) => t.markdown).join("\n\n") : documentText;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md animate-fade-in p-4 sm:p-6">
      <div className="w-full max-w-4xl max-h-[90vh] rounded-2xl border border-border bg-card shadow-2xl flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-nexora-indigo/10 text-nexora-indigo border border-nexora-indigo/20">
              {fileType === "image" && <Eye className="w-5 h-5" />}
              {fileType === "video" && <Video className="w-5 h-5" />}
              {fileType === "document" && <FileText className="w-5 h-5" />}
              {fileType === "table" && <Table className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="font-semibold text-foreground text-sm sm:text-base truncate max-w-md">
                {fileName}
              </h3>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">{fileType} intelligence preview</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {(tables.length > 0 || documentText) && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground bg-muted hover:bg-muted/80 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? "Copied" : "Copy Content"}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 1. Image Preview */}
          {fileType === "image" && fileUrl && (
            <div className="flex items-center justify-center bg-black/40 rounded-xl overflow-hidden p-4 border border-border">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={fileUrl}
                alt={fileName}
                className="max-h-[60vh] object-contain rounded-lg shadow-lg"
              />
            </div>
          )}

          {/* 2. Video Preview with Interactive Timestamp Controls */}
          {fileType === "video" && (
            <div className="space-y-4">
              <div className="relative rounded-xl overflow-hidden bg-black aspect-video border border-border flex items-center justify-center">
                {fileUrl ? (
                  <video
                    ref={videoRef}
                    src={fileUrl}
                    controls
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="text-center p-8 text-muted-foreground">
                    <Video className="w-12 h-12 mx-auto mb-2 opacity-40 text-nexora-indigo" />
                    <p className="text-sm">Video Media Stream Initialized</p>
                  </div>
                )}
              </div>

              {/* Timestamp Scene Navigation */}
              {videoMarkers.length > 0 && (
                <div className="rounded-xl border border-border bg-muted/20 p-4 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Play className="w-3.5 h-3.5 text-nexora-indigo" />
                    Scene Timeline & Jump-to-Timestamp:
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {videoMarkers.map((marker, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSeek(marker.timestamp_seconds)}
                        className="flex items-start gap-2.5 p-2.5 rounded-lg border border-border/60 bg-card hover:border-nexora-indigo/50 hover:bg-nexora-indigo/5 transition-all text-left group"
                      >
                        <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-nexora-indigo/15 text-nexora-indigo border border-nexora-indigo/30 shrink-0 group-hover:bg-nexora-indigo group-hover:text-white transition-colors">
                          {marker.timestamp_formatted}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-foreground truncate">{marker.label}</p>
                          <p className="text-[11px] text-muted-foreground line-clamp-1">{marker.description}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 3. Document Extracted Tables Viewer */}
          {tables.length > 0 && (
            <div className="space-y-4">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Table className="w-3.5 h-3.5 text-nexora-indigo" />
                Extracted Structured Tables ({tables.length}):
              </h4>
              <div className="space-y-4">
                {tables.map((table, tIdx) => (
                  <div key={tIdx} className="rounded-xl border border-border overflow-x-auto bg-card">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/60 text-muted-foreground font-semibold border-b border-border">
                        <tr>
                          {table.headers.map((h, hIdx) => (
                            <th key={hIdx} className="px-4 py-2.5 whitespace-nowrap">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {table.rows.map((row, rIdx) => (
                          <tr key={rIdx} className="hover:bg-muted/30 transition-colors">
                            {row.map((cell, cIdx) => (
                              <td key={cIdx} className="px-4 py-2 text-foreground/90 whitespace-nowrap">
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. Document Text Preview */}
          {documentText && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-nexora-indigo" />
                Document Content:
              </h4>
              <div className="rounded-xl border border-border bg-muted/20 p-4 font-mono text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed max-h-[40vh] overflow-y-auto">
                {documentText}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
