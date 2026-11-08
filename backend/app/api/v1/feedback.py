from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.feedback import Feedback
from app.models.message import Message
from app.models.user import User
from app.schemas.auth import MessageResponse as SimpleResponse
from app.schemas.message import FeedbackResponse, MessageFeedbackRequest

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/messages/{message_id}", response_model=FeedbackResponse)
async def submit_message_feedback(
    message_id: str,
    data: MessageFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit like/dislike feedback and optional comment on an assistant message."""
    # Ensure message exists
    msg = await db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Check if feedback already exists for this user & message
    query = select(Feedback).where(
        Feedback.message_id == message_id,
        Feedback.user_id == current_user.id
    )
    res = await db.execute(query)
    feedback = res.scalar_one_or_none()

    if feedback:
        feedback.rating = data.rating
        feedback.comment = data.comment
        feedback.tags = data.tags
    else:
        feedback = Feedback(
            message_id=message_id,
            user_id=current_user.id,
            rating=data.rating,
            comment=data.comment,
            tags=data.tags
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.delete("/messages/{message_id}", response_model=SimpleResponse)
async def delete_message_feedback(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove feedback for a message."""
    query = select(Feedback).where(
        Feedback.message_id == message_id,
        Feedback.user_id == current_user.id
    )
    res = await db.execute(query)
    feedback = res.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    await db.delete(feedback)
    await db.commit()
    return SimpleResponse(message="Feedback removed")
