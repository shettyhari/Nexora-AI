export interface ArchitectureConfig {
  vocab_size: number;
  d_model: number;
  n_layers: number;
  n_heads: number;
  n_kv_heads?: number;
  max_seq_len: number;
  ffn_hidden_dim?: number;
  norm_type: "rmsnorm" | "layernorm";
  activation: "swiglu" | "gelu" | "silu" | "relu";
  rotary_base: number;
  tie_word_embeddings: boolean;
  precision: "fp32" | "fp16" | "bf16";
}

export interface ArchitectureAnalysis {
  total_parameters: number;
  total_parameters_formatted: string;
  non_embedding_parameters: number;
  non_embedding_formatted: string;
  breakdown: {
    token_embeddings: number;
    attention_all_layers: number;
    attention_per_layer: number;
    ffn_all_layers: number;
    ffn_per_layer: number;
    norms_all_layers: number;
    lm_head: number;
    is_tied_embeddings: boolean;
  };
  flops: {
    forward_flops_per_token: number;
    training_flops_per_token: number;
    chinchilla_recommended_tokens: number;
    chinchilla_training_petaflops: number;
  };
  memory: {
    weights_mb: number;
    weights_gb: number;
    kv_cache_per_sequence_mb: number;
    precision: string;
  };
}

export interface LabModel {
  id: string;
  name: string;
  version: string;
  model_family: "nano" | "core" | "pro" | "custom";
  architecture_type: string;
  parameter_count: number;
  base_model: string;
  license: string;
  description?: string;
  architecture_config: ArchitectureConfig;
  training_config: Record<string, any>;
  evaluation_results: Record<string, any>;
  dataset_associations: string[];
  deployment_status: "draft" | "training" | "evaluating" | "registered" | "deployed" | "archived";
  checkpoint_count: number;
  created_at: string;
  updated_at: string;
}

export interface LabDataset {
  id: string;
  name: string;
  version: string;
  description?: string;
  source_uri: string;
  source_type: "upload" | "curated" | "synthetic" | "scraped";
  license: string;
  file_format: "jsonl" | "txt" | "csv" | "parquet";
  raw_size_bytes: number;
  cleaned_size_bytes: number;
  num_samples_raw: number;
  num_samples_cleaned: number;
  train_count: number;
  val_count: number;
  test_count: number;
  language_distribution: Record<string, number>;
  pii_findings: Record<string, number>;
  cleaning_stats: Record<string, any>;
  provenance: Record<string, any>;
  status: "uploaded" | "cleaning" | "ready" | "error";
  storage_path: string;
  created_at: string;
  updated_at: string;
}

export interface LabTokenizer {
  id: string;
  name: string;
  version: string;
  algorithm: "bpe" | "unigram_sentencepiece";
  vocab_size: number;
  special_tokens: string[];
  training_corpus_id?: string;
  vocab_data: {
    merges_count: number;
    merges_sample: string[][];
    vocab_sample: Record<number, string>;
  };
  evaluation_metrics: {
    fertility: number;
    compression_ratio: number;
    tokens_per_word: number;
    unknown_rate: number;
    total_tokens: number;
    total_words: number;
    total_bytes: number;
  };
  status: string;
  created_at: string;
}

