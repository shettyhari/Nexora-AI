"""
Isolated ML Compute Worker Runtime Bridge.
Enables seamless execution whether PyTorch/Transformers/PEFT/TRL live in the same
Python interpreter (single-node / Docker GPU) or in a dedicated isolated ML worker
virtual environment (e.g. slim API venv + dedicated training/inference venv).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional

_IN_PROCESS_ML_CACHE: Optional[bool] = None
_WORKER_PYTHON_CACHE: Optional[str] = None

_MARKER_START = "__NEXORA_BRIDGE_START__"
_MARKER_END = "__NEXORA_BRIDGE_END__"


def get_backend_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def can_run_ml_in_process() -> bool:
    """Returns True if the active Python interpreter can import and run torch + transformers."""
    global _IN_PROCESS_ML_CACHE
    if os.environ.get("NEXORA_IN_ML_WORKER") == "1":
        return True
    if _IN_PROCESS_ML_CACHE is not None:
        return _IN_PROCESS_ML_CACHE
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        _IN_PROCESS_ML_CACHE = True
    except Exception:
        _IN_PROCESS_ML_CACHE = False
    return _IN_PROCESS_ML_CACHE


def resolve_worker_python() -> str:
    """
    Resolves the Python interpreter that hosts the ML stack (torch/transformers/peft/trl).
    Priority:
      1. `TRAINING_WORKER_PYTHON` env var if set and valid
      2. Active interpreter (`sys.executable`) if it can run torch/transformers
      3. Dedicated worker venv in backend (`.venv311`, `.venv-worker`, `.venv-ml`)
      4. Fallback to `sys.executable`
    """
    global _WORKER_PYTHON_CACHE
    env_py = os.environ.get("TRAINING_WORKER_PYTHON")
    if env_py and os.path.exists(env_py):
        return os.path.abspath(env_py)

    if can_run_ml_in_process():
        return sys.executable

    if _WORKER_PYTHON_CACHE and os.path.exists(_WORKER_PYTHON_CACHE):
        return _WORKER_PYTHON_CACHE

    backend_root = get_backend_root()
    candidates = [
        os.path.join(backend_root, ".venv311", "Scripts", "python.exe"),
        os.path.join(backend_root, ".venv311", "bin", "python"),
        os.path.join(backend_root, ".venv-worker", "Scripts", "python.exe"),
        os.path.join(backend_root, ".venv-worker", "bin", "python"),
        os.path.join(backend_root, ".venv-ml", "Scripts", "python.exe"),
        os.path.join(backend_root, ".venv-ml", "bin", "python"),
    ]
    for path in candidates:
        if os.path.exists(path):
            _WORKER_PYTHON_CACHE = os.path.abspath(path)
            return _WORKER_PYTHON_CACHE

    return sys.executable


def invoke_worker_task(action: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 120) -> Dict[str, Any]:
    """Executes an ML task inside the resolved isolated ML worker interpreter and returns parsed JSON."""
    worker_py = resolve_worker_python()
    backend_root = get_backend_root()

    fd, tmp_path = tempfile.mkstemp(prefix="nexora_bridge_", suffix=".json")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload or {}, f)

        env = os.environ.copy()
        env["NEXORA_IN_ML_WORKER"] = "1"
        env["PYTHONPATH"] = backend_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        proc = subprocess.run(
            [worker_py, "-m", "app.lab.runtime_bridge", "--action", action, "--payload-file", tmp_path],
            cwd=backend_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout or ""
        if _MARKER_START in stdout and _MARKER_END in stdout:
            raw_json = stdout.split(_MARKER_START, 1)[1].split(_MARKER_END, 1)[0].strip()
            data = json.loads(raw_json)
            if isinstance(data, dict) and "__bridge_error__" in data:
                raise RuntimeError(data["__bridge_error__"])
            return data

        raise RuntimeError(
            f"ML worker bridge action '{action}' failed (code={proc.returncode}): {proc.stderr or stdout}"
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _execute_bridge_action(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Server-side entrypoint inside the isolated ML worker Python."""
    if action == "inspect_frameworks":
        from app.lab.training.frameworks import FrameworkInspector
        return FrameworkInspector.inspect_frameworks()

    if action == "engine_capabilities":
        from app.lab.inference.server import InferenceDeploymentManager
        return InferenceDeploymentManager.check_engine_capabilities()

    if action == "validate_checkpoint":
        from app.lab.checkpoints.manager import CheckpointManager
        return CheckpointManager.validate_checkpoint(
            storage_path=payload["storage_path"],
            expected_sha256=payload.get("expected_sha256"),
        )

    if action == "compare_models":
        from app.lab.evaluation.benchmark import BenchmarkEvaluator
        return BenchmarkEvaluator.compare_models(**payload)

    if action == "optimize_model":
        from app.lab.optimization.quantizer import ModelOptimizer
        return ModelOptimizer.run_optimization_and_benchmark(**payload)

    if action == "verify_load_checkpoint":
        from app.lab.evaluation.benchmark import BenchmarkEvaluator
        model, tok = BenchmarkEvaluator._load_checkpoint_model_and_tokenizer(payload.get("checkpoint_path"))
        return {"loaded": model is not None and tok is not None}

    if action == "generate_tokens":
        from app.lab.inference.server import InferenceDeploymentManager
        mgr = InferenceDeploymentManager()
        return mgr._generate_tokens_sync(
            model_alias=payload["model_alias"],
            checkpoint_path=payload.get("checkpoint_path"),
            prompt=payload["prompt"],
            max_tokens=int(payload.get("max_tokens", 32)),
            temperature=float(payload.get("temperature", 0.7)),
            quantization=payload.get("quantization", "none"),
        )

    raise ValueError(f"Unknown bridge action: {action}")


def main() -> None:
    os.environ["NEXORA_IN_ML_WORKER"] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True)
    parser.add_argument("--payload-file", required=True)
    args = parser.parse_args()

    try:
        with open(args.payload_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        result = _execute_bridge_action(args.action, payload)
    except Exception as exc:
        result = {"__bridge_error__": str(exc)}

    print(f"{_MARKER_START}{json.dumps(result)}{_MARKER_END}", flush=True)


if __name__ == "__main__":
    main()

