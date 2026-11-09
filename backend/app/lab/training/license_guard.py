"""
Model & Dataset License Compatibility Verification Guard.
Enforces legal & ethical license compliance prior to initiating fine-tuning or commercial deployment.
"""
from typing import Any, Dict, List


class LicenseGuard:
    """Evaluates whether base model + dataset licenses permit fine-tuning and intended deployment."""

    # Licenses allowing derivative fine-tuning + commercial deployment
    PERMISSIVE_LICENSES = {
        "apache-2.0",
        "mit",
        "bsd-3-clause",
        "bsd-2-clause",
        "isc",
        "cc-by-4.0",
        "cc0-1.0",
        "proprietary-commercial",
        "proprietary-enterprise",
        "proprietary-curated",
    }

    # Licenses allowing modifications + deployment under behavioral use restrictions
    RAIL_OR_COMMUNITY_LICENSES = {
        "openrail-m",
        "llama-3.1-community",
        "llama-3-community",
        "gemma-terms",
        "mistral-research",
    }

    # Strict non-commercial / research-only licenses
    NON_COMMERCIAL_LICENSES = {
        "cc-by-nc-4.0",
        "cc-by-nc-sa-4.0",
        "proprietary-research",
        "nc-research-only",
    }

    # Copyleft licenses requiring derivative distribution under identical terms
    COPYLEFT_LICENSES = {
        "gpl-3.0",
        "agpl-3.0",
    }

    @classmethod
    def _normalize(cls, license_str: str) -> str:
        s = (license_str or "").strip().lower()
        if "apache" in s:
            return "apache-2.0"
        if "mit" == s or "mit " in s:
            return "mit"
        if "cc-by-nc" in s:
            return "cc-by-nc-4.0"
        if "cc-by-4.0" in s or "creative commons attribution" in s:
            return "cc-by-4.0"
        if "openrail" in s:
            return "openrail-m"
        if "llama" in s and "community" in s:
            return "llama-3.1-community"
        if "proprietary-commercial" in s:
            return "proprietary-commercial"
        if "proprietary-enterprise" in s:
            return "proprietary-enterprise"
        if "proprietary-curated" in s or "proprietary curated" in s:
            return "proprietary-curated"
        if "proprietary-research" in s or "academic & internal" in s:
            return "proprietary-research"
        if "gpl" in s:
            return "gpl-3.0"
        return s or "unknown"

    @classmethod
    def verify_compatibility(
        cls,
        base_model_license: str,
        dataset_license: str,
        intended_use: str = "research",
        training_method: str = "sft",
    ) -> Dict[str, Any]:
        """
        Checks base model license, dataset license, and intended use (`research`, `internal`, `commercial`).
        Returns structured verification status, warnings, and blocking reasons.
        """
        model_norm = cls._normalize(base_model_license)
        dataset_norm = cls._normalize(dataset_license)
        use_norm = (intended_use or "research").strip().lower()

        warnings: List[str] = []
        errors: List[str] = []

        if model_norm == "unknown":
            errors.append(f"Base model license '{base_model_license}' is unknown or missing.")
        if dataset_norm == "unknown":
            errors.append(f"Dataset license '{dataset_license}' is unknown or missing.")

        # Block non-commercial assets when intended use is commercial
        if use_norm == "commercial":
            if model_norm in cls.NON_COMMERCIAL_LICENSES or "nc" in model_norm or "research-only" in model_norm:
                errors.append(
                    f"Base model license '{base_model_license}' prohibits commercial fine-tuning/deployment."
                )
            if dataset_norm in cls.NON_COMMERCIAL_LICENSES or "nc" in dataset_norm:
                errors.append(
                    f"Dataset license '{dataset_license}' prohibits commercial derivative model training."
                )
            if model_norm in cls.COPYLEFT_LICENSES or dataset_norm in cls.COPYLEFT_LICENSES:
                warnings.append(
                    f"Copyleft terms detected ({base_model_license} / {dataset_license}); derivative weights may require source disclosure."
                )

        if model_norm in cls.RAIL_OR_COMMUNITY_LICENSES:
            warnings.append(
                f"Base model uses responsible/community terms ({base_model_license}); behavioral acceptable-use clauses apply."
            )

        if model_norm == "proprietary-research" and use_norm in ("research", "internal"):
            warnings.append(
                f"Model license '{base_model_license}' restricts fine-tuned weights to internal/academic research only."
            )

        if training_method in ("dpo", "grpo", "qlora", "lora", "sft", "instruction", "pretrain"):
            # Fine-tuning & LoRA adapters create derivative works under base model terms
            obligations = ["Preserve attribution notices and base model card metadata."]
            if training_method in ("lora", "qlora"):
                obligations.append(
                    "LoRA/QLoRA adapter weights inherit use restrictions of both base model and training dataset."
                )
        else:
            obligations = []

        approved = len(errors) == 0
        return {
            "approved": approved,
            "intended_use": use_norm,
            "training_method": training_method,
            "base_model_license": base_model_license,
            "base_model_normalized": model_norm,
            "dataset_license": dataset_license,
            "dataset_normalized": dataset_norm,
            "errors": errors,
            "warnings": warnings,
            "obligations": obligations,
        }

