import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )
    theme: Mapped[str] = mapped_column(String(20), default="system")  # dark, light, system
    default_model: Mapped[str] = mapped_column(String(50), default="nexora-pro")
    stream_responses: Mapped[bool] = mapped_column(Boolean, default=True)
    enter_to_send: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_mode_default: Mapped[bool] = mapped_column(Boolean, default=False)
    web_search_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="preferences")
