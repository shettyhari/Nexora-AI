import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, AsyncGenerator, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.usage import UsageRecord
from app.models.user import User
from app.schemas.auth import MessageResponse as SimpleResponse
from app.schemas.message import (
    MessageCreateRequest,
    MessageEditRequest,
    MessageResponse
)
from app.services.llm.base import LLMMessage
from app.services.memory.memory_service import memory_service
from app.services.model_registry.registry import model_registry
from app.services.reasoning.orchestrator import reasoning_orchestrator

router = APIRouter(prefix="/messages", tags=["Messages"])
logger = logging.getLogger(__name__)


async def generate_chat_stream(
    user_id: str,
    conversation_id: str,
    user_message_id: str,
    assistant_message_id: str,
    model_name: str,
    reasoning_mode: bool,
    web_search: bool,
    user_prompt: str,
    attachment_ids: Optional[List[str]] = None
) -> AsyncGenerator[str, None]:
    """Stream AI tokens, update database on finish, and yield SSE."""
    start_time = time.time()
    accumulated_content = []
    accumulated_reasoning = []
    tokens_prompt = 0
    tokens_completion = 0
    resolved_model = model_name
    routing_reason = ""
    citations_data: List[Dict[str, Any]] = []

    # Yield initial start event
    yield f"data: {json.dumps({'type': 'start', 'message_id': assistant_message_id, 'conversation_id': conversation_id})}\n\n"

    try:
        # 1. Fetch conversation history and attachments inside isolated session
        async with AsyncSessionLocal() as session:
            conv_q = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            conv_res = await session.execute(conv_q)
            conv = conv_res.scalar_one_or_none()
            project_id = conv.project_id if conv else None

            # Fetch recent messages
            msgs_q = (
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.id != assistant_message_id,
                    Message.id != user_message_id
                )
                .order_by(Message.created_at.asc())
            )
            msgs_res = await session.execute(msgs_q)
            db_messages = msgs_res.scalars().all()

            # Fetch attachments
            attachments_objs = []
            if attachment_ids:
                att_q = select(Attachment).where(Attachment.id.in_(attachment_ids))
                att_res = await session.execute(att_q)
                attachments_objs = list(att_res.scalars().all())

        # 2. Build LLM message list for prior history
        history_llm = []
        for msg in db_messages:
            history_llm.append(LLMMessage(
                role=msg.role,
                content=msg.content,
                reasoning_content=msg.reasoning_content
            ))

        # 3. Execute 8-stage Advanced Reasoning Flow
        async for chunk in reasoning_orchestrator.execute_reasoning_flow(
            db=session,
            user_id=user_id,
            prompt=user_prompt,
            conversation_history=history_llm,
            requested_model_id=model_name,
            reasoning_mode=reasoning_mode,
            web_search=web_search,
            project_id=project_id,
            attachments=attachments_objs
        ):
            if chunk.resolved_model:
                resolved_model = chunk.resolved_model
            if chunk.routing_reason:
                routing_reason = chunk.routing_reason
            if chunk.citations:
                citations_data = chunk.citations

            if chunk.type == "token":
                accumulated_content.append(chunk.content)
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content, 'resolved_model': resolved_model})}\n\n"

            elif chunk.type == "reasoning":
                accumulated_reasoning.append(chunk.content)
                yield f"data: {json.dumps({'type': 'reasoning', 'content': chunk.content, 'resolved_model': resolved_model})}\n\n"

            elif chunk.type == "usage":
                # Metadata / Router notification
                payload = {
                    "type": "routing",
                    "resolved_model": resolved_model,
                    "routing_reason": routing_reason
                }
                if citations_data:
                    payload["citations"] = citations_data
                yield f"data: {json.dumps(payload)}\n\n"

            elif chunk.type == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': chunk.content})}\n\n"

            elif chunk.type == "done":
                if chunk.usage:
                    tokens_prompt = chunk.usage.prompt_tokens
                    tokens_completion = chunk.usage.completion_tokens
                break

    except Exception as e:
        logger.exception("Error during LLM streaming")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Streaming interrupted: {str(e)}'})}\n\n"

    # 4. Persist assistant message, routing metadata, citations, and usage
    latency_ms = int((time.time() - start_time) * 1000)
    full_content = "".join(accumulated_content)
    full_reasoning = "".join(accumulated_reasoning) if accumulated_reasoning else None

    try:
        async with AsyncSessionLocal() as session:
            # Update assistant message
            asst_msg = await session.get(Message, assistant_message_id)
            if asst_msg:
                asst_msg.content = full_content or "No response generated."
                asst_msg.reasoning_content = full_reasoning
                asst_msg.model = resolved_model
                asst_msg.routing_reason = routing_reason
                if citations_data:
                    asst_msg.citations_json = json.dumps(citations_data)
                asst_msg.tokens_used = tokens_prompt + tokens_completion
                asst_msg.updated_at = datetime.now(timezone.utc)

            # Update conversation timestamp & title if default
            conv = await session.get(Conversation, conversation_id)
            if conv:
                conv.updated_at = datetime.now(timezone.utc)
                if conv.title == "New Chat":
                    clean_title = user_prompt.strip().replace("\n", " ")
                    conv.title = (clean_title[:36] + "...") if len(clean_title) > 36 else clean_title

            # Create usage record
            usage = UsageRecord(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=assistant_message_id,
                model=resolved_model,
                prompt_tokens=tokens_prompt,
                completion_tokens=tokens_completion,
                total_tokens=tokens_prompt + tokens_completion,
                latency_ms=latency_ms
            )
            session.add(usage)
            await session.commit()

            # Automatic memory extraction: check if user expressed an explicit preference
            prompt_lower = user_prompt.lower()
            if any(p in prompt_lower for p in ["i prefer", "remember that", "my name is", "i work as", "always use", "never use"]):
                try:
                    await memory_service.store_memory(
                        db=session,
                        user_id=user_id,
                        content=user_prompt.strip(),
                        memory_type="user_preference",
                        category="preference",
                        conversation_id=conversation_id
                    )
                except Exception as mem_err:
                    logger.debug(f"Auto-memory store skip: {mem_err}")

    except Exception as e:
        logger.error(f"Failed to persist stream output: {e}")

    yield f"data: {json.dumps({'type': 'done', 'finish_reason': 'stop', 'resolved_model': resolved_model, 'citations': citations_data})}\n\n"


