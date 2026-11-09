"""
Analytical Parameter Counter & FLOPs Estimator.
Calculates exact parameter counts, training/inference FLOPs, and memory footprints.
"""
from typing import Any, Dict
from app.lab.architecture.config import TransformerConfig


class ParameterCounter:
    """
    Computes exact parameter counts, FLOPs requirements, and memory estimates
    for any decoder-only Transformer configuration.
    """

    @classmethod
    def analyze(cls, config: TransformerConfig) -> Dict[str, Any]:
        """
        Performs exhaustive mathematical component breakdown of parameters,
        FLOPs per token, and memory footprints.
        """
        v = config.vocab_size
        d = config.d_model
        l = config.n_layers
        h = config.n_heads
        kv_h = config.n_kv_heads or h
        d_head = d // h
        ffn_d = config.ffn_hidden_dim or int(2 * (4 * d) / 3)

        # 1. Token Embeddings
        # Shape: [vocab_size, d_model]
        embedding_params = v * d

        # 2. Attention Layers (per layer)
        # W_q: [d_model, d_model]
        wq_params = d * d
        # W_k: [d_model, n_kv_heads * d_head]
        wk_params = d * (kv_h * d_head)
        # W_v: [d_model, n_kv_heads * d_head]
        wv_params = d * (kv_h * d_head)
        # W_out: [d_model, d_model]
        wo_params = d * d
        attn_params_per_layer = wq_params + wk_params + wv_params + wo_params

        # 3. Feed-Forward Network (per layer)
        if config.activation == "swiglu":
            # SwiGLU uses 3 linear projections: W_gate, W_up, W_down
            w_gate = d * ffn_d
            w_up = d * ffn_d
            w_down = ffn_d * d
            ffn_params_per_layer = w_gate + w_up + w_down
        else:
            # Standard MLP (e.g. GELU): W_1 [d, ffn], W_2 [ffn, d]
            w1 = d * ffn_d
            w2 = ffn_d * d
            ffn_params_per_layer = w1 + w2

        # 4. Normalization (per layer)
        # RMSNorm has 1 scale parameter per feature dimension; LayerNorm has scale + bias (2*d)
        norm_params_per_block = d if config.norm_type == "rmsnorm" else (2 * d)
        # 2 normalization layers per transformer block: pre-attention and pre-ffn
        norm_params_per_layer = 2 * norm_params_per_block

        # Total single Transformer block
        single_block_params = attn_params_per_layer + ffn_params_per_layer + norm_params_per_layer
        all_blocks_params = single_block_params * l

        # 5. Final Normalization
        final_norm_params = norm_params_per_block

        # 6. LM Output Head
        # Shape: [d_model, vocab_size] (0 if weights are tied to embeddings)
        lm_head_params = 0 if config.tie_word_embeddings else (d * v)

        # Total parameters
        total_parameters = embedding_params + all_blocks_params + final_norm_params + lm_head_params

        # Non-embedding parameters (often used in scaling law literature)
        non_embedding_parameters = all_blocks_params + final_norm_params + (0 if config.tie_word_embeddings else lm_head_params)

        # 7. FLOPs Estimation
        # Forward pass FLOPs per token: ~ 2 * P (where P is non-embedding params, plus attention matrix ops)
        forward_flops_per_token = 2 * total_parameters
        # Backward pass is ~ 2x forward pass: ~ 4 * P
        backward_flops_per_token = 4 * total_parameters
        total_training_flops_per_token = 6 * total_parameters

        # Compute for standard Chinchilla optimal tokens (20 * P)
        chinchilla_tokens = 20 * total_parameters
        chinchilla_training_flops = total_training_flops_per_token * chinchilla_tokens

        # 8. Memory Footprint Estimation (in MegaBytes and GigaBytes)
        bytes_per_param = 4 if config.precision == "fp32" else 2  # fp16/bf16 = 2 bytes
        model_weights_mb = round((total_parameters * bytes_per_param) / (1024 * 1024), 2)
        model_weights_gb = round(model_weights_mb / 1024, 3)

        # KV Cache per token per sequence: 2 (K and V) * n_layers * n_kv_heads * head_dim * bytes_per_param
        kv_cache_bytes_per_token = 2 * l * kv_h * d_head * bytes_per_param
        kv_cache_per_seq_mb = round((kv_cache_bytes_per_token * config.max_seq_len) / (1024 * 1024), 2)

        return {
            "total_parameters": total_parameters,
            "total_parameters_formatted": cls._format_param_count(total_parameters),
            "non_embedding_parameters": non_embedding_parameters,
            "non_embedding_formatted": cls._format_param_count(non_embedding_parameters),
            "breakdown": {
                "token_embeddings": embedding_params,
                "attention_all_layers": attn_params_per_layer * l,
                "attention_per_layer": attn_params_per_layer,
                "ffn_all_layers": ffn_params_per_layer * l,
                "ffn_per_layer": ffn_params_per_layer,
                "norms_all_layers": (norm_params_per_layer * l) + final_norm_params,
                "lm_head": lm_head_params,
                "is_tied_embeddings": config.tie_word_embeddings
            },
            "flops": {
                "forward_flops_per_token": forward_flops_per_token,
                "training_flops_per_token": total_training_flops_per_token,
                "chinchilla_recommended_tokens": chinchilla_tokens,
                "chinchilla_training_petaflops": round(chinchilla_training_flops / 1e15, 2)
            },
            "memory": {
                "weights_mb": model_weights_mb,
                "weights_gb": model_weights_gb,
                "kv_cache_per_sequence_mb": kv_cache_per_seq_mb,
                "precision": config.precision
            }
        }

    @staticmethod
    def _format_param_count(count: int) -> str:
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.2f}B"
        elif count >= 1_000_000:
            return f"{count / 1_000_000:.2f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.2f}K"
        return str(count)

