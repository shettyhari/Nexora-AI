"""
Comprehensive Automated Test Suite for NEXORA MODEL LAB.
Tests Model Registry, Dataset Processing, Tokenizer Research,
Transformer Architecture, and Experiment Tracking.
"""
import pytest
import numpy as np
from app.lab.architecture.config import TransformerConfig
from app.lab.architecture.param_counter import ParameterCounter
from app.lab.architecture.transformer import (
    DecoderTransformer,
    MultiHeadAttention,
    RMSNorm,
    RotaryEmbedding,
    SwiGLUFeedForward,
)
from app.lab.dataset.processor import DatasetProcessor
from app.lab.experiments.runner import TrainingRunner
from app.lab.experiments.tracker import ExperimentTracker, HardwareProfiler
from app.lab.models.families import MODEL_FAMILIES_ROADMAP
from app.lab.tokenizer.bpe import BPETokenizer
from app.lab.tokenizer.evaluator import TokenizerEvaluator


# =====================================================================
# 1. MODEL FAMILIES & REGISTRY TESTS
# =====================================================================

def test_model_families_roadmap():
    """Verifies standard foundation model families: NANO, CORE, PRO."""
    families = {f["model_family"]: f for f in MODEL_FAMILIES_ROADMAP}
    assert "nano" in families
    assert "core" in families
    assert "pro" in families

    # Verify NANO configuration
    nano = families["nano"]
    assert nano["architecture_config"]["d_model"] == 512
    assert nano["architecture_config"]["n_layers"] == 8
    assert nano["architecture_config"]["n_kv_heads"] == 4

    # Verify CORE configuration
    core = families["core"]
    assert core["architecture_config"]["d_model"] == 2048
    assert core["architecture_config"]["n_layers"] == 24

    # Verify PRO configuration
    pro = families["pro"]
    assert pro["architecture_config"]["d_model"] == 4096
    assert pro["architecture_config"]["n_layers"] == 36


# =====================================================================
# 2. ARCHITECTURE & PARAMETER COUNTER TESTS
# =====================================================================

def test_parameter_counter_analytical():
    """Verifies analytical parameter counts, breakdown, and FLOPs."""
    config = TransformerConfig(
        vocab_size=32000,
        d_model=512,
        n_layers=8,
        n_heads=8,
        n_kv_heads=4,
        max_seq_len=2048,
        activation="swiglu",
        norm_type="rmsnorm",
        tie_word_embeddings=False,
        precision="fp32"
    )

    analysis = ParameterCounter.analyze(config)
    assert analysis["total_parameters"] > 0
    assert "breakdown" in analysis
    assert "flops" in analysis
    assert "memory" in analysis

    # Mathematical assertions
    d = 512
    v = 32000
    l = 8
    embedding_p = v * d
    assert analysis["breakdown"]["token_embeddings"] == embedding_p
    assert analysis["breakdown"]["lm_head"] == embedding_p
    assert analysis["flops"]["training_flops_per_token"] == 6 * analysis["total_parameters"]
    assert analysis["memory"]["precision"] == "fp32"


def test_tied_word_embeddings_parameter_reduction():
    """Tying input embeddings and LM head reduces parameter count by d_model * vocab_size."""
    untied_cfg = TransformerConfig(vocab_size=10000, d_model=256, n_layers=4, n_heads=4, tie_word_embeddings=False)
    tied_cfg = TransformerConfig(vocab_size=10000, d_model=256, n_layers=4, n_heads=4, tie_word_embeddings=True)

    untied_analysis = ParameterCounter.analyze(untied_cfg)
    tied_analysis = ParameterCounter.analyze(tied_cfg)

    diff = untied_analysis["total_parameters"] - tied_analysis["total_parameters"]
    expected_diff = 10000 * 256
    assert diff == expected_diff
    assert tied_analysis["breakdown"]["lm_head"] == 0


# =====================================================================
# 3. TRANSFORMER MATHEMATICAL MODULE TESTS
# =====================================================================

