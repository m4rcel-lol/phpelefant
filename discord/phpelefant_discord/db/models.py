from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from phpelefant_discord.db.base import Base


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reputation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Guild(Base):
    __tablename__ = "guilds"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    owner_id: Mapped[int | None] = mapped_column(BigInteger)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    welcome_text: Mapped[str] = mapped_column(Text, default="Welcome {user} to {server}!")
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    goodbye_text: Mapped[str] = mapped_column(Text, default="Goodbye {user}.")
    rules_text: Mapped[str] = mapped_column(Text, default="Be respectful, avoid spam, and follow Discord Terms of Service.")
    warning_limit: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    warn_limit_action: Mapped[str] = mapped_column(String(16), default="timeout", server_default="timeout")
    warn_limit_timeout_minutes: Mapped[int] = mapped_column(Integer, default=1440, server_default="1440")
    anti_spam_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_link_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_caps_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    anti_badword_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    activity_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fun_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    force_subscribe_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    flood_window_seconds: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    flood_max_messages: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    repeat_max: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    mention_max: Mapped[int] = mapped_column(Integer, default=8, server_default="8")
    emoji_max_ratio: Mapped[float] = mapped_column(Float, default=0.65, server_default="0.65")
    caps_min_length: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    caps_max_ratio: Mapped[float] = mapped_column(Float, default=0.75, server_default="0.75")
    welcome_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    goodbye_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    official_channel_id: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    language: Mapped[str] = mapped_column(String(12), default="en", server_default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemberActivity(Base):
    __tablename__ = "member_activity"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_member_activity_guild_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_xp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityDaily(Base):
    __tablename__ = "activity_daily"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", "day", name="uq_activity_daily_guild_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    day: Mapped[date] = mapped_column(Date)
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class BlacklistedUser(Base):
    __tablename__ = "blacklisted_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BlacklistedGuild(Base):
    __tablename__ = "blacklisted_guilds"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShellAllowedUser(Base):
    __tablename__ = "shell_allowed_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_by: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhitelistedUser(Base):
    __tablename__ = "whitelisted_users"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", name="uq_whitelisted_users_guild_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhitelistedDomain(Base):
    __tablename__ = "whitelisted_domains"
    __table_args__ = (UniqueConstraint("guild_id", "domain", name="uq_whitelisted_domains_guild_domain"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    domain: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BadWord(Base):
    __tablename__ = "bad_words"
    __table_args__ = (UniqueConstraint("guild_id", "word", name="uq_bad_words_guild_word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
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


class TicketConfig(Base):
    __tablename__ = "ticket_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    category_id: Mapped[int | None] = mapped_column(BigInteger)
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    staff_role_id: Mapped[int | None] = mapped_column(BigInteger)
    panel_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    panel_message_id: Mapped[int | None] = mapped_column(BigInteger)
    ticket_categories: Mapped[str] = mapped_column(
        Text,
        default="General Support|Billing|Bug Report|Staff Report|Appeal",
        server_default="General Support|Billing|Bug Report|Staff Report|Appeal",
    )
    ticket_counter: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    transcript_limit: Mapped[int] = mapped_column(Integer, default=300, server_default="300")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("guild_id", "ticket_number", name="uq_tickets_guild_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ticket_number: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    opener_id: Mapped[int] = mapped_column(BigInteger, index=True)
    claimed_by_id: Mapped[int | None] = mapped_column(BigInteger)
    closed_by_id: Mapped[int | None] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(64), default="General Support", server_default="General Support")
    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open", index=True)
    subject: Mapped[str] = mapped_column(Text, default="No reason provided")
    close_reason: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
