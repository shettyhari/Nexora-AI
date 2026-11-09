"""
Transformer Model Architecture Configuration.
Specifies hyperparameters for decoder-only foundation model research.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class TransformerConfig(BaseModel):
    """Architectural hyperparameters for a decoder-only autoregressive Transformer."""

    name: str = "nexora-transformer-research"
    vocab_size: int = Field(default=32000, description="Size of the token vocabulary")
    d_model: int = Field(default=512, description="Hidden dimension / embedding width")
    n_layers: int = Field(default=8, description="Number of Transformer decoder layers")
    n_heads: int = Field(default=8, description="Number of query attention heads")
    n_kv_heads: Optional[int] = Field(default=4, description="Number of key/value heads for GQA/MQA (<= n_heads)")
    max_seq_len: int = Field(default=2048, description="Maximum sequence / context length")
    ffn_hidden_dim: Optional[int] = Field(default=None, description="Hidden dimension of Feed-Forward Network")

    norm_type: Literal["rmsnorm", "layernorm"] = Field(default="rmsnorm", description="Layer normalization algorithm")
    norm_eps: float = Field(default=1e-5, description="Normalization epsilon for numerical stability")
    activation: Literal["swiglu", "gelu", "silu", "relu"] = Field(default="swiglu", description="Feed-forward activation function")
    rotary_base: float = Field(default=10000.0, description="Base frequency for RoPE rotary embeddings")
    tie_word_embeddings: bool = Field(default=False, description="Whether to tie input embeddings and output LM head weights")
    precision: Literal["fp32", "fp16", "bf16"] = Field(default="fp32", description="Floating-point compute precision")

    def model_post_init(self, __context):
        # Auto-calculate n_kv_heads if omitted
        if self.n_kv_heads is None:
            self.n_kv_heads = self.n_heads

        # Auto-calculate SwiGLU hidden dimension if omitted: ~ 8/3 * d_model rounded to multiple of 256
        if self.ffn_hidden_dim is None:
            base_ffn = int(2 * (4 * self.d_model) / 3)
            # Round up to nearest multiple of 256
            self.ffn_hidden_dim = ((base_ffn + 255) // 256) * 256

        # Validation assertions
        if self.d_model % self.n_heads != 0:
            raise ValueError(f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})")
        if self.n_heads % self.n_kv_heads != 0:
            raise ValueError(f"n_heads ({self.n_heads}) must be divisible by n_kv_heads ({self.n_kv_heads})")

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

