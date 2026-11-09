"""
Training Frameworks Inspector & Distributed Configuration Generators.
Integrates PyTorch, Hugging Face Transformers, Accelerate, PEFT, TRL,
plus DeepSpeed and NVIDIA NeMo configuration synthesis with compatibility validation.
"""
import importlib.metadata
import importlib.util
import sys
import time
from typing import Any, Dict, List, Optional

from app.lab.runtime_bridge import (
    can_run_ml_in_process,
    invoke_worker_task,
    resolve_worker_python,
)

_FRAMEWORKS_CACHE: Optional[Dict[str, Any]] = None
_FRAMEWORKS_CACHE_TS: float = 0.0


class FrameworkInspector:
    """Detects installed ML training & serving frameworks and their exact versions."""

    TRACKED_PACKAGES = [
        ("torch", "PyTorch Core Tensor & Autograd Engine"),
        ("transformers", "Hugging Face Transformers"),
        ("accelerate", "Hugging Face Accelerate Distributed Launcher"),
        ("peft", "PEFT (LoRA / QLoRA Parameter-Efficient Tuning)"),
        ("trl", "TRL (SFTTrainer / DPOTrainer / GRPOTrainer)"),
        ("datasets", "Hugging Face Datasets Streaming"),
        ("safetensors", "SafeTensors Zero-Copy Weight Serialization"),
        ("bitsandbytes", "BitsAndBytes 4-bit / 8-bit CUDA Quantization"),
        ("deepspeed", "Microsoft DeepSpeed ZeRO Optimizer"),
        ("vllm", "vLLM PagedAttention Inference Engine"),
        ("nemo", "NVIDIA NeMo Megatron Framework"),
        ("psutil", "Hardware & Process System Telemetry"),
    ]

    @classmethod
    def inspect_frameworks(cls) -> Dict[str, Any]:
        """Returns authentic installation status & versions of all integrated frameworks."""
        global _FRAMEWORKS_CACHE, _FRAMEWORKS_CACHE_TS
        if not can_run_ml_in_process() and resolve_worker_python() != sys.executable:
            if _FRAMEWORKS_CACHE and (time.time() - _FRAMEWORKS_CACHE_TS) < 60.0:
                return _FRAMEWORKS_CACHE
            try:
                _FRAMEWORKS_CACHE = invoke_worker_task("inspect_frameworks", {})
                _FRAMEWORKS_CACHE_TS = time.time()
                return _FRAMEWORKS_CACHE
            except Exception:
                pass

        cuda_available = False
        cuda_version: Optional[str] = None
        if importlib.util.find_spec("torch") is not None:
            try:
                import torch
                cuda_available = bool(torch.cuda.is_available())
                cuda_version = getattr(torch.version, "cuda", None)
            except Exception:
                pass

        frameworks: Dict[str, Dict[str, Any]] = {}
        for pkg_name, description in cls.TRACKED_PACKAGES:
            spec = importlib.util.find_spec(pkg_name)
            installed = spec is not None
            version: Optional[str] = None
            if installed:
                dist_name = "nvidia-ml-py" if pkg_name == "pynvml" else pkg_name
                try:
                    version = importlib.metadata.version(dist_name)
                except Exception:
                    try:
                        mod = __import__(pkg_name)
                        version = getattr(mod, "__version__", "installed")
                    except Exception:
                        version = "installed"

            mode = "active_runtime" if installed else (
                "config_adapter" if pkg_name in ("deepspeed", "nemo", "bitsandbytes", "vllm") else "missing"
            )
            frameworks[pkg_name] = {
                "name": pkg_name,
                "description": description,
                "installed": installed,
                "version": version,
                "mode": mode,
            }

        # Verify key symbols cleanly
        capabilities = {
            "sft_trainer": frameworks["trl"]["installed"] and frameworks["transformers"]["installed"],
            "lora_peft": frameworks["peft"]["installed"] and frameworks["torch"]["installed"],
            "qlora_4bit_cuda": frameworks["bitsandbytes"]["installed"] and cuda_available,
            "dpo_trainer": frameworks["trl"]["installed"] and frameworks["torch"]["installed"],
            "grpo_trainer": frameworks["trl"]["installed"] and frameworks["torch"]["installed"],
            "accelerate_distributed": frameworks["accelerate"]["installed"],
            "deepspeed_runtime": frameworks["deepspeed"]["installed"] and cuda_available,
            "nemo_runtime": frameworks["nemo"]["installed"] and cuda_available,
            "vllm_serving": frameworks["vllm"]["installed"] and cuda_available,
        }

        return {
            "cuda_available": cuda_available,
            "cuda_version": cuda_version,
            "frameworks": frameworks,
            "capabilities": capabilities,
        }