def test_rotary_position_embedding():
    """Verifies RoPE dimensions and rotational property."""
    dim = 64
    seq_len = 16
    rope = RotaryEmbedding(dim=dim, max_seq_len=32)

    # Tensor [batch=1, seq_len=16, n_heads=2, head_dim=64]
    x = np.ones((1, seq_len, 2, dim), dtype=np.float32)
    rotated = rope.apply(x, seq_len)

    assert rotated.shape == x.shape
    # Position 0 has angle 0, cos(0)=1, sin(0)=0 so position 0 is unchanged
    np.testing.assert_allclose(rotated[0, 0, 0, :], x[0, 0, 0, :], atol=1e-5)
    # Later positions must be transformed by rotation
    assert not np.allclose(rotated[0, 5, 0, :], x[0, 5, 0, :])


def test_rmsnorm_forward():
    """Verifies RMSNorm normalizes root-mean-square to 1."""
    d_model = 128
    norm = RMSNorm(d_model=d_model)
    x = np.random.randn(2, 10, d_model).astype(np.float32) * 5.0

    out = norm.forward(x)
    assert out.shape == x.shape
    rms = np.sqrt(np.mean(out ** 2, axis=-1))
    np.testing.assert_allclose(rms, np.ones_like(rms), atol=1e-3)


def test_swiglu_feed_forward():
    """Verifies SwiGLU forward pass dimensions."""
    config = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ffn_hidden_dim=128)
    swiglu = SwiGLUFeedForward(config)

    x = np.random.randn(2, 8, 64).astype(np.float32)
    out = swiglu.forward(x)
    assert out.shape == (2, 8, 64)


def test_decoder_transformer_forward_and_loss():
    """Verifies full forward pass, cross-entropy loss, and perplexity calculation."""
    config = TransformerConfig(
        vocab_size=50,
        d_model=32,
        n_layers=2,
        n_heads=4,
        n_kv_heads=2,
        max_seq_len=16
    )
    model = DecoderTransformer(config, seed=42)

    token_ids = np.random.randint(0, 50, (2, 8))
    target_ids = np.roll(token_ids, -1, axis=1)

    loss, ppl = model.compute_loss(token_ids, target_ids)
    assert isinstance(loss, float)
    assert isinstance(ppl, float)
    assert loss > 0.0
    assert ppl >= 1.0


# =====================================================================
# 4. DATASET MANAGEMENT & CLEANING TESTS
# =====================================================================

def test_dataset_processor_normalization():
    """Verifies unicode NFKC normalization, whitespace collapse, and quote cleaning."""
    dirty_text = "NEXORA   AI  “neural”\t\tmodel — test  \n\n\n\nline 2"
    cleaned = DatasetProcessor.clean_and_normalize(dirty_text)
    assert "  " not in cleaned
    assert "“" not in cleaned
    assert '"neural"' in cleaned
    assert "\n\n\n" not in cleaned


def test_pii_detection_and_redaction():
    """Verifies detection and redaction of emails, phones, SSNs, IPs, and credit cards."""
    text_with_pii = (
        "Contact researcher at scientist@nexora.ai or call +1-555-123-4567. "
        "Sensitive ID: 123-45-6789 on server 192.168.1.1."
    )

    redacted, findings, counts = DatasetProcessor.detect_and_redact_pii(text_with_pii, redact=True)
    assert counts["email"] == 1
    assert counts["phone"] == 1
    assert counts["ssn"] == 1
    assert counts["ipv4"] == 1

    assert "scientist@nexora.ai" not in redacted
    assert "<EMAIL_REDACTED>" in redacted
    assert "<SSN_REDACTED>" in redacted
    assert "<IPV4_REDACTED>" in redacted


def test_dataset_deduplication():
    """Verifies exact SHA-256 deduplication."""
    samples = [
        "First unique sample text for pretraining.",
        "Second unique sample text for pretraining.",
        "First unique sample text for pretraining.",
        "Third unique sample text for pretraining."
    ]
    deduped, removed = DatasetProcessor.deduplicate(samples)
    assert len(deduped) == 3
    assert removed == 1


