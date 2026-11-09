"""
Extensible Decoder-Only Transformer Research Architecture.
Implements Rotary Position Embeddings (RoPE), RMSNorm, Multi-Head Attention (with GQA),
SwiGLU Feed-Forward Networks, and Language Modeling Cross-Entropy Loss.
"""
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.lab.architecture.config import TransformerConfig


class RotaryEmbedding:
    """Precomputes and applies Rotary Position Embeddings (RoPE)."""

    def __init__(self, dim: int, max_seq_len: int = 2048, base: float = 10000.0):
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base

        # Precompute theta frequencies: theta_i = base^(-2(i-1)/dim)
        inv_freq = 1.0 / (base ** (np.arange(0, dim, 2, dtype=np.float32) / dim))
        positions = np.arange(max_seq_len, dtype=np.float32)
        # Outer product: [seq_len, dim/2]
        angles = np.outer(positions, inv_freq)

        self.cos = np.cos(angles)  # [seq_len, dim/2]
        self.sin = np.sin(angles)  # [seq_len, dim/2]

    def apply(self, x: np.ndarray, seq_len: int) -> np.ndarray:
        """
        Applies 2D rotation to pairs of elements in query or key tensors.
        x shape: [batch, seq_len, n_heads, head_dim]
        """
        cos = self.cos[:seq_len]  # [seq_len, dim/2]
        sin = self.sin[:seq_len]  # [seq_len, dim/2]

        # Reshape for broadcasting over heads and batches
        # [1, seq_len, 1, dim/2]
        cos = np.expand_dims(np.expand_dims(cos, axis=0), axis=2)
        sin = np.expand_dims(np.expand_dims(sin, axis=0), axis=2)

        # Split x into even and odd components
        x1 = x[..., 0::2]
        x2 = x[..., 1::2]

        # Planar rotation: [x1*cos - x2*sin, x1*sin + x2*cos]
        rotated_1 = x1 * cos - x2 * sin
        rotated_2 = x1 * sin + x2 * cos

        out = np.empty_like(x)
        out[..., 0::2] = rotated_1
        out[..., 1::2] = rotated_2
        return out


class RMSNorm:
    """Root Mean Square Layer Normalization."""

    def __init__(self, d_model: int, eps: float = 1e-5):
        self.eps = eps
        self.weight = np.ones(d_model, dtype=np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        # x shape: [batch, seq_len, d_model]
        rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + self.eps)
        return (x / rms) * self.weight


class MultiHeadAttention:
    """Multi-Head Attention supporting Grouped Query Attention (GQA) & Causal Masking."""

    def __init__(self, config: TransformerConfig):
        self.d_model = config.d_model
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads or config.n_heads
        self.head_dim = config.d_model // config.n_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        rng = np.random.default_rng(42)
        # Weight matrices initialized with Xavier/Glorot normal distribution
        init_std = 0.02
        self.wq = rng.normal(0, init_std, (self.d_model, self.n_heads * self.head_dim)).astype(np.float32)
        self.wk = rng.normal(0, init_std, (self.d_model, self.n_kv_heads * self.head_dim)).astype(np.float32)
        self.wv = rng.normal(0, init_std, (self.d_model, self.n_kv_heads * self.head_dim)).astype(np.float32)
        self.wo = rng.normal(0, init_std, (self.n_heads * self.head_dim, self.d_model)).astype(np.float32)

        self.rope = RotaryEmbedding(self.head_dim, max_seq_len=config.max_seq_len, base=config.rotary_base)

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch, seq_len, _ = x.shape

        # Projections
        q = np.dot(x, self.wq).reshape(batch, seq_len, self.n_heads, self.head_dim)
        k = np.dot(x, self.wk).reshape(batch, seq_len, self.n_kv_heads, self.head_dim)
        v = np.dot(x, self.wv).reshape(batch, seq_len, self.n_kv_heads, self.head_dim)

        # Apply RoPE
        q = self.rope.apply(q, seq_len)
        k = self.rope.apply(k, seq_len)

        # Grouped Query Attention expansion if n_kv_heads < n_heads
        if self.n_kv_heads < self.n_heads:
            repeats = self.n_heads // self.n_kv_heads
            k = np.repeat(k, repeats, axis=2)
            v = np.repeat(v, repeats, axis=2)

        # Transpose for attention: [batch, n_heads, seq_len, head_dim]
        q = np.swapaxes(q, 1, 2)
        k = np.swapaxes(k, 1, 2)
        v = np.swapaxes(v, 1, 2)

        # Scaled dot product: [batch, n_heads, seq_len, seq_len]
        scores = np.matmul(q, np.swapaxes(k, -1, -2)) * self.scale

        # Causal mask: upper triangular matrix set to -infinity
        mask = np.triu(np.full((seq_len, seq_len), -1e9, dtype=np.float32), k=1)
        scores += mask

        # Softmax along last dimension
        exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
        attn_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

        # Context output: [batch, n_heads, seq_len, head_dim]
        context = np.matmul(attn_weights, v)

        # Reshape back to [batch, seq_len, d_model]
        context = np.swapaxes(context, 1, 2).reshape(batch, seq_len, self.d_model)

        # Output projection
        return np.dot(context, self.wo)