export interface LabExperiment {
  id: string;
  name: string;
  description?: string;
  model_id?: string;
  model_name: string;
  dataset_id?: string;
  dataset_version: string;
  tokenizer_id?: string;
  hyperparameters: {
    learning_rate: number;
    optimizer: string;
    batch_size: number;
    grad_accum_steps: number;
    max_steps: number;
    seed: number;
    warmup_steps?: number;
    weight_decay?: number;
  };
  reproducibility_env: Record<string, any>;
  status: "created" | "running" | "completed" | "failed" | "aborted";
  duration_seconds: number;
  current_step: number;
  max_steps: number;
  best_val_loss?: number;
  best_perplexity?: number;
  loss_history: Array<{
    step: number;
    train_loss: number;
    val_loss: number;
    perplexity: number;
    lr: number;
  }>;
  notes?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface LabCheckpoint {
  id: string;
  experiment_id?: string;
  training_job_id?: string;
  step: number;
  epoch: number;
  version: string;
  format: string;
  train_loss: number;
  val_loss: number;
  perplexity: number;
  learning_rate: number;
  storage_path: string;
  weights_sha256: string;
  is_best: boolean;
  is_adapter_only: boolean;
  adapter_config: Record<string, any>;
  validated: boolean;
  validation_report: Record<string, any>;
  export_path?: string;
  parent_checkpoint_id?: string;
  is_active_rollback_target: boolean;
  created_at: string;
}

export interface HardwareTelemetry {
  timestamp: number;
  platform: string;
  accelerator: "cuda" | "mps" | "cpu";
  gpu_available: boolean;
  gpu_count: number;
  gpu_status: string;
  cuda_version?: string;
  torch_version?: string;
  gpus: Array<{
    index: number;
    name: string;
    backend: string;
    driver_version?: string;
    gpu_utilization_pct?: number | null;
    memory_utilization_pct?: number | null;
    memory_used_mb?: number | null;
    memory_free_mb?: number | null;
    memory_total_mb?: number | null;
    temperature_c?: number | null;
    power_draw_w?: number | null;
  }>;
  cpu: {
    utilization_pct: number;
    cores_logical: number;
    cores_physical: number;
    frequency_mhz?: number | null;
  };
  memory: {
    ram_total_gb: number;
    ram_used_gb: number;
    ram_available_gb: number;
    ram_utilization_pct: number;
  };
  disk: {
    total_gb: number;
    free_gb: number;
  };
}

export interface LicenseVerificationResult {
  approved: boolean;
  intended_use: string;
  training_method: string;
  base_model_license: string;
  dataset_license: string;
  errors: string[];
  warnings: string[];
  obligations: string[];
}

export interface LabTrainingJob {
  id: string;
  name: string;
  experiment_id?: string;
  base_model_id: string;
  base_model_name: string;
  base_model_license: string;
  dataset_id?: string;
  dataset_name: string;
  dataset_license: string;
  intended_use: string;
  training_method: "sft" | "instruction" | "lora" | "qlora" | "dpo" | "grpo" | "pretrain";
  framework: "trl" | "transformers" | "peft" | "accelerate" | "deepspeed" | "nemo" | "pytorch";
  framework_config: Record<string, any>;
  lora_config: Record<string, any>;
  hyperparameters: Record<string, any>;
  license_verified: boolean;
  license_report: LicenseVerificationResult;
  status: "queued" | "scheduled" | "running" | "paused" | "completed" | "failed" | "cancelled";
  priority: number;
  worker_pid?: number;
  device_type: string;
  gpu_required: boolean;
  current_step: number;
  total_steps: number;
  tokens_processed: number;
  tokens_per_sec: number;
  current_train_loss?: number;
  current_val_loss?: number;
  current_lr?: number;
  loss_history: Array<{
    step: number;
    train_loss: number;
    val_loss: number;
    perplexity: number;
    lr: number;
    grad_norm?: number;
    tokens_per_sec?: number;
  }>;
  hardware_snapshot: Record<string, any>;
  checkpoint_dir: string;
  log_file_path: string;
  output_checkpoint_id?: string;
  checkpoint_validated: boolean;
  error_message?: string;
  recovery_attempts: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface LabBenchmarkSuite {
  id: string;
  name: string;
  version: string;
  candidate_model_name: string;
  candidate_checkpoint_id?: string;
  baseline_model_name: string;
  baseline_checkpoint_id?: string;
  dataset_id?: string;
  leakage_checked: boolean;
  leakage_overlap_count: number;
  leakage_blocked: boolean;
  leakage_report: Record<string, any>;
  dimension_scores: Record<string, { score: number; perplexity: number; avg_latency_ms: number; measured_via_forward_pass: boolean }>;
  baseline_scores: Record<string, { score: number; perplexity: number; avg_latency_ms: number; measured_via_forward_pass: boolean }>;
  deltas: Record<string, number>;
  regression_passed: boolean;
  regression_failures: string[];
  human_ratings: Array<{
    evaluator: string;
    prompt: string;
    preference: string;
    coherence: number;
    helpfulness: number;
    safety_pass: boolean;
    notes?: string;
    timestamp: number;
  }>;
  aggregate_candidate_score: number;
  aggregate_baseline_score: number;
  created_at: string;
}

export interface LabOptimizationRun {
  id: string;
  checkpoint_id?: string;
  model_name: string;
  target_precision: string;
  batch_size: number;
  context_length: number;
  kv_cache_enabled: boolean;
  original_size_mb: number;
  optimized_size_mb: number;
  compression_ratio: number;
  ttft_ms: number;
  tokens_per_sec: number;
  peak_memory_mb: number;
  context_scaling_results: Array<{ seq_len: number; prefill_latency_ms: number; prefill_tok_per_sec: number }>;
  batch_scaling_results: Array<{ batch_size: number; latency_ms: number; throughput_tok_per_sec: number }>;
  artifact_path: string;
  status: string;
  created_at: string;
}

export interface LabInferenceDeployment {
  id: string;
  model_alias: string;
  checkpoint_id?: string;
  model_name: string;
  engine: string;
  quantization: string;
  device: string;
  max_model_len: number;
  max_concurrent_requests: number;
  gpu_memory_utilization: number;
  status: string;
  requests_served: number;
  active_queue_depth: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  avg_latency_ms: number;
  created_at: string;
}

export interface LabEvaluation {
  id: string;
  experiment_id: string;
  checkpoint_id?: string;
  benchmark_name: string;
  metrics: {
    perplexity: number;
    cross_entropy_loss: number;
    accuracy: number;
    eval_tokens: number;
    bits_per_byte: number;
  };
  sample_generations: Array<{
    prompt: string;
    completion: string;
  }>;
  created_at: string;
}

export interface LabDashboardData {
  status: string;
  models_count: number;
  datasets_count: number;
  experiments_count: number;
  checkpoints_count: number;
  model_families: {
    nano: number;
    core: number;
    pro: number;
    custom: number;
  };
  environment: Record<string, any>;
}