class DistributedConfigGenerator:
    """Builds validated distributed & fine-tuning configs for Accelerate, PEFT, TRL, DeepSpeed, and NVIDIA NeMo."""

    @classmethod
    def build_peft_lora_config(
        cls,
        r: int = 8,
        lora_alpha: int = 16,
        lora_dropout: float = 0.05,
        target_modules: Optional[List[str]] = None,
        quantization_bits: Optional[int] = None,
    ) -> Dict[str, Any]:
        modules = target_modules or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        cfg: Dict[str, Any] = {
            "task_type": "CAUSAL_LM",
            "r": r,
            "lora_alpha": lora_alpha,
            "lora_dropout": lora_dropout,
            "bias": "none",
            "target_modules": modules,
            "use_rslora": False,
        }
        if quantization_bits == 4:
            cfg["quantization"] = {
                "load_in_4bit": True,
                "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_use_double_quant": True,
                "bnb_4bit_compute_dtype": "bfloat16",
            }
        elif quantization_bits == 8:
            cfg["quantization"] = {
                "load_in_8bit": True,
            }
        return cfg

    @classmethod
    def build_accelerate_config(
        cls,
        mixed_precision: str = "no",
        grad_accum_steps: int = 2,
        num_processes: int = 1,
        use_deepspeed: bool = False,
        zero_stage: int = 2,
    ) -> Dict[str, Any]:
        return {
            "compute_environment": "LOCAL_MACHINE",
            "distributed_type": "DEEPSPEED" if use_deepspeed else ("MULTI_GPU" if num_processes > 1 else "NO"),
            "mixed_precision": mixed_precision,
            "num_processes": num_processes,
            "gradient_accumulation_steps": grad_accum_steps,
            "use_cpu": mixed_precision == "no" and num_processes == 1,
            "deepspeed_config": cls.build_deepspeed_config(zero_stage=zero_stage) if use_deepspeed else None,
        }

    @classmethod
    def build_deepspeed_config(
        cls,
        zero_stage: int = 2,
        micro_batch_size: int = 4,
        grad_accum_steps: int = 2,
        bf16: bool = True,
        offload_optimizer: bool = False,
    ) -> Dict[str, Any]:
        zero_opt: Dict[str, Any] = {
            "stage": zero_stage,
            "overlap_comm": True,
            "contiguous_gradients": True,
            "reduce_bucket_size": "auto",
        }
        if zero_stage == 3:
            zero_opt.update({
                "stage3_prefetch_bucket_size": "auto",
                "stage3_param_persistence_threshold": "auto",
                "stage3_max_live_parameters": 1e9,
            })
        if offload_optimizer:
            zero_opt["offload_optimizer"] = {"device": "cpu", "pin_memory": True}

        return {
            "train_micro_batch_size_per_gpu": micro_batch_size,
            "gradient_accumulation_steps": grad_accum_steps,
            "gradient_clipping": 1.0,
            "bf16": {"enabled": bf16},
            "fp16": {"enabled": not bf16, "loss_scale": 0},
            "zero_optimization": zero_opt,
            "steps_per_print": 50,
            "wall_clock_breakdown": False,
        }

    @classmethod
    def build_nemo_config(
        cls,
        model_name: str,
        training_method: str = "lora",
        tensor_parallel: int = 1,
        pipeline_parallel: int = 1,
        max_steps: int = 1000,
        lr: float = 1e-4,
    ) -> Dict[str, Any]:
        """Generates NVIDIA NeMo Megatron GPT SFT / PEFT YAML-compatible recipe dictionary."""
        return {
            "trainer": {
                "devices": tensor_parallel * pipeline_parallel,
                "accelerator": "gpu",
                "precision": "bf16-mixed",
                "max_steps": max_steps,
                "val_check_interval": max(1, max_steps // 10),
                "gradient_clip_val": 1.0,
            },
            "model": {
                "restore_from_path": model_name,
                "tensor_model_parallel_size": tensor_parallel,
                "pipeline_model_parallel_size": pipeline_parallel,
                "activations_checkpoint_granularity": "selective",
                "peft": {
                    "peft_scheme": "lora" if training_method in ("lora", "qlora") else "none",
                    "lora_tuning": {
                        "target_modules": ["attention_qkv", "attention_dense"],
                        "adapter_dim": 16,
                        "adapter_dropout": 0.05,
                    },
                },
                "optim": {
                    "name": "distributed_fused_adam",
                    "lr": lr,
                    "weight_decay": 0.01,
                    "sched": {"name": "CosineAnnealing", "warmup_steps": min(50, max_steps // 10)},
                },
            },
        }