@router.post("", response_class=StreamingResponse)
async def send_message(
    data: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and stream the assistant's response via Server-Sent Events (SSE).
    """
    conversation_id = data.conversation_id

    # 1. Resolve or create conversation
    if conversation_id:
        conv_q = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        conv_res = await db.execute(conv_q)
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied"
            )
    else:
        # Auto-create conversation
        title = data.content.strip()[:36] + "..." if len(data.content.strip()) > 36 else data.content.strip()
        conv = Conversation(
            user_id=current_user.id,
            title=title or "New Chat",
            model_id=data.model or settings.DEFAULT_MODEL_ID,
            reasoning_mode=bool(data.reasoning_mode),
            web_search_enabled=bool(data.web_search)
        )
        db.add(conv)
        await db.flush()
        conversation_id = conv.id

    model_name = data.model or conv.model_id or settings.DEFAULT_MODEL_ID
    reasoning_mode = data.reasoning_mode if data.reasoning_mode is not None else conv.reasoning_mode
    web_search = data.web_search if data.web_search is not None else conv.web_search_enabled

    # 2. Persist User Message
    user_msg = Message(
        conversation_id=conversation_id,
        user_id=current_user.id,
        parent_id=data.parent_id,
        role="user",
        content=data.content,
        model=model_name
    )
    db.add(user_msg)
    await db.flush()

    # Link attachments if any
    if data.attachment_ids:
        for att_id in data.attachment_ids:
            att = await db.get(Attachment, att_id)
            if att and att.user_id == current_user.id:
                att.message_id = user_msg.id
                att.conversation_id = conversation_id

    # 3. Create Placeholder Assistant Message
    asst_msg = Message(
        conversation_id=conversation_id,
        user_id=current_user.id,
        parent_id=user_msg.id,
        role="assistant",
        content="",
        model=model_name
    )
    db.add(asst_msg)
    await db.commit()

    return StreamingResponse(
        generate_chat_stream(
            user_id=current_user.id,
            conversation_id=conversation_id,
            user_message_id=user_msg.id,
            assistant_message_id=asst_msg.id,
            model_name=model_name,
            reasoning_mode=reasoning_mode,
            web_search=web_search,
            user_prompt=data.content,
            attachment_ids=data.attachment_ids
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.put("/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: str,
    data: MessageEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Edit user message content."""
    query = (
        select(Message)
        .options(selectinload(Message.attachments), selectinload(Message.feedback))
        .where(Message.id == message_id, Message.user_id == current_user.id)
    )
    result = await db.execute(query)
    msg = result.scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only user messages can be edited"
        )

    msg.content = data.content
    msg.is_edited = True
    msg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/{message_id}/regenerate", response_class=StreamingResponse)
async def regenerate_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate assistant response for a given message or its parent user message."""
    query = select(Message).where(Message.id == message_id, Message.user_id == current_user.id)
    result = await db.execute(query)
    target_msg = result.scalar_one_or_none()

    if not target_msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    conversation_id = target_msg.conversation_id
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if target_msg.role == "assistant":
        user_msg_q = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.created_at < target_msg.created_at,
                Message.role == "user"
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_msg_res = await db.execute(user_msg_q)
        user_msg = user_msg_res.scalar_one_or_none()
        asst_msg = target_msg
    else:
        user_msg = target_msg
        asst_msg = Message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            parent_id=user_msg.id,
            role="assistant",
            content="",
            model=conv.model_id
        )
        db.add(asst_msg)
        await db.commit()

    user_prompt = user_msg.content if user_msg else "Please summarize"
    asst_msg.content = ""
    asst_msg.reasoning_content = None
    await db.commit()

    return StreamingResponse(
        generate_chat_stream(
            user_id=current_user.id,
            conversation_id=conversation_id,
            user_message_id=user_msg.id if user_msg else asst_msg.id,
            assistant_message_id=asst_msg.id,
            model_name=conv.model_id or settings.DEFAULT_MODEL_ID,
            reasoning_mode=conv.reasoning_mode,
            web_search=conv.web_search_enabled,
            user_prompt=user_prompt
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.delete("/{message_id}", response_model=SimpleResponse)
async def delete_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific message."""
    query = select(Message).where(Message.id == message_id, Message.user_id == current_user.id)
    result = await db.execute(query)
    msg = result.scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    await db.delete(msg)
    await db.commit()
    return SimpleResponse(message="Message deleted successfully")
