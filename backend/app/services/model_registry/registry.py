from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelProvider(str, Enum):
    NEXORA = "nexora"
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    OPENAI_COMPATIBLE = "openai_compatible"


class ModelStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class ModelDeployment(str, Enum):
    CLOUD = "cloud"
    SELF_HOSTED = "self_hosted"
    LOCAL = "local"


class ModelCapabilities(BaseModel):
    streaming: bool = True
    reasoning: bool = False
    vision: bool = False
    function_calling: bool = True
    json_output: bool = True
    code_interpreter: bool = False


class ModelPricing(BaseModel):
    input_per_million: float = 0.0   # USD per 1M input tokens
    output_per_million: float = 0.0  # USD per 1M output tokens

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost = (prompt_tokens / 1_000_000.0) * self.input_per_million
        output_cost = (completion_tokens / 1_000_000.0) * self.output_per_million
        return round(input_cost + output_cost, 6)


class ModelDescriptor(BaseModel):
    id: str
    name: str
    provider: ModelProvider
    version: str = "1.0"
    description: str = ""
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    context_window: int = 128000
    max_output_tokens: int = 4096
    supported_modalities: List[str] = Field(default_factory=lambda: ["text"])
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    availability: str = "public"
    deployment: ModelDeployment = ModelDeployment.CLOUD
    status: ModelStatus = ModelStatus.ACTIVE
    is_default: bool = False
    recommended_intents: List[str] = Field(default_factory=lambda: ["general"])


