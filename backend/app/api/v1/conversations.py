from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    ConversationUpdateRequest
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationSummaryResponse])
async def list_conversations(
    archived: bool = Query(False, description="Filter by archived state"),
    search: Optional[str] = Query(None, description="Search conversation titles"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List conversations belonging exclusively to current user.
    Strict tenant isolation is guaranteed.
    """
    conditions = [
        Conversation.user_id == current_user.id,
        Conversation.is_archived == archived
    ]

    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"
        conditions.append(func.lower(Conversation.title).like(search_term))

    query = (
        select(Conversation)
        .where(*conditions)
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()

    # Build summaries with message count and preview
    summaries = []
    for conv in conversations:
        # Get count of messages
        count_q = select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        count_res = await db.execute(count_q)
        msg_count = count_res.scalar() or 0

        # Get preview of latest message
        last_msg_q = (
            select(Message.content)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg_res = await db.execute(last_msg_q)
        last_msg = last_msg_res.scalar_one_or_none()
        preview = (last_msg[:80] + "...") if last_msg and len(last_msg) > 80 else last_msg

        summaries.append(
            ConversationSummaryResponse(
                id=conv.id,
                title=conv.title,
                is_pinned=conv.is_pinned,
                is_archived=conv.is_archived,
                model_id=conv.model_id,
                project_id=conv.project_id,
                reasoning_mode=conv.reasoning_mode,
                web_search_enabled=conv.web_search_enabled,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count,
                last_message_preview=preview
            )
        )

    return summaries


@router.post("", response_model=ConversationDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation."""
    new_conv = Conversation(
        user_id=current_user.id,
        title=data.title or "New Chat",
        model_id=data.model_id or "nexora-pro",
        project_id=data.project_id,
        system_prompt=data.system_prompt,
        reasoning_mode=bool(data.reasoning_mode),
        web_search_enabled=bool(data.web_search_enabled)
    )
    db.add(new_conv)
    await db.commit()
    await db.refresh(new_conv)

    return ConversationDetailResponse(
        id=new_conv.id,
        title=new_conv.title,
        is_pinned=new_conv.is_pinned,
        is_archived=new_conv.is_archived,
        model_id=new_conv.model_id,
        project_id=new_conv.project_id,
        system_prompt=new_conv.system_prompt,
        reasoning_mode=new_conv.reasoning_mode,
        web_search_enabled=new_conv.web_search_enabled,
        created_at=new_conv.created_at,
        updated_at=new_conv.updated_at,
        messages=[]
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full conversation details and all messages with attachments & feedback."""
    query = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.attachments),
            selectinload(Conversation.messages).selectinload(Message.feedback)
        )
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )

    return conv


@router.patch("/{conversation_id}", response_model=ConversationDetailResponse)
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update conversation title, pin status, archive status, model, etc."""
    query = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.attachments),
            selectinload(Conversation.messages).selectinload(Message.feedback)
        )
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(conv, field, value)

    await db.commit()
    await db.refresh(conv)
    return conv


@router.post("/{conversation_id}/pin", response_model=ConversationDetailResponse)
async def toggle_pin_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle pin status of a conversation."""
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.is_pinned = not conv.is_pinned
    await db.commit()
    await db.refresh(conv)
    return conv


@router.post("/{conversation_id}/archive", response_model=ConversationDetailResponse)
async def toggle_archive_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle archive status of a conversation."""
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.is_archived = not conv.is_archived
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation and its messages."""
    query = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    result = await db.execute(query)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )

    await db.delete(conv)
    await db.commit()
    return MessageResponse(message="Conversation deleted successfully")
