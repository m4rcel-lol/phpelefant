from __future__ import annotations

from datetime import UTC, datetime
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import User
from phpelefant.services.settings import get_or_create_chat_settings
from phpelefant.services.stats import global_counts
from phpelefant.utils.text import html_escape

router = Router(name="common")
STARTED_AT = time.monotonic()


def uptime_text() -> str:
    seconds = int(time.monotonic() - STARTED_AT)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "PHPelefant is online.\n"
        "Add me to a group and grant moderation permissions to enable community management tools.\n"
        "Use /help for commands."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>PHPelefant commands</b>\n"
        "Moderation: /ban /unban /kick /mute /unmute /warn /warnings /resetwarnings /purge /delete /lock /unlock /slowmode /rules /setrules /pin /unpin /report /adminlist\n"
        "Settings: /settings /setlogchannel /setwarnlimit /antispam /antilink /anticaps /badwords /whitelist /forcesub\n"
        "Welcome: /setwelcome /welcome /setgoodbye /goodbye\n"
        "Activity: /rank /level /xp /leaderboard /top /activity /profile\n"
        "Fun: /joke /meme /quote /fact /8ball /coinflip /dice /roll /ship /roast /compliment /hug /slap /cat /dog /poll /quiz\n"
        "Utility: /about /id /userinfo /chatinfo /ping /uptime /stats /language /timezone"
    )


@router.message(Command("about"))
async def about(message: Message, settings: Settings) -> None:
    await message.answer(
        "<b>PHPelefant</b>\n"
        "Purpose: moderation, activities, and fun community tools.\n"
        f"Official channel: <code>{settings.official_channel_id}</code>"
    )


@router.message(Command("id"))
async def id_command(message: Message) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    if target is None:
        await message.answer(f"Chat ID: <code>{message.chat.id}</code>")
        return
    await message.answer(f"User ID: <code>{target.id}</code>\nChat ID: <code>{message.chat.id}</code>")


@router.message(Command("userinfo"))
async def userinfo(message: Message, session: AsyncSession) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    if target is None:
        await message.answer("No user found.")
        return
    db_user = await session.get(User, target.id)
    first_seen = db_user.first_seen_at.isoformat() if db_user else "unknown"
    await message.answer(
        f"ID: <code>{target.id}</code>\n"
        f"Username: @{html_escape(target.username) if target.username else 'none'}\n"
        f"Name: {html_escape(target.full_name)}\n"
        f"Bot: {target.is_bot}\n"
        f"First seen: {first_seen}"
    )


@router.message(Command("chatinfo"))
async def chatinfo(message: Message, bot: Bot) -> None:
    member_count = await bot.get_chat_member_count(message.chat.id)
    await message.answer(
        f"Chat ID: <code>{message.chat.id}</code>\n"
        f"Type: {message.chat.type}\n"
        f"Title: {html_escape(message.chat.title)}\n"
        f"Members: {member_count}"
    )


@router.message(Command("ping"))
async def ping(message: Message) -> None:
    started = datetime.now(tz=UTC)
    sent = await message.answer("Pong.")
    latency = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
    await sent.edit_text(f"Pong. <code>{latency} ms</code>")


@router.message(Command("uptime"))
async def uptime(message: Message) -> None:
    await message.answer(f"Uptime: <code>{uptime_text()}</code>")


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession) -> None:
    counts = await global_counts(session)
    await message.answer(
        f"Groups: <code>{counts['groups']}</code>\n"
        f"Users: <code>{counts['users']}</code>\n"
        f"Messages processed: <code>{counts['messages']}</code>\n"
        f"Moderation actions: <code>{counts['moderation_actions']}</code>"
    )


@router.message(Command("settings"))
async def show_settings(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("Settings are available in groups.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    await message.answer(
        "<b>Group settings</b>\n"
        f"Welcome: {row.welcome_enabled}\n"
        f"Goodbye: {row.goodbye_enabled}\n"
        f"Warning limit: {row.warning_limit}\n"
        f"Anti-spam: {row.anti_spam_enabled}\n"
        f"Anti-link: {row.anti_link_enabled}\n"
        f"Anti-caps: {row.anti_caps_enabled}\n"
        f"Anti-badword: {row.anti_badword_enabled}\n"
        f"Activity: {row.activity_enabled}\n"
        f"Fun: {row.fun_enabled}\n"
        f"Force-subscribe: {row.force_subscribe_enabled}\n"
        f"Log channel: {row.log_channel_id or 'not set'}\n"
        f"Language: {html_escape(row.language)}\n"
        f"Timezone: {html_escape(row.timezone)}"
    )


@router.message(Command("language"))
async def language(message: Message, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    await message.answer(f"Language: <code>{html_escape(row.language)}</code>")


@router.message(Command("timezone"))
async def timezone(message: Message, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    await message.answer(f"Timezone: <code>{html_escape(row.timezone)}</code>")