class ModelRegistry:
    """Centralized Model Registry managing all LLM specifications, pricing, capabilities, and availability."""

    def __init__(self):
        self._models: Dict[str, ModelDescriptor] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        defaults = [
            # 1. Virtual Auto Router
            ModelDescriptor(
                id="nexora-auto",
                name="NEXORA Auto Router",
                provider=ModelProvider.NEXORA,
                version="2.0",
                description="Intelligent autonomous model router. Automatically matches your task to the optimal model based on intent, complexity, speed, and cost.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=2000000,
                max_output_tokens=8192,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=0.50, output_per_million=2.00),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=True,
                recommended_intents=["general", "auto", "coding", "reasoning", "fast"]
            ),

            # 2. NEXORA Proprietary Flagship
            ModelDescriptor(
                id="nexora-flagship",
                name="NEXORA Flagship 2.0",
                provider=ModelProvider.NEXORA,
                version="2.0",
                description="NEXORA autonomous deep-reasoning neural model. Optimized for code synthesis, complex system architecture, and tool use.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=True,
                    function_calling=True,
                    json_output=True,
                    code_interpreter=True
                ),
                context_window=128000,
                max_output_tokens=8192,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=1.50, output_per_million=6.00),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["coding", "reasoning", "architecture"]
            ),

            # 3. NEXORA Fast
            ModelDescriptor(
                id="nexora-fast",
                name="NEXORA Fast",
                provider=ModelProvider.NEXORA,
                version="1.5",
                description="Ultra-low latency model for high-throughput chatting, summarization, and interactive tasks.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=False,
                    vision=False,
                    function_calling=True,
                    json_output=True
                ),
                context_window=64000,
                max_output_tokens=4096,
                supported_modalities=["text"],
                pricing=ModelPricing(input_per_million=0.10, output_per_million=0.40),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["fast", "summarization", "simple_qa"]
            ),

            # 4. Google Gemini 1.5 Pro
            ModelDescriptor(
                id="gemini-1.5-pro",
                name="Google Gemini 1.5 Pro",
                provider=ModelProvider.GOOGLE,
                version="002",
                description="Google flagship multimodal foundation model with 2M token context window and advanced mathematical/analytical reasoning.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=2000000,
                max_output_tokens=8192,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=1.25, output_per_million=5.00),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["reasoning", "vision", "large_context", "analysis"]
            ),

            # 5. Google Gemini 1.5 Flash
            ModelDescriptor(
                id="gemini-1.5-flash",
                name="Google Gemini 1.5 Flash",
                provider=ModelProvider.GOOGLE,
                version="002",
                description="Fast and cost-efficient multimodal model with 1M context window for real-time applications.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=False,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=1000000,
                max_output_tokens=8192,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=0.075, output_per_million=0.30),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["fast", "vision", "general"]
            ),

            # 6. OpenAI GPT-4o
            ModelDescriptor(
                id="gpt-4o",
                name="OpenAI GPT-4o",
                provider=ModelProvider.OPENAI,
                version="2024-08-06",
                description="OpenAI flagship omni model for multimodal intelligence, code generation, and complex instruction following.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=128000,
                max_output_tokens=4096,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=2.50, output_per_million=10.00),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["coding", "reasoning", "general", "structured_output"]
            ),

            # 7. OpenAI GPT-4o Mini
            ModelDescriptor(
                id="gpt-4o-mini",
                name="OpenAI GPT-4o Mini",
                provider=ModelProvider.OPENAI,
                version="2024-07-18",
                description="Affordable, fast, and intelligent small model for lightweight reasoning and high-volume tasks.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=False,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=128000,
                max_output_tokens=4096,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=0.15, output_per_million=0.60),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["fast", "simple_qa", "cost_sensitive"]
            ),

            # 8. Anthropic Claude 3.5 Sonnet
            ModelDescriptor(
                id="claude-3-5-sonnet",
                name="Anthropic Claude 3.5 Sonnet",
                provider=ModelProvider.ANTHROPIC,
                version="20241022",
                description="Industry-leading frontier model for software engineering, deep architectural analysis, and nuanced multi-step reasoning.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=True,
                    function_calling=True,
                    json_output=True
                ),
                context_window=200000,
                max_output_tokens=8192,
                supported_modalities=["text", "image"],
                pricing=ModelPricing(input_per_million=3.00, output_per_million=15.00),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["coding", "architecture", "analysis", "reasoning"]
            ),

            # 9. Hugging Face Llama 3.1 70B
            ModelDescriptor(
                id="hf-llama-3-70b",
                name="Meta Llama 3.1 70B (HF)",
                provider=ModelProvider.HUGGINGFACE,
                version="3.1-70b-instruct",
                description="Open-weights flagship model hosted via Hugging Face Inference Endpoints.",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=True,
                    vision=False,
                    function_calling=True,
                    json_output=True
                ),
                context_window=128000,
                max_output_tokens=4096,
                supported_modalities=["text"],
                pricing=ModelPricing(input_per_million=0.70, output_per_million=0.90),
                deployment=ModelDeployment.CLOUD,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["open_weights", "general", "coding"]
            ),

            # 10. OpenAI-Compatible Self-Hosted (Ollama / vLLM)
            ModelDescriptor(
                id="ollama-local",
                name="Self-Hosted Inference (Ollama / vLLM)",
                provider=ModelProvider.OPENAI_COMPATIBLE,
                version="custom",
                description="Local private inference via OpenAI-compatible endpoints (Ollama, vLLM, LM Studio).",
                capabilities=ModelCapabilities(
                    streaming=True,
                    reasoning=False,
                    vision=False,
                    function_calling=True,
                    json_output=True
                ),
                context_window=32000,
                max_output_tokens=4096,
                supported_modalities=["text"],
                pricing=ModelPricing(input_per_million=0.0, output_per_million=0.0),
                deployment=ModelDeployment.SELF_HOSTED,
                status=ModelStatus.ACTIVE,
                is_default=False,
                recommended_intents=["private", "offline", "local"]
            )
        ]

        for model in defaults:
            self._models[model.id] = model

    def register_model(self, descriptor: ModelDescriptor) -> None:
        self._models[descriptor.id] = descriptor

    def get_model(self, model_id: str) -> Optional[ModelDescriptor]:
        return self._models.get(model_id)

    def list_models(
        self,
        include_inactive: bool = False,
        provider: Optional[ModelProvider] = None,
        modality: Optional[str] = None
    ) -> List[ModelDescriptor]:
        result = []
        for model in self._models.values():
            if not include_inactive and model.status != ModelStatus.ACTIVE:
                continue
            if provider and model.provider != provider:
                continue
            if modality and modality not in model.supported_modalities:
                continue
            result.append(model)
        return result

    def calculate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        model = self.get_model(model_id)
        if not model:
            return 0.0
        return model.pricing.calculate_cost(prompt_tokens, completion_tokens)

    def update_status(self, model_id: str, status: ModelStatus) -> bool:
        if model_id in self._models:
            self._models[model_id].status = status
            return True
        return False


# Global singleton instance
model_registry = ModelRegistry()
