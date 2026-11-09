# NEXORA MODEL LAB – Proprietary Foundation Model Research Lab

NEXORA Model Lab is an isolated research and foundation model engineering platform within the NEXORA ecosystem. It provides the infrastructure to curate training data, train subword tokenizers, design decoder-only Transformer architectures with analytical parameter estimation, track MLflow-compatible experiments, save verifiable checkpoints, and execute reproducible training runs.

---

## 🏛 1. Core Research Modules

### 1.1 Model Registry & Families Roadmap
The model registry tracks decoder-only Transformer architectures, parameter counts, base models, licenses, checkpoint associations, and deployment statuses.

Three canonical roadmap research targets are defined:
- **NEXORA NANO (`1.0.0-research`)**:
  - ~45M parameters
  - Architecture: `d_model=512`, `n_layers=8`, `n_heads=8`, `n_kv_heads=4`, `max_seq_len=2048`, `vocab_size=32000`, `norm=rmsnorm`, `act=swiglu`.
  - Role: Rapid architectural experimentation, tokenizer validation, hyperparameter sensitivity analysis.
- **NEXORA CORE (`1.0.0-research`)**:
  - ~1.2B parameters
  - Architecture: `d_model=2048`, `n_layers=24`, `n_heads=16`, `n_kv_heads=8`, `max_seq_len=4096`, `vocab_size=50000`, `norm=rmsnorm`, `act=swiglu`.
  - Role: General-purpose instruction and reasoning foundation model.
- **NEXORA PRO (`1.0.0-research`)**:
  - ~8.4B parameters
  - Architecture: `d_model=4096`, `n_layers=36`, `n_heads=32`, `n_kv_heads=8`, `max_seq_len=8192`, `vocab_size=64000`, `norm=rmsnorm`, `act=swiglu`.
  - Role: Advanced multi-step mathematical theorem proving, deep coding, and agentic workflows.

---

