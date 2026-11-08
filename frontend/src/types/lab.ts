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
  experiment_id: string;
  step: number;
  epoch: number;
  train_loss: number;
  val_loss: number;
  perplexity: number;
  learning_rate: number;
  storage_path: string;
  weights_sha256: string;
  is_best: boolean;
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
