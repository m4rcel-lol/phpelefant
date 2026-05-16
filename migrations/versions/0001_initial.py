"""Initial PHPelefant schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def utcnow() -> sa.Function:
    return sa.func.now()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reputation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "chat_settings",
        sa.Column("chat_id", sa.BigInteger(), sa.ForeignKey("chats.chat_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("welcome_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("welcome_text", sa.Text(), nullable=False),
        sa.Column("goodbye_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("goodbye_text", sa.Text(), nullable=False),
        sa.Column("rules_text", sa.Text(), nullable=False),
        sa.Column("warning_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("warn_limit_action", sa.String(length=16), nullable=False, server_default="mute"),
        sa.Column("warn_limit_mute_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("anti_spam_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anti_link_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anti_caps_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anti_badword_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("anti_forward_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activity_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fun_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("force_subscribe_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delete_service_messages", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("flood_window_seconds", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("flood_max_messages", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("repeat_max", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("mention_max", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("emoji_max_ratio", sa.Float(), nullable=False, server_default="0.65"),
        sa.Column("caps_min_length", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("caps_max_ratio", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("log_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("official_channel_id", sa.BigInteger(), nullable=False, server_default="-1003908421427"),
        sa.Column("language", sa.String(length=12), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "warnings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "member_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_xp_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_member_activity_chat_user"),
    )
    op.create_table(
        "activity_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("chat_id", "user_id", "day", name="uq_activity_daily_chat_user_day"),
    )
    op.create_table(
        "blacklisted_users",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "blacklisted_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "whitelisted_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_whitelisted_users_chat_user"),
    )
    op.create_table(
        "whitelisted_domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.UniqueConstraint("chat_id", "domain", name="uq_whitelisted_domains_chat_domain"),
    )
    op.create_table(
        "bad_words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
        sa.UniqueConstraint("chat_id", "word", name="uq_bad_words_chat_word"),
    )
    op.create_table(
        "broadcast_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )
    op.create_table(
        "bot_statistics",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=utcnow()),
    )


def downgrade() -> None:
    for table in (
        "bot_statistics",
        "broadcast_history",
        "bad_words",
        "whitelisted_domains",
        "whitelisted_users",
        "blacklisted_chats",
        "blacklisted_users",
        "activity_daily",
        "member_activity",
        "moderation_logs",
        "warnings",
        "chat_settings",
        "chats",
        "users",
    ):
        op.drop_table(table)

