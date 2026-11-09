"""
Real Hardware & Training Telemetry Monitor.
Collects authentic CPU, RAM, Disk, Process, and GPU metrics via pynvml, nvidia-smi,
PyTorch CUDA/MPS, and psutil. Never fabricates GPU hardware or training telemetry.
"""
import importlib.util
import os
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional


class HardwareTelemetryMonitor:
    """Queries live host hardware telemetry without faking missing accelerators."""

    @classmethod
    def _probe_pynvml(cls) -> Optional[List[Dict[str, Any]]]:
        if importlib.util.find_spec("pynvml") is None:
            return None
        try:
            import pynvml  # type: ignore

            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            driver_ver = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_ver, bytes):
                driver_ver = driver_ver.decode("utf-8", errors="ignore")

            gpus: List[Dict[str, Any]] = []
            for idx in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                uuid = pynvml.nvmlDeviceGetUUID(handle)
                if isinstance(uuid, bytes):
                    uuid = uuid.decode("utf-8", errors="ignore")

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                temp_c: Optional[float] = None
                try:
                    temp_c = float(
                        pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                    )
                except Exception:
                    pass

                power_w: Optional[float] = None
                try:
                    power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0, 2)
                except Exception:
                    pass

                total_mb = round(mem_info.total / (1024 * 1024), 2)
                used_mb = round(mem_info.used / (1024 * 1024), 2)
                free_mb = round(mem_info.free / (1024 * 1024), 2)

                gpus.append({
                    "index": idx,
                    "name": name,
                    "uuid": uuid,
                    "backend": "nvml",
                    "driver_version": driver_ver,
                    "gpu_utilization_pct": float(util.gpu),
                    "memory_utilization_pct": round((used_mb / max(total_mb, 1e-6)) * 100.0, 2),
                    "memory_used_mb": used_mb,
                    "memory_free_mb": free_mb,
                    "memory_total_mb": total_mb,
                    "temperature_c": temp_c,
                    "power_draw_w": power_w,
                })

            pynvml.nvmlShutdown()
            return gpus
        except Exception:
            return None

    @classmethod
    def _probe_nvidia_smi(cls) -> Optional[List[Dict[str, Any]]]:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return None
        try:
            cmd = [
                nvidia_smi,
                "--query-gpu=index,name,uuid,utilization.gpu,memory.used,memory.free,memory.total,temperature.gpu,power.draw,driver_version",
                "--format=csv,noheader,nounits",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if proc.returncode != 0 or not proc.stdout.strip():
                return None

            gpus: List[Dict[str, Any]] = []
            for line in proc.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 10:
                    continue

                def _safe_float(val: str) -> Optional[float]:
                    try:
                        if val in ("[N/A]", "N/A", "[Not Supported]", ""):
                            return None
                        return float(val)
                    except ValueError:
                        return None

                used_mb = _safe_float(parts[4]) or 0.0
                total_mb = _safe_float(parts[6]) or 0.0
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "uuid": parts[2],
                    "backend": "nvidia-smi",
                    "driver_version": parts[9],
                    "gpu_utilization_pct": _safe_float(parts[3]) or 0.0,
                    "memory_utilization_pct": round((used_mb / max(total_mb, 1e-6)) * 100.0, 2)
                    if total_mb > 0
                    else 0.0,
                    "memory_used_mb": used_mb,
                    "memory_free_mb": _safe_float(parts[5]) or 0.0,
                    "memory_total_mb": total_mb,
                    "temperature_c": _safe_float(parts[7]),
                    "power_draw_w": _safe_float(parts[8]),
                })
            return gpus if gpus else None
        except Exception:
            return None

    @classmethod
    def _probe_torch_cuda(cls) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "torch_installed": importlib.util.find_spec("torch") is not None,
            "cuda_available": False,
            "cuda_version": None,
            "mps_available": False,
            "gpus": [],
        }
        if not info["torch_installed"]:
            return info
        try:
            import torch

            info["torch_version"] = torch.__version__
            info["cuda_version"] = getattr(torch.version, "cuda", None)
            info["cuda_available"] = bool(torch.cuda.is_available())
            info["mps_available"] = bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
            if info["cuda_available"]:
                for idx in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(idx)
                    total_mb = round(props.total_memory / (1024 * 1024), 2)
                    alloc_mb = round(torch.cuda.memory_allocated(idx) / (1024 * 1024), 2)
                    reserved_mb = round(torch.cuda.memory_reserved(idx) / (1024 * 1024), 2)
                    info["gpus"].append({
                        "index": idx,
                        "name": props.name,
                        "backend": "torch.cuda",
                        "cuda_version": info["cuda_version"],
                        "gpu_utilization_pct": None,
                        "memory_utilization_pct": round((reserved_mb / max(total_mb, 1e-6)) * 100.0, 2),
                        "memory_used_mb": reserved_mb,
                        "memory_allocated_mb": alloc_mb,
                        "memory_free_mb": round(max(0.0, total_mb - reserved_mb), 2),
                        "memory_total_mb": total_mb,
                        "temperature_c": None,
                        "power_draw_w": None,
                        "compute_capability": f"{props.major}.{props.minor}",
                    })
        except Exception:
            pass
        return info

    @classmethod
    def get_system_telemetry(cls) -> Dict[str, Any]:
        """Collects authentic real-time CPU, RAM, Disk, and GPU metrics."""
        # 1. CPU & RAM telemetry via psutil
        cpu_percent = 0.0
        cpu_cores_logical = os.cpu_count() or 1
        cpu_cores_physical = cpu_cores_logical
        cpu_freq_mhz: Optional[float] = None
        ram_total_gb = 0.0
        ram_used_gb = 0.0
        ram_available_gb = 0.0
        ram_percent = 0.0
        disk_total_gb = 0.0
        disk_free_gb = 0.0

        if importlib.util.find_spec("psutil") is not None:
            try:
                import psutil

                cpu_percent = float(psutil.cpu_percent(interval=0.05))
                cpu_cores_logical = psutil.cpu_count(logical=True) or cpu_cores_logical
                cpu_cores_physical = psutil.cpu_count(logical=False) or cpu_cores_logical
                freq = psutil.cpu_freq()
                if freq and freq.current:
                    cpu_freq_mhz = round(float(freq.current), 1)

                vm = psutil.virtual_memory()
                ram_total_gb = round(vm.total / (1024 ** 3), 2)
                ram_used_gb = round(vm.used / (1024 ** 3), 2)
                ram_available_gb = round(vm.available / (1024 ** 3), 2)
                ram_percent = float(vm.percent)

                disk = psutil.disk_usage(os.getcwd())
                disk_total_gb = round(disk.total / (1024 ** 3), 2)
                disk_free_gb = round(disk.free / (1024 ** 3), 2)
            except Exception:
                pass
        else:
            try:
                disk = shutil.disk_usage(os.getcwd())
                disk_total_gb = round(disk.total / (1024 ** 3), 2)
                disk_free_gb = round(disk.free / (1024 ** 3), 2)
            except Exception:
                pass

        # 2. Genuine GPU Detection (NVML -> nvidia-smi -> PyTorch CUDA -> MPS)
        gpus = cls._probe_pynvml()
        if not gpus:
            gpus = cls._probe_nvidia_smi()

        torch_info = cls._probe_torch_cuda()
        if not gpus and torch_info["gpus"]:
            gpus = torch_info["gpus"]

        gpu_available = bool(gpus and len(gpus) > 0) or bool(torch_info.get("mps_available"))
        if gpus and len(gpus) > 0:
            accelerator = "cuda"
            gpu_status = f"GPU Online ({len(gpus)} device{'s' if len(gpus) > 1 else ''}: {gpus[0]['name']})"
        elif torch_info.get("mps_available"):
            accelerator = "mps"
            gpu_status = "Apple Silicon MPS Accelerator Online"
            gpus = [{
                "index": 0,
                "name": "Apple Silicon MPS GPU",
                "backend": "torch.mps",
                "gpu_utilization_pct": None,
                "memory_utilization_pct": None,
                "memory_used_mb": None,
                "memory_total_mb": None,
                "temperature_c": None,
            }]
        else:
            accelerator = "cpu"
            gpu_status = "GPU Unavailable — No CUDA/MPS hardware accelerator detected (CPU compute active)"
            gpus = []

        return {
            "timestamp": time.time(),
            "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "accelerator": accelerator,
            "gpu_available": gpu_available,
            "gpu_count": len(gpus),
            "gpu_status": gpu_status,
            "cuda_version": torch_info.get("cuda_version"),
            "torch_version": torch_info.get("torch_version"),
            "gpus": gpus,
            "cpu": {
                "utilization_pct": round(cpu_percent, 1),
                "cores_logical": cpu_cores_logical,
                "cores_physical": cpu_cores_physical,
                "frequency_mhz": cpu_freq_mhz,
            },
            "memory": {
                "ram_total_gb": ram_total_gb,
                "ram_used_gb": ram_used_gb,
                "ram_available_gb": ram_available_gb,
                "ram_utilization_pct": round(ram_percent, 1),
            },
            "disk": {
                "total_gb": disk_total_gb,
                "free_gb": disk_free_gb,
            },
        }

