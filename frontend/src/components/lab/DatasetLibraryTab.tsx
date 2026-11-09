"use client";

import React, { useState } from "react";
import { LabDataset } from "@/types/lab";
import { Database, Plus, ShieldCheck, Sparkles, Filter, CheckCircle2, AlertTriangle, FileText } from "lucide-react";
import { api } from "@/lib/api";

interface DatasetLibraryTabProps {
  datasets: LabDataset[];
  onRefresh: () => void;
}

export const DatasetLibraryTab: React.FC<DatasetLibraryTabProps> = ({ datasets, onRefresh }) => {
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0.0");
  const [description, setDescription] = useState("");
  const [license, setLicense] = useState("Apache-2.0");
  const [rawText, setRawText] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [cleaningId, setCleaningId] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<{ dataset: LabDataset; sample_preview: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("name", name);
      formData.append("version", version);
      formData.append("license", license);
      if (description) formData.append("description", description);
      if (file) formData.append("file", file);
      if (rawText) formData.append("raw_text", rawText);

      await api.uploadLabDataset(formData);
      setShowUploadModal(false);
      setName("");
      setRawText("");
      setFile(null);
      onRefresh();
    } catch (err: any) {
      setError(err.message || "Failed to upload dataset");
    } finally {
      setLoading(false);
    }
  };

  const handleClean = async (datasetId: string) => {
    setCleaningId(datasetId);
    try {
      await api.cleanLabDataset(datasetId, { redact_pii: true, seed: 42 });
      onRefresh();
    } catch (err: any) {
      alert(`Cleaning failed: ${err.message}`);
    } finally {
      setCleaningId(null);
    }
  };

  const handlePreview = async (datasetId: string) => {
    try {
      const data = await api.getLabDatasetDetails(datasetId);
      setPreviewData(data);
    } catch (err: any) {
      alert(`Failed to load preview: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Database className="w-5 h-5 text-cyan-400" />
            Curated Dataset Library & Provenance
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Ingestion, Unicode NFKC normalization, automated PII redaction, deduplication, and quality filtering.
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>Upload Dataset</span>
        </button>
      </div>

      {/* Datasets Table */}
      <div className="border border-border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
              <tr>
                <th className="px-4 py-3">Dataset Name</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">License & Format</th>
                <th className="px-4 py-3">Samples (Raw / Cleaned)</th>
                <th className="px-4 py-3">Train / Val / Test</th>
                <th className="px-4 py-3">PII Scan</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {datasets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    No datasets uploaded yet. Click &quot;Upload Dataset&quot; to begin.
                  </td>
                </tr>
              ) : (
                datasets.map((ds) => {
                  const pii = ds.pii_findings || {};
                  const totalPii = Object.values(pii).reduce((a, b) => a + Number(b), 0);

                  return (
                    <tr key={ds.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-foreground">{ds.name}</div>
                        <div className="text-[11px] font-mono text-muted-foreground">v{ds.version}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium capitalize ${
                            ds.status === "ready"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              ds.status === "ready" ? "bg-emerald-400" : "bg-amber-400"
                            }`}
                          />
                          {ds.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-foreground">{ds.license}</div>
                        <div className="text-[11px] uppercase text-muted-foreground">{ds.file_format}</div>
                      </td>
                      <td className="px-4 py-3 font-mono">
                        <div>{ds.num_samples_raw.toLocaleString()} raw</div>
                        <div className="text-emerald-400 font-semibold">
                          {ds.num_samples_cleaned.toLocaleString()} cleaned
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px]">
                        <div>Train: {ds.train_count.toLocaleString()}</div>
                        <div className="text-muted-foreground">
                          Val: {ds.val_count} | Test: {ds.test_count}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {totalPii > 0 ? (
                          <span className="inline-flex items-center gap-1 text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded text-[10px]">
                            <AlertTriangle className="w-3 h-3" />
                            {totalPii} Redacted
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded text-[10px]">
                            <ShieldCheck className="w-3 h-3" />
                            Clean
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        {ds.status === "uploaded" && (
                          <button
                            onClick={() => handleClean(ds.id)}
                            disabled={cleaningId === ds.id}
                            className="px-2.5 py-1 rounded bg-cyan-500 hover:bg-cyan-600 text-white text-[11px] font-medium transition-colors disabled:opacity-50"
                          >
                            {cleaningId === ds.id ? "Cleaning..." : "Run Pipeline"}
                          </button>
                        )}
                        <button
                          onClick={() => handlePreview(ds.id)}
                          className="px-2.5 py-1 rounded border border-border hover:bg-muted text-[11px] text-foreground transition-colors"
                        >
                          Preview
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <h3 className="text-base font-bold text-foreground mb-1">Upload & Register Training Dataset</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Upload JSONL, TXT, or paste samples. The system performs NFKC normalization and PII scanning.
            </p>

            {error && (
              <div className="p-3 mb-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleUpload} className="space-y-3.5">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Dataset Name</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., nexora-pretrain-v1"
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Version</label>
                  <input
                    type="text"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">License</label>
                <select
                  value={license}
                  onChange={(e) => setLicense(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none"
                >
                  <option value="Apache-2.0">Apache 2.0 (Permissive Commercial)</option>
                  <option value="MIT">MIT License</option>
                  <option value="OpenRAIL-M">OpenRAIL-M (Responsible AI)</option>
                  <option value="CC-BY-4.0">Creative Commons Attribution 4.0</option>
                  <option value="Proprietary-Curated">Proprietary Curated Internal</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Attach File (JSONL / TXT)</label>
                <input
                  type="file"
                  accept=".jsonl,.txt,.csv"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-muted-foreground file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:bg-cyan-500/10 file:text-cyan-400 hover:file:bg-cyan-500/20"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Or Paste Direct Text Samples</label>
                <textarea
                  rows={4}
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste raw pretraining documents or text lines..."
                  className="w-full px-3 py-1.5 rounded-lg border border-border bg-muted/40 text-xs outline-none resize-none font-mono text-[11px]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-xs font-medium disabled:opacity-50"
                >
                  {loading ? "Uploading..." : "Upload & Register"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewData && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl w-full max-w-2xl p-6 shadow-2xl relative max-h-[85vh] flex flex-col">
            <h3 className="text-base font-bold text-foreground">{previewData.dataset.name} – Sample Preview</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Provenance SHA-256: {previewData.dataset.provenance?.cleaned_sha256 || "N/A"}
            </p>

            <div className="flex-1 overflow-y-auto space-y-2 border border-border rounded-lg p-3 bg-muted/30 font-mono text-xs">
              {previewData.sample_preview.map((sample, idx) => (
                <div key={idx} className="p-2 rounded bg-card border border-border/50 text-[11px]">
                  <span className="text-muted-foreground mr-2 font-semibold">[{idx + 1}]</span>
                  <span>{sample}</span>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={() => setPreviewData(null)}
                className="px-4 py-1.5 rounded-lg bg-muted hover:bg-muted/80 text-foreground text-xs"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