### 1.2 Dataset Management & Quality Pipeline
Maintains complete data provenance and executes a 7-stage quality and safety transformation pipeline:
1. **Unicode NFKC Normalization**: Strips invalid control characters, normalizes quotation marks, and collapses whitespace loops.
2. **PII Detection & Redaction**: Scans for emails, phone numbers, US SSNs, IPv4 addresses, and credit card numbers (verified via Luhn's algorithm). Automatically replaces matches with `<PII_REDACTED>` tokens.
3. **Exact Deduplication**: SHA-256 hash collision matching drops redundant documents.
4. **Quality Filtering**: Enforces minimum/maximum character thresholds, alpha-to-symbol ratios ($\ge 0.60$), and filters repetitive line loops.
5. **Language Profiling**: Classifies language distributions across English, Code, and multilingual sets.
6. **Deterministic Splitting**: Deterministically partitions datasets into Train (80%), Validation (10%), and Test (10%) splits with locked random seeds.
7. **Cryptographic Provenance**: Records raw and cleaned SHA-256 checksums, pipeline versions, and collection metadata.

---

### 1.3 Tokenizer Research Engine
- **Byte-Pair Encoding (BPE)**: Implements iterative subword merge learning from training corpora, building merge tables, vocabulary mappings, and special tokens (`<pad>`, `<unk>`, `<s>`, `</s>`, `<bos>`, `<eos>`, `<mask_token>`).
- **Tokenizer Evaluation Metrics**:
  - **Fertility**: Average tokens per word ($\frac{N_{tokens}}{N_{words}}$). Values between $1.1$ and $1.4$ signify optimal subword compression.
  - **Compression Ratio**: Raw UTF-8 bytes per token ($\frac{\text{bytes}}{N_{tokens}}$). Higher ratios decrease context window consumption.
  - **Out-of-Vocabulary (OOV) Rate**: Ratio of unmapped tokens falling back to `<unk>` or single-byte fallback.
  - **Cross-Lingual Benchmarks**: Evaluates compression efficiency across English, Python Code, Spanish, German, and Mathematical prose.

---

### 1.4 Decoder-Only Transformer Architecture
Extensible mathematical implementation of state-of-the-art autoregressive Transformers:
- **Rotary Position Embedding (RoPE)**: Precomputes angular frequencies $\theta_i = \text{base}^{-2(i-1)/d}$ and applies 2D planar rotation to query and key vector pairs.
- **Root Mean Square Normalization (RMSNorm)**:
  $$y = \frac{x}{\sqrt{\frac{1}{d}\sum_{i=1}^d x_i^2 + \epsilon}} \odot \gamma$$
- **Grouped-Query Attention (GQA)**: Configurable query heads ($n_{heads}$) to key/value heads ($n_{kv\_heads}$) ratio with scaled dot-product attention and causal lower-triangular masking.
- **SwiGLU Feed-Forward Network**:
  $$\text{SwiGLU}(x) = (\text{swish}(x W_{gate})) \otimes (x W_{up}) W_{down}$$
- **Analytical Parameter Counter & FLOPs Estimator**:
  - Exact layer-by-layer parameter counting formulas.
  - Training FLOPs per token: $\approx 6 \times P$.
  - Chinchilla compute recommendation: $20 \times P$ tokens and $120 \times P^2$ FLOPs.
  - Memory footprint estimation for model weights and dynamic KV cache.
- **Loss & Perplexity**: Calculates cross-entropy loss against shifted target tokens and computes validation perplexity ($e^{\text{loss}}$).

---

### 1.5 Experiment Management & Reproducibility
- **MLflow Lineage**: Logs step-by-step training loss, validation loss, cosine learning rate schedules, and validation perplexity.
- **Verifiable Checkpoints**: Generates checkpoints on validation milestones with SHA-256 digests of weights.
- **Reproducibility Lock**: Captures git commit hash, random seeds (`python`, `numpy`), hardware CPU cores, RAM, OS, and library versions in an immutable SHA-256 manifest.
- **One-Click Twin Reproduction**: Re-executes any previous experiment using identical locked parameters and seeds.

---

## 🔬 2. Model Lab REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/lab/dashboard` | Overview counts, model family status, and hardware environment |
| `GET` | `/api/v1/lab/models` | List registered foundation models & roadmap families |
| `POST` | `/api/v1/lab/models` | Register a new foundation model configuration |
| `GET` | `/api/v1/lab/models/{id}` | Retrieve model details, checkpoints, and linked experiments |
| `POST` | `/api/v1/lab/models/analyze-architecture` | Compute analytical parameter breakdown, FLOPs, and memory |
| `GET` | `/api/v1/lab/datasets` | List curated datasets and cleaning status |
| `POST` | `/api/v1/lab/datasets/upload` | Upload and register raw training dataset |
| `POST` | `/api/v1/lab/datasets/{id}/clean` | Run normalization, PII redaction, deduplication, and 80/10/10 split |
| `GET` | `/api/v1/lab/datasets/{id}` | Get dataset provenance, PII findings, and sample preview |
| `GET` | `/api/v1/lab/tokenizers` | List research tokenizers |
| `POST` | `/api/v1/lab/tokenizers/train` | Train a BPE or SentencePiece tokenizer on a corpus |
| `POST` | `/api/v1/lab/tokenizers/evaluate` | Evaluate fertility, compression ratio, and multilingual efficiency |
| `GET` | `/api/v1/lab/experiments` | List experiment tracking runs |
| `POST` | `/api/v1/lab/experiments` | Create a new experiment run with hyperparameters |
| `POST` | `/api/v1/lab/experiments/{id}/start` | Execute training steps and log checkpoints |
| `GET` | `/api/v1/lab/experiments/{id}` | Inspect loss curves and reproducibility manifest |
| `POST` | `/api/v1/lab/experiments/{id}/reproduce` | Launch reproducible twin run with locked seeds |
| `GET` | `/api/v1/lab/checkpoints` | List saved checkpoints across experiments |
| `POST` | `/api/v1/lab/checkpoints/{id}/validate` | Verify SHA-256 checksum, reload SafeTensors/PEFT weights, scan NaN/Inf, and test forward pass |
| `POST` | `/api/v1/lab/checkpoints/{id}/export` | Export validated checkpoint bundle (`EXPORT_MANIFEST.json`) |
| `POST` | `/api/v1/lab/checkpoints/{id}/rollback` | Switch active rollback pointer to a validated checkpoint |
| `GET` | `/api/v1/lab/evaluations` | List benchmark evaluation records |
| `POST` | `/api/v1/lab/evaluations/run` | Execute benchmark evaluation against a checkpoint |
| `GET` | `/api/v1/lab/telemetry` | Real-time NVML/CUDA/CPU/RAM hardware telemetry + active worker progress |
| `GET` | `/api/v1/lab/frameworks` | Detect installed PyTorch, Transformers, Accelerate, PEFT, TRL, DeepSpeed, NeMo versions |
| `POST` | `/api/v1/lab/licenses/verify` | Enforce base model + dataset + intended use license compatibility |
| `GET` | `/api/v1/lab/jobs` | List & synchronize isolated fine-tuning jobs |
| `POST` | `/api/v1/lab/jobs` | Create & optionally spawn isolated PyTorch/PEFT/TRL training worker |
| `POST` | `/api/v1/lab/jobs/{id}/start` | Spawn isolated worker subprocess (`worker.py`) |
| `POST` | `/api/v1/lab/jobs/{id}/pause` | Signal worker pause & save resumable checkpoint |
| `POST` | `/api/v1/lab/jobs/{id}/resume` | Resume worker from last checkpoint & `optimizer.pt` |
| `POST` | `/api/v1/lab/jobs/{id}/recover` | Failure recovery restart from latest verified checkpoint |
| `POST` | `/api/v1/lab/jobs/{id}/cancel` | Cancel queued or running job cleanly |
| `GET` | `/api/v1/lab/jobs/{id}/logs` | Tail live stdout/stderr logs from isolated worker |
| `GET` | `/api/v1/lab/benchmarks` | List 10-dimension comparative benchmark suites |
| `POST` | `/api/v1/lab/benchmarks/compare` | Run 10-axis base vs fine-tuned evaluation + data leakage guard + regression check |
| `POST` | `/api/v1/lab/benchmarks/{id}/human-rating` | Append human evaluator ratings to benchmark suite |
| `GET` | `/api/v1/lab/optimizations` | List quantization & inference speed benchmarks |
| `POST` | `/api/v1/lab/optimizations/run` | Execute INT8/FP16/BF16 quantization & TTFT/memory/context/batch scaling sweeps |
| `GET` | `/api/v1/lab/deployments` | List deployed OpenAI-compatible serving endpoints & engine capabilities |
| `POST` | `/api/v1/lab/deployments` | Deploy a validated checkpoint to independent OpenAI inference server |
| `POST` | `/api/v1/lab/deployments/{id}/stop` | Unload & stop deployed inference endpoint |

---

## 🧪 3. Verification & Testing

Run the automated Model Lab and Training Infrastructure test suites:
```bash
cd backend
pytest tests/test_lab.py tests/test_training_infra.py -v
```
See [`TRAINING_INFRASTRUCTURE.md`](TRAINING_INFRASTRUCTURE.md) for deep coverage of isolated workers, quantization, checkpoint gates, and OpenAI serving endpoints.

Run the automated Model Lab test suite:
```bash
cd backend
pytest tests/test_lab.py -v
```
All 15 test suites verify:
- Roadmap model family specs (NANO, CORE, PRO).
- Analytical parameter counting and tied embeddings parameter reduction.
- RoPE rotary position embedding mathematical invariants.
- RMSNorm root-mean-square unit variance.
- SwiGLU forward pass dimensions.
- DecoderTransformer cross-entropy loss and perplexity.
- Unicode NFKC normalization and quote cleaning.
- Regex PII detection and redaction (emails, phones, SSNs, IPs, credit cards).
- SHA-256 deduplication and deterministic splitting.
- BPE subword training, encoding, and lossless decoding.
- Fertility, compression ratio, and multilingual evaluation.
- Hardware profiling and reproducibility manifest hashing.
- Authentic training step execution and checkpoint SHA-256 hashing.

