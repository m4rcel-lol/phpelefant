from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from phpelefant.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reputation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatSettings(Base):
    __tablename__ = "chat_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), primary_key=True)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    welcome_text: Mapped[str] = mapped_column(Text, default="Welcome {user} to {group}!")
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    goodbye_text: Mapped[str] = mapped_column(Text, default="Goodbye {user}.")
    rules_text: Mapped[str] = mapped_column(Text, default="Be respectful, avoid spam, and follow Telegram Terms of Service.")
    warning_limit: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    warn_limit_action: Mapped[str] = mapped_column(String(16), default="mute", server_default="mute")
    warn_limit_mute_minutes: Mapped[int] = mapped_column(Integer, default=1440, server_default="1440")
    anti_spam_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_link_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_caps_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_badword_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_forward_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    activity_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fun_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    force_subscribe_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    verification_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    delete_service_messages: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    flood_window_seconds: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    flood_max_messages: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    repeat_max: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    mention_max: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    emoji_max_ratio: Mapped[float] = mapped_column(Float, default=0.65, server_default="0.65")
    caps_min_length: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    caps_max_ratio: Mapped[float] = mapped_column(Float, default=0.75, server_default="0.75")
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    official_channel_id: Mapped[int] = mapped_column(BigInteger, default=-1003908421427, server_default="-1003908421427")
    language: Mapped[str] = mapped_column(String(12), default="en", server_default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemberActivity(Base):
    __tablename__ = "member_activity"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_member_activity_chat_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_xp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityDaily(Base):
    __tablename__ = "activity_daily"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", "day", name="uq_activity_daily_chat_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    day: Mapped[date] = mapped_column(Date)
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class BlacklistedUser(TimestampMixin, Base):
    __tablename__ = "blacklisted_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger)


class BlacklistedChat(TimestampMixin, Base):
    __tablename__ = "blacklisted_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger)


class WhitelistedUser(Base):
    __tablename__ = "whitelisted_users"
    __table_args__ = (UniqueConstraint("chat_id", "user_id", name="uq_whitelisted_users_chat_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhitelistedDomain(Base):
    __tablename__ = "whitelisted_domains"
    __table_args__ = (UniqueConstraint("chat_id", "domain", name="uq_whitelisted_domains_chat_domain"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    domain: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BadWord(Base):
    __tablename__ = "bad_words"
    __table_args__ = (UniqueConstraint("chat_id", "word", name="uq_bad_words_chat_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    word: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BroadcastHistory(Base):
    __tablename__ = "broadcast_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(BigInteger)
    target: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotStatistic(Base):
    __tablename__ = "bot_statistics"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

