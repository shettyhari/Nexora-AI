import logging
from typing import Any, Dict, List, Optional
import tiktoken
from app.services.llm.base import LLMMessage
from app.services.model_registry.registry import model_registry

logger = logging.getLogger(__name__)


class ContextBudget(Dict[str, int]):
    context_window: int
    max_output: int
    available_input: int
    rag_budget: int
    memory_budget: int


class ContextManager:
    """Intelligent Context Engine managing token accounting, context window budgeting, and compression."""

    def __init__(self):
        self._encoders: Dict[str, Any] = {}

    def _get_encoder(self, model_id: str) -> Any:
        if model_id in self._encoders:
            return self._encoders[model_id]

        try:
            if "gpt-4" in model_id or "o1" in model_id:
                enc = tiktoken.get_encoding("o200k_base")
            else:
                enc = tiktoken.get_encoding("cl100k_base")
            self._encoders[model_id] = enc
            return enc
        except Exception:
            return None

    def count_tokens(self, text: str, model_id: str = "gpt-4o") -> int:
        """Count tokens using tiktoken with fast heuristic fallback."""
        if not text:
            return 0
        enc = self._get_encoder(model_id)
        if enc:
            try:
                return len(enc.encode(text))
            except Exception:
                pass
        return max(1, int(len(text) / 3.8))

    def count_messages_tokens(self, messages: List[LLMMessage], model_id: str = "gpt-4o") -> int:
        """Count total tokens across all messages including role and formatting overhead."""
        total = 0
        for msg in messages:
            total += 3  # Message framing tokens
            total += self.count_tokens(msg.content, model_id)
            if msg.reasoning_content:
                total += self.count_tokens(msg.reasoning_content, model_id)
        return total + 3  # Priming tokens

    def get_model_budget(self, model_id: str) -> Dict[str, int]:
        """Compute strict token budget partitions for a given model."""
        desc = model_registry.get_model(model_id)
        context_window = desc.context_window if desc else 128000
        max_output = desc.max_output_tokens if desc else 4096

        safety_reserve = 1000
        available_input = max(2000, context_window - max_output - safety_reserve)

        # Proportional sub-budgets
        rag_budget = min(6000, int(available_input * 0.25))
        memory_budget = min(2000, int(available_input * 0.10))
        history_budget = available_input - rag_budget - memory_budget

        return {
            "context_window": context_window,
            "max_output": max_output,
            "available_input": available_input,
            "rag_budget": rag_budget,
            "memory_budget": memory_budget,
            "history_budget": history_budget
        }

    def compress_conversation_history(
        self,
        messages: List[LLMMessage],
        max_tokens: int,
        model_id: str = "gpt-4o",
        keep_recent_turns: int = 4
    ) -> List[LLMMessage]:
        """Compress older message turns into an executive summary when context limit is approached."""
        total_tokens = self.count_messages_tokens(messages, model_id)
        if total_tokens <= max_tokens or len(messages) <= keep_recent_turns:
            return messages

        # Split into older messages (to compress) and recent messages (to preserve intact)
        split_idx = max(0, len(messages) - keep_recent_turns)
        older_messages = messages[:split_idx]
        recent_messages = messages[split_idx:]

        # Create concise summary block from older messages
        summary_lines = []
        for msg in older_messages:
            preview = msg.content[:120].replace("\n", " ").strip()
            summary_lines.append(f"- {msg.role.upper()}: {preview}")

        summary_content = (
            "[CONVERSATION CONTEXT SUMMARY OF EARLIER MESSAGES]\n"
            + "\n".join(summary_lines)
            + "\n[END SUMMARY - RESUMING DIRECT DIALOGUE]"
        )

        compressed = [LLMMessage(role="system", content=summary_content)] + recent_messages
        return compressed

    def assemble_context(
        self,
        model_id: str,
        system_prompt: Optional[str],
        history_messages: List[LLMMessage],
        rag_context: Optional[str] = None,
        memory_context: Optional[str] = None
    ) -> List[LLMMessage]:
        """Assemble budgeted prompt messages ensuring context window limits are strictly preserved."""
        budget = self.get_model_budget(model_id)
        system_blocks = []

        if system_prompt:
            system_blocks.append(system_prompt.strip())

        if memory_context:
            system_blocks.append(f"--- RELEVANT USER & PROJECT MEMORIES ---\n{memory_context.strip()}\n---------------------------------------")

        if rag_context:
            system_blocks.append(rag_context.strip())

        unified_system_prompt = "\n\n".join(system_blocks) if system_blocks else None

        # Check token usage for system prompt
        system_tokens = self.count_tokens(unified_system_prompt or "", model_id)
        remaining_history_budget = max(1000, budget["available_input"] - system_tokens)

        # Compress message history if needed
        fitted_history = self.compress_conversation_history(
            messages=history_messages,
            max_tokens=remaining_history_budget,
            model_id=model_id,
            keep_recent_turns=4
        )

        final_messages = []
        if unified_system_prompt:
            final_messages.append(LLMMessage(role="system", content=unified_system_prompt))
        final_messages.extend(fitted_history)

        return final_messages


# Global singleton instance
context_manager = ContextManager()

