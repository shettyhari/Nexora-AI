"""
NEXORA Foundation Model Families & Roadmap Definitions.
Defines standard research targets: NEXORA NANO, NEXORA CORE, and NEXORA PRO.
"""
from typing import Any, Dict, List


MODEL_FAMILIES_ROADMAP: List[Dict[str, Any]] = [
    {
        "id": "nexora-nano-v1",
        "name": "NEXORA NANO",
        "version": "1.0.0-research",
        "model_family": "nano",
        "architecture_type": "decoder-only",
        "base_model": "scratch",
        "license": "Proprietary-Research (Academic & Internal)",
        "description": "Lightweight, high-velocity research model optimized for rapid architectural experimentation, tokenizer benchmarking, and hyperparameter sensitivity searches.",
        "deployment_status": "registered",
        "architecture_config": {
            "vocab_size": 32000,
            "d_model": 512,
            "n_layers": 8,
            "n_heads": 8,
            "n_kv_heads": 4,  # Grouped Query Attention (2:1 ratio)
            "max_seq_len": 2048,
            "ffn_hidden_dim": 1376,  # SwiGLU 8/3 d_model rounded
            "norm_type": "rmsnorm",
            "norm_eps": 1e-5,
            "activation": "swiglu",
            "rotary_base": 10000.0,
            "tie_word_embeddings": False,
            "precision": "fp32"
        },
        "training_config": {
            "optimizer": "AdamW",
            "learning_rate": 3e-4,
            "min_learning_rate": 3e-5,
            "weight_decay": 0.1,
            "lr_scheduler": "cosine_with_warmup",
            "warmup_steps": 200,
            "batch_size": 32,
            "grad_accum_steps": 4,
            "clip_grad_norm": 1.0,
            "max_steps": 10000,
            "seed": 42
        },
        "evaluation_results": {
            "target_perplexity": 24.5,
            "benchmark_targets": ["WikiText-103", "LAMBADA", "PIQA-Mini"]
        },
        "dataset_associations": ["nexora-pretrain-curated-v1"]
    },
    {
        "id": "nexora-core-v1",
        "name": "NEXORA CORE",
        "version": "1.0.0-research",
        "model_family": "core",
        "architecture_type": "decoder-only",
        "base_model": "scratch",
        "license": "Proprietary-Commercial (Enterprise Self-Hosted)",
        "description": "General-purpose instruction foundation model engineered for balanced reasoning, code synthesis, cross-lingual knowledge retrieval, and tool orchestration.",
        "deployment_status": "draft",
        "architecture_config": {
            "vocab_size": 50000,
            "d_model": 2048,
            "n_layers": 24,
            "n_heads": 16,
            "n_kv_heads": 8,  # GQA
            "max_seq_len": 4096,
            "ffn_hidden_dim": 5504,
            "norm_type": "rmsnorm",
            "norm_eps": 1e-5,
            "activation": "swiglu",
            "rotary_base": 50000.0,
            "tie_word_embeddings": False,
            "precision": "bf16"
        },
        "training_config": {
            "optimizer": "AdamW",
            "learning_rate": 1.5e-4,
            "min_learning_rate": 1.5e-5,
            "weight_decay": 0.1,
            "lr_scheduler": "cosine_with_warmup",
            "warmup_steps": 2000,
            "batch_size": 64,
            "grad_accum_steps": 8,
            "clip_grad_norm": 1.0,
            "max_steps": 100000,
            "seed": 1337
        },
        "evaluation_results": {
            "target_perplexity": 12.2,
            "benchmark_targets": ["MMLU", "GSM8K", "HumanEval", "ARC-Challenge"]
        },
        "dataset_associations": ["nexora-pretrain-curated-v1", "nexora-code-instruct-v1"]
    },
    {
        "id": "nexora-pro-v1",
        "name": "NEXORA PRO",
        "version": "1.0.0-research",
        "model_family": "pro",
        "architecture_type": "decoder-only",
        "base_model": "scratch",
        "license": "Proprietary-Enterprise",
        "description": "Flagship research model designed for deep hierarchical reasoning, agentic planning, multi-step mathematics, and long-context comprehension.",
        "deployment_status": "draft",
        "architecture_config": {
            "vocab_size": 64000,
            "d_model": 4096,
            "n_layers": 36,
            "n_heads": 32,
            "n_kv_heads": 8,  # 4:1 GQA
            "max_seq_len": 8192,
            "ffn_hidden_dim": 11008,
            "norm_type": "rmsnorm",
            "norm_eps": 1e-5,
            "activation": "swiglu",
            "rotary_base": 500000.0,
            "tie_word_embeddings": False,
            "precision": "bf16"
        },
        "training_config": {
            "optimizer": "AdamW",
            "learning_rate": 8e-5,
            "min_learning_rate": 8e-6,
            "weight_decay": 0.1,
            "lr_scheduler": "cosine_with_warmup",
            "warmup_steps": 4000,
            "batch_size": 128,
            "grad_accum_steps": 16,
            "clip_grad_norm": 1.0,
            "max_steps": 500000,
            "seed": 2026
        },
        "evaluation_results": {
            "target_perplexity": 7.8,
            "benchmark_targets": ["MMLU-Pro", "MATH", "HumanEval-Plus", "GPQA"]
        },
        "dataset_associations": ["nexora-pretrain-curated-v1", "nexora-math-reasoning-v1"]
    }
]
