"use client";

import React, { useState, useEffect, useCallback } from "react";
import { LabHeader, LabTab } from "@/components/lab/LabHeader";
import { ModelRegistryTab } from "@/components/lab/ModelRegistryTab";
import { DatasetLibraryTab } from "@/components/lab/DatasetLibraryTab";
import { TokenizerLabTab } from "@/components/lab/TokenizerLabTab";
import { ArchitectureWorkbenchTab } from "@/components/lab/ArchitectureWorkbenchTab";
import { ExperimentHistoryTab } from "@/components/lab/ExperimentHistoryTab";
import { TrainingConfigTab } from "@/components/lab/TrainingConfigTab";
import { CheckpointBrowserTab } from "@/components/lab/CheckpointBrowserTab";
import { EvaluationHistoryTab } from "@/components/lab/EvaluationHistoryTab";
import {
  LabDashboardData,
  LabModel,
  LabDataset,
  LabTokenizer,
  LabExperiment,
  LabCheckpoint,
  LabEvaluation
} from "@/types/lab";
import { api } from "@/lib/api";

export default function ModelLabPage() {
  const [activeTab, setActiveTab] = useState<LabTab>("models");
  const [dashboard, setDashboard] = useState<LabDashboardData | null>(null);
  const [models, setModels] = useState<LabModel[]>([]);
  const [datasets, setDatasets] = useState<LabDataset[]>([]);
  const [tokenizers, setTokenizers] = useState<LabTokenizer[]>([]);
  const [experiments, setExperiments] = useState<LabExperiment[]>([]);
  const [checkpoints, setCheckpoints] = useState<LabCheckpoint[]>([]);
  const [evaluations, setEvaluations] = useState<LabEvaluation[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAllData = useCallback(async () => {
    try {
      const [dashRes, mRes, dRes, tRes, eRes, cRes, evRes] = await Promise.allSettled([
        api.getLabDashboard(),
        api.getLabModels(),
        api.getLabDatasets(),
        api.getLabTokenizers(),
        api.getLabExperiments(),
        api.getLabCheckpoints(),
        api.getLabEvaluations(),
      ]);

      if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
      if (mRes.status === "fulfilled") setModels(mRes.value);
      if (dRes.status === "fulfilled") setDatasets(dRes.value);
      if (tRes.status === "fulfilled") setTokenizers(tRes.value);
      if (eRes.status === "fulfilled") setExperiments(eRes.value);
      if (cRes.status === "fulfilled") setCheckpoints(cRes.value);
      if (evRes.status === "fulfilled") setEvaluations(evRes.value);
    } catch (err) {
      console.error("Failed to load Model Lab data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <LabHeader
        activeTab={activeTab}
        onTabChange={setActiveTab}
        environment={dashboard?.environment}
        counts={{
          models: models.length,
          datasets: datasets.length,
          experiments: experiments.length,
          checkpoints: checkpoints.length
        }}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-3">
            <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-muted-foreground font-mono">Loading Foundation Model Lab...</p>
          </div>
        ) : (
          <>
            {activeTab === "models" && <ModelRegistryTab models={models} onRefresh={fetchAllData} />}
            {activeTab === "datasets" && <DatasetLibraryTab datasets={datasets} onRefresh={fetchAllData} />}
            {activeTab === "tokenizers" && <TokenizerLabTab tokenizers={tokenizers} onRefresh={fetchAllData} />}
            {activeTab === "architecture" && <ArchitectureWorkbenchTab />}
            {activeTab === "experiments" && (
              <ExperimentHistoryTab experiments={experiments} onRefresh={fetchAllData} />
            )}
            {activeTab === "training" && (
              <TrainingConfigTab
                models={models}
                datasets={datasets}
                onExperimentStarted={() => {
                  fetchAllData();
                  setActiveTab("experiments");
                }}
              />
            )}
            {activeTab === "checkpoints" && <CheckpointBrowserTab checkpoints={checkpoints} />}
            {activeTab === "evaluations" && (
              <EvaluationHistoryTab
                evaluations={evaluations}
                experiments={experiments}
                onRefresh={fetchAllData}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