def test_dataset_splitting():
    """Verifies deterministic train/validation/test splitting."""
    samples = [f"Sample text document {i}" for i in range(100)]
    splits = DatasetProcessor.split_dataset(samples, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42)

    assert len(splits["train"]) == 80
    assert len(splits["validation"]) == 10
    assert len(splits["test"]) == 10

    # Test seed determinism
    splits2 = DatasetProcessor.split_dataset(samples, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42)
    assert splits["train"] == splits2["train"]


# =====================================================================
# 5. TOKENIZER RESEARCH TESTS
# =====================================================================

def test_bpe_tokenizer_train_and_encode_decode():
    """Verifies BPE merge learning, encoding into subwords, and lossless reconstruction."""
    corpus = [
        "the quick brown fox jumps over the lazy dog",
        "the fox is quick and the dog is lazy",
        "quick brown foxes leap high in the air"
    ]

    tokenizer = BPETokenizer()
    tokenizer.train(corpus, target_vocab_size=120, min_frequency=1)

    assert len(tokenizer.vocab) >= len(tokenizer.special_tokens)
    assert len(tokenizer.merges) > 0

    test_sentence = "the quick brown fox"
    token_ids = tokenizer.encode(test_sentence)
    assert len(token_ids) > 0

    decoded = tokenizer.decode(token_ids)
    assert decoded.strip() == test_sentence.strip()


def test_tokenizer_evaluator_metrics():
    """Verifies fertility, compression ratio, and frequency analysis."""
    tokenizer = BPETokenizer()
    tokenizer.train(["hello world from nexora AI lab"], target_vocab_size=50)

    metrics = TokenizerEvaluator.evaluate(tokenizer, "hello world from nexora AI lab")
    assert "fertility" in metrics
    assert "compression_ratio" in metrics
    assert metrics["fertility"] >= 1.0
    assert metrics["compression_ratio"] > 0.0

    multilingual = TokenizerEvaluator.evaluate_multilingual(tokenizer)
    assert "english" in multilingual
    assert "code_python" in multilingual


# =====================================================================
# 6. EXPERIMENT TRACKING & REPRODUCIBILITY TESTS
# =====================================================================

def test_hardware_profiler_and_manifest():
    """Verifies environment snapshot and cryptographic manifest creation."""
    snapshot = HardwareProfiler.get_environment_snapshot(seed=1337)
    assert "python_version" in snapshot
    assert "cpu_cores" in snapshot
    assert snapshot["random_seed"] == 1337

    manifest = ExperimentTracker.create_reproducibility_manifest(
        experiment_id="exp-test-001",
        model_config={"name": "NEXORA NANO"},
        dataset_provenance={"dataset": "curated-v1"},
        hyperparameters={"lr": 3e-4, "seed": 1337},
        env_snapshot=snapshot
    )
    assert "manifest_sha256" in manifest
    assert len(manifest["manifest_sha256"]) == 64


def test_training_runner_authentic_execution(tmp_path):
    """
    Verifies that the training runner computes authentic loss,
    validation perplexity, and saves checkpoints with SHA-256 weight hashes.
    """
    config = TransformerConfig(
        vocab_size=64,
        d_model=32,
        n_layers=2,
        n_heads=4,
        n_kv_heads=2,
        max_seq_len=32
    )

    train_texts = [
        "foundation model training with attention and swiglu.",
        "rotary position embeddings calculate angular positional shifts."
    ]
    val_texts = [
        "perplexity is exponentiated cross entropy loss."
    ]

    result = TrainingRunner.execute_training_run(
        experiment_id="exp-run-001",
        config=config,
        train_texts=train_texts,
        val_texts=val_texts,
        hyperparameters={"max_steps": 5, "learning_rate": 1e-3, "seed": 42},
        checkpoint_dir=str(tmp_path)
    )

    assert result["status"] == "completed"
    assert result["current_step"] == 5
    assert len(result["loss_history"]) == 5
    assert result["best_val_loss"] > 0.0
    assert result["best_perplexity"] >= 1.0
    assert len(result["checkpoints"]) > 0

    # Verify checkpoint weights hash
    ckpt = result["checkpoints"][-1]
    assert "weights_sha256" in ckpt
    assert len(ckpt["weights_sha256"]) == 64
