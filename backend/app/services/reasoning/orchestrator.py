import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.services.context.context_manager import context_manager
from app.services.llm.base import LLMMessage, LLMRequest, LLMStreamChunk
from app.services.llm.gateway import gateway
from app.services.memory.memory_service import memory_service
from app.services.rag.rag_service import rag_service
from app.services.router.model_router import model_router
from app.services.search_service import search_service

logger = logging.getLogger(__name__)


class ReasoningOrchestrator:
    """
    8-Stage Advanced Reasoning Orchestrator:
    1. Classify Request -> 2. Identify Capabilities -> 3. Determine Tools ->
    4. Retrieve Context (Memory + RAG + Web) -> 5. Select Model -> 6. Assemble Context ->
    7. Execute Streaming -> 8. Validate & Deliver Response.
    """

    async def execute_reasoning_flow(
        self,
        db: AsyncSession,
        user_id: str,
        prompt: str,
        conversation_history: List[LLMMessage],
        requested_model_id: Optional[str] = None,
        reasoning_mode: bool = False,
        web_search: bool = False,
        project_id: Optional[str] = None,
        attachments: Optional[List[Any]] = None
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        # Stage 1: Classify request and task profile
        task_profile = model_router.analyze_prompt(prompt, attachments, conversation_history)

        # Stage 2 & 3: Determine Tools & Capabilities
        # Check if user needs memory, RAG, and/or web grounding
        memories_text = ""
        rag_context_text = ""
        citations_list: List[Dict[str, Any]] = []

        # 4. Context Retrieval: Memory
        try:
            memories = await memory_service.retrieve_relevant_memories(
                db=db,
                user_id=user_id,
                query=prompt,
                project_id=project_id,
                top_k=3,
                min_similarity=0.45
            )
            if memories:
                mem_lines = [f"- [{m.category.upper()}]: {m.content}" for m in memories]
                memories_text = "\n".join(mem_lines)
        except Exception as e:
            logger.warning(f"Memory retrieval skip: {e}")

        # 4. Context Retrieval: RAG Knowledge Base
        try:
            rag_chunks = await rag_service.hybrid_search(
                db=db,
                user_id=user_id,
                query=prompt,
                project_id=project_id,
                top_k=4
            )
            if rag_chunks:
                rag_context_text, citations_objs = rag_service.format_rag_context(rag_chunks)
                citations_list = [c.model_dump() for c in citations_objs]
        except Exception as e:
            logger.warning(f"RAG retrieval skip: {e}")

        # 4. Context Retrieval: Web Search
        web_search_text = ""
        if web_search:
            try:
                search_results = await search_service.search(prompt, max_results=3)
                if search_results:
                    search_blocks = [f"Source: {res.title} ({res.url})\n{res.snippet}" for res in search_results]
                    web_search_text = "--- LIVE WEB SEARCH GROUNDING ---\n" + "\n\n".join(search_blocks) + "\n--------------------------------\n"
            except Exception as e:
                logger.warning(f"Web search skip: {e}")

        # Stage 5: Select Appropriate Model via Intelligent Router (or manual override)
        routing_decision = model_router.route(
            requested_model_id=requested_model_id,
            prompt=prompt,
            attachments=attachments,
            message_history=conversation_history
        )
        resolved_model = routing_decision.selected_model_id
        routing_reason = routing_decision.reason

        # Emit initial metadata chunk so client knows which model was selected and why!
        yield LLMStreamChunk(
            type="usage",
            resolved_model=resolved_model,
            routing_reason=routing_reason,
            citations=citations_list if citations_list else None
        )

        # Stage 6: Assemble and Budget Context
        combined_external_context = ""
        if web_search_text:
            combined_external_context += web_search_text + "\n"
        if rag_context_text:
            combined_external_context += rag_context_text

        system_instruction = (
            "You are NEXORA AI, an autonomous intelligence engine. "
            "Deliver direct, rigorous, clear solutions with high technical precision. "
            "Use Markdown formatting, syntax-highlighted code blocks, and KaTeX math ($...$ or $$...$$). "
            "When knowledge citations or sources are provided, ground your response and reference them accurately."
        )

        # Build full message history including user prompt
        full_history = conversation_history.copy()
        full_history.append(LLMMessage(role="user", content=prompt))

        assembled_messages = context_manager.assemble_context(
            model_id=resolved_model,
            system_prompt=system_instruction,
            history_messages=full_history,
            rag_context=combined_external_context if combined_external_context else None,
            memory_context=memories_text if memories_text else None
        )

        # Stage 7: Execute Streaming via Unified Model Gateway
        llm_request = LLMRequest(
            messages=assembled_messages,
            model=resolved_model,
            reasoning_mode=reasoning_mode,
            temperature=0.7,
            user_id=user_id
        )

        async for chunk in gateway.stream(llm_request):
            chunk.resolved_model = resolved_model
            chunk.routing_reason = routing_reason
            if citations_list and chunk.type == "done":
                chunk.citations = citations_list
            yield chunk


# Global singleton orchestrator
reasoning_orchestrator = ReasoningOrchestrator()