class SwiGLUFeedForward:
    """Swish-Gated Linear Unit (SwiGLU) Feed-Forward Network."""

    def __init__(self, config: TransformerConfig):
        self.d_model = config.d_model
        self.ffn_dim = config.ffn_hidden_dim or int(2 * (4 * config.d_model) / 3)

        rng = np.random.default_rng(42)
        init_std = 0.02
        self.w_gate = rng.normal(0, init_std, (self.d_model, self.ffn_dim)).astype(np.float32)
        self.w_up = rng.normal(0, init_std, (self.d_model, self.ffn_dim)).astype(np.float32)
        self.w_down = rng.normal(0, init_std, (self.ffn_dim, self.d_model)).astype(np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        # Swish(x * W_gate) * (x * W_up) * W_down
        gate = np.dot(x, self.w_gate)
        # Swish activation: x * sigmoid(x)
        swish_gate = gate / (1.0 + np.exp(-gate))
        up = np.dot(x, self.w_up)
        return np.dot(swish_gate * up, self.w_down)


class TransformerBlock:
    """Pre-Norm Decoder Transformer Block."""

    def __init__(self, config: TransformerConfig):
        self.attn_norm = RMSNorm(config.d_model, eps=config.norm_eps)
        self.attn = MultiHeadAttention(config)
        self.ffn_norm = RMSNorm(config.d_model, eps=config.norm_eps)
        self.ffn = SwiGLUFeedForward(config)

    def forward(self, x: np.ndarray) -> np.ndarray:
        # Pre-norm residual connection for attention
        x = x + self.attn.forward(self.attn_norm.forward(x))
        # Pre-norm residual connection for feed-forward
        x = x + self.ffn.forward(self.ffn_norm.forward(x))
        return x


class DecoderTransformer:
    """
    Extensible Decoder-Only Autoregressive Foundation Transformer.
    Computes logits, cross-entropy loss, and perplexity on input sequences.
    """

    def __init__(self, config: TransformerConfig, seed: int = 42):
        self.config = config
        self.seed = seed
        rng = np.random.default_rng(seed)

        # Token embedding lookup table
        init_std = 0.02
        self.embeddings = rng.normal(0, init_std, (config.vocab_size, config.d_model)).astype(np.float32)

        # Stack of Transformer blocks
        self.layers = [TransformerBlock(config) for _ in range(config.n_layers)]

        # Final normalization
        self.final_norm = RMSNorm(config.d_model, eps=config.norm_eps)

        # LM Head (tied or untied)
        if config.tie_word_embeddings:
            self.lm_head = self.embeddings.T
        else:
            self.lm_head = rng.normal(0, init_std, (config.d_model, config.vocab_size)).astype(np.float32)

    def forward(self, token_ids: np.ndarray) -> np.ndarray:
        """
        Forward pass through Transformer.
        token_ids: [batch, seq_len] of integer IDs.
        Returns logits: [batch, seq_len, vocab_size].
        """
        batch, seq_len = token_ids.shape

        # Embedding lookup
        x = self.embeddings[token_ids]  # [batch, seq_len, d_model]

        # Pass through layers
        for layer in self.layers:
            x = layer.forward(x)

        # Final norm
        x = self.final_norm.forward(x)

        # Project to vocabulary logits: [batch, seq_len, vocab_size]
        logits = np.dot(x, self.lm_head)
        return logits

    def compute_loss(self, input_ids: np.ndarray, target_ids: np.ndarray) -> Tuple[float, float]:
        """
        Computes standard autoregressive cross-entropy loss and perplexity.
        input_ids: [batch, seq_len]
        target_ids: [batch, seq_len] (typically shifted tokens)
        Returns (cross_entropy_loss, perplexity).
        """
        logits = self.forward(input_ids)
        batch, seq_len, vocab_size = logits.shape

        # Flatten for loss calculation
        flat_logits = logits.reshape(-1, vocab_size)
        flat_targets = target_ids.reshape(-1)

        # Numerically stable log-softmax
        max_logits = np.max(flat_logits, axis=-1, keepdims=True)
        exp_logits = np.exp(flat_logits - max_logits)
        log_probs = (flat_logits - max_logits) - np.log(np.sum(exp_logits, axis=-1, keepdims=True))

        # Select target log probabilities
        target_log_probs = log_probs[np.arange(len(flat_targets)), flat_targets]
        loss = -float(np.mean(target_log_probs))

        # Prevent overflow in perplexity
        perplexity = float(np.exp(min(loss, 20.0)))
        return round(loss, 4), round(perplexity, 4)

