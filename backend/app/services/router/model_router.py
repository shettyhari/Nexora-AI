import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.config import settings
from app.services.model_registry.registry import ModelProvider, model_registry

logger = logging.getLogger(__name__)


class TaskProfile(BaseModel):
    intent: str = "general"  # coding, deep_reasoning, vision, fast_chat, large_context, creative, general
    complexity: str = "medium"  # simple, medium, complex
    requires_vision: bool = False
    requires_code: bool = False
    requires_reasoning: bool = False
    estimated_tokens: int = 0
    urgency: str = "balanced"  # high_speed, balanced, deep_quality


class RoutingDecision(BaseModel):
    selected_model_id: str
    provider: str
    reason: str
    confidence: float = 1.0
    is_override: bool = False
    task_profile: TaskProfile = Field(default_factory=TaskProfile)


class IntelligentModelRouter:
    """Intelligent Model Router that analyzes user prompts and routes to the optimal LLM."""

    # Keywords for intent detection
    CODING_KEYWORDS = [
        "code", "python", "javascript", "typescript", "rust", "c++", "golang", "sql",
        "function", "class", "def ", "async ", "bug", "refactor", "algorithm",
        "docker", "kubernetes", "regex", "api", "endpoint", "git", "syntax", "compile",
        "script", "program", "implement", "distributed", "tokio", "mutex", "lock"
    ]

    REASONING_KEYWORDS = [
        "proof", "prove", "derive", "calculate", "mathematical", "theorem", "quantum",
        "deduce", "evaluate tradeoff", "step-by-step", "architect", "formal logic",
        "complexity analysis", "causality", "simulation"
    ]

    FAST_KEYWORDS = [
        "hi", "hello", "who are you", "what is", "quick", "summarize in 1 sentence",
        "define", "translate", "list 3", "synonym"
    ]

    def analyze_prompt(
        self,
        prompt: str,
        attachments: Optional[List[Any]] = None,
        message_history: Optional[List[Any]] = None
    ) -> TaskProfile:
        text = prompt.lower()
        requires_vision = False

        # 1. Vision check
        if attachments:
            for att in attachments:
                mime = getattr(att, "mime_type", "") if not isinstance(att, dict) else att.get("mime_type", "")
                if mime.startswith("image/"):
                    requires_vision = True
                    break

        if not requires_vision and any(w in text for w in ["look at this image", "in this picture", "describe the photo"]):
            requires_vision = True

        # 2. Code check
        has_code_syntax = bool(re.search(r"```|def\s+\w+|function\s+\w+|class\s+\w+|SELECT\s+.+FROM", prompt))
        code_hits = sum(1 for kw in self.CODING_KEYWORDS if kw in text)
        requires_code = has_code_syntax or code_hits >= 1

        # 3. Reasoning check
        reasoning_hits = sum(1 for kw in self.REASONING_KEYWORDS if kw in text)
        requires_reasoning = reasoning_hits >= 2 or ("why" in text and len(text) > 200)

        # 4. Context estimation
        history_tokens = 0
        if message_history:
            for m in message_history:
                c = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
                history_tokens += len(c) // 4
        prompt_tokens = len(prompt) // 4
        total_estimated = history_tokens + prompt_tokens

        # 5. Complexity determination
        is_complex_coding = requires_code and any(kw in text for kw in [
            "distributed", "concurrent", "tokio", "mutex", "lock", "architect",
            "scale", "performance", "optimize", "kernel", "protocol"
        ])

        if total_estimated > 50000 or (requires_code and requires_reasoning) or len(prompt) > 2000 or is_complex_coding:
            complexity = "complex"
        elif any(prompt.strip().lower() == k for k in ["hi", "hello", "hey", "test"]) or (len(prompt) < 40 and not requires_code):
            complexity = "simple"
        else:
            complexity = "medium"

        # 6. Intent classification
        if requires_vision:
            intent = "vision"
        elif total_estimated > 40000:
            intent = "large_context"
        elif requires_code:
            intent = "coding"
        elif requires_reasoning:
            intent = "deep_reasoning"
        elif complexity == "simple":
            intent = "fast_chat"
        else:
            intent = "general"

        urgency = "high_speed" if complexity == "simple" else ("deep_quality" if complexity == "complex" else "balanced")

        return TaskProfile(
            intent=intent,
            complexity=complexity,
            requires_vision=requires_vision,
            requires_code=requires_code,
            requires_reasoning=requires_reasoning,
            estimated_tokens=total_estimated,
            urgency=urgency
        )

    def route(
        self,
        requested_model_id: Optional[str],
        prompt: str,
        attachments: Optional[List[Any]] = None,
        message_history: Optional[List[Any]] = None
    ) -> RoutingDecision:
        profile = self.analyze_prompt(prompt, attachments, message_history)

        # 1. Manual user override check:
        # If user explicitly selected a concrete model (anything other than 'auto' or 'nexora-auto'), honor the override!
        if requested_model_id and requested_model_id not in ["auto", "nexora-auto"]:
            target_desc = model_registry.get_model(requested_model_id)
            if target_desc:
                return RoutingDecision(
                    selected_model_id=target_desc.id,
                    provider=target_desc.provider.value,
                    reason=f"Manual user override: explicitly selected '{target_desc.name}'",
                    confidence=1.0,
                    is_override=True,
                    task_profile=profile
                )

        # 2. Autonomous Routing based on task profile & provider health/keys
        has_gemini = bool(settings.GEMINI_API_KEY)
        has_openai = bool(settings.OPENAI_API_KEY)
        has_anthropic = bool(settings.ANTHROPIC_API_KEY)

        # Case A: Vision
        if profile.requires_vision:
            if has_gemini:
                return RoutingDecision(
                    selected_model_id="gemini-1.5-flash",
                    provider="google",
                    reason="Autonomous routing: Multimodal vision query routed to Gemini 1.5 Flash for high-speed visual parsing",
                    confidence=0.95,
                    task_profile=profile
                )
            elif has_openai:
                return RoutingDecision(
                    selected_model_id="gpt-4o",
                    provider="openai",
                    reason="Autonomous routing: Multimodal image analysis routed to OpenAI GPT-4o",
                    confidence=0.92,
                    task_profile=profile
                )
            else:
                return RoutingDecision(
                    selected_model_id="nexora-flagship",
                    provider="nexora",
                    reason="Autonomous routing: Vision query routed to NEXORA Flagship multimodal engine",
                    confidence=0.88,
                    task_profile=profile
                )

        # Case B: Large Context (> 40K tokens)
        if profile.intent == "large_context":
            if has_gemini:
                return RoutingDecision(
                    selected_model_id="gemini-1.5-pro",
                    provider="google",
                    reason=f"Autonomous routing: Large context ({profile.estimated_tokens:,} tokens) routed to Gemini 1.5 Pro (2M token capacity)",
                    confidence=0.98,
                    task_profile=profile
                )
            elif has_anthropic:
                return RoutingDecision(
                    selected_model_id="claude-3-5-sonnet",
                    provider="anthropic",
                    reason=f"Autonomous routing: Large context ({profile.estimated_tokens:,} tokens) routed to Claude 3.5 Sonnet (200K token capacity)",
                    confidence=0.94,
                    task_profile=profile
                )

        # Case C: High Complexity Coding or Architecture
        if profile.requires_code and profile.complexity == "complex":
            if has_anthropic:
                return RoutingDecision(
                    selected_model_id="claude-3-5-sonnet",
                    provider="anthropic",
                    reason="Autonomous routing: High-complexity software architecture task routed to Claude 3.5 Sonnet",
                    confidence=0.96,
                    task_profile=profile
                )
            elif has_openai:
                return RoutingDecision(
                    selected_model_id="gpt-4o",
                    provider="openai",
                    reason="Autonomous routing: Complex coding task routed to OpenAI GPT-4o",
                    confidence=0.93,
                    task_profile=profile
                )
            elif has_gemini:
                return RoutingDecision(
                    selected_model_id="gemini-1.5-pro",
                    provider="google",
                    reason="Autonomous routing: Advanced programming task routed to Gemini 1.5 Pro",
                    confidence=0.90,
                    task_profile=profile
                )
            else:
                return RoutingDecision(
                    selected_model_id="nexora-flagship",
                    provider="nexora",
                    reason="Autonomous routing: High-complexity coding task routed to NEXORA Flagship 2.0",
                    confidence=0.89,
                    task_profile=profile
                )

        # Case D: Deep Mathematical / Formal Reasoning
        if profile.requires_reasoning and profile.complexity in ["medium", "complex"]:
            if has_gemini:
                return RoutingDecision(
                    selected_model_id="gemini-1.5-pro",
                    provider="google",
                    reason="Autonomous routing: Formal mathematical and analytical reasoning routed to Gemini 1.5 Pro",
                    confidence=0.95,
                    task_profile=profile
                )
            elif has_openai:
                return RoutingDecision(
                    selected_model_id="gpt-4o",
                    provider="openai",
                    reason="Autonomous routing: Deep reasoning task routed to OpenAI GPT-4o",
                    confidence=0.91,
                    task_profile=profile
                )
            else:
                return RoutingDecision(
                    selected_model_id="nexora-flagship",
                    provider="nexora",
                    reason="Autonomous routing: Deep analytical task routed to NEXORA Flagship Reasoning Engine",
                    confidence=0.88,
                    task_profile=profile
                )

        # Case E: Fast Chat / Simple Q&A
        if profile.complexity == "simple":
            if has_gemini:
                return RoutingDecision(
                    selected_model_id="gemini-1.5-flash",
                    provider="google",
                    reason="Autonomous routing: Lightweight conversational query routed to Gemini 1.5 Flash for sub-second latency",
                    confidence=0.94,
                    task_profile=profile
                )
            elif has_openai:
                return RoutingDecision(
                    selected_model_id="gpt-4o-mini",
                    provider="openai",
                    reason="Autonomous routing: Fast Q&A query routed to GPT-4o Mini for optimal cost and speed",
                    confidence=0.92,
                    task_profile=profile
                )
            else:
                return RoutingDecision(
                    selected_model_id="nexora-fast",
                    provider="nexora",
                    reason="Autonomous routing: Simple chat query routed to NEXORA Fast",
                    confidence=0.90,
                    task_profile=profile
                )

        # Default fallback routing
        if has_gemini:
            return RoutingDecision(
                selected_model_id="gemini-1.5-flash",
                provider="google",
                reason="Autonomous routing: Balanced performance routed to Gemini 1.5 Flash",
                confidence=0.85,
                task_profile=profile
            )
        elif has_openai:
            return RoutingDecision(
                selected_model_id="gpt-4o",
                provider="openai",
                reason="Autonomous routing: Balanced general query routed to OpenAI GPT-4o",
                confidence=0.85,
                task_profile=profile
            )
        else:
            return RoutingDecision(
                selected_model_id="nexora-flagship",
                provider="nexora",
                reason="Autonomous routing: Balanced general query routed to NEXORA Flagship",
                confidence=0.85,
                task_profile=profile
            )


# Global singleton instance
model_router = IntelligentModelRouter()
