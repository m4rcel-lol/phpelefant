from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.db.models import BadWord, ChatSettings, WhitelistedDomain, WhitelistedUser
from phpelefant.utils.text import (
    contains_invite_link,
    contains_link,
    emoji_ratio,
    extract_domains,
    mention_count,
    normalize_text,
    uppercase_ratio,
)


class AutoAction(str, Enum):
    NONE = "none"
    DELETE = "delete"
    WARN = "warn"
    MUTE = "mute"
    BAN = "ban"


@dataclass(slots=True)
class SpamDecision:
    action: AutoAction
    reason: str


class SpamMemory:
    def __init__(self) -> None:
        self._messages: dict[tuple[int, int], deque[tuple[float, str]]] = defaultdict(deque)

    def update(self, chat_id: int, user_id: int, text: str, now: datetime, window_seconds: int) -> tuple[int, int]:
        key = (chat_id, user_id)
        bucket = self._messages[key]
        timestamp = now.timestamp()
        normalized = normalize_text(text)
        bucket.append((timestamp, normalized))
        while bucket and timestamp - bucket[0][0] > window_seconds:
            bucket.popleft()
        repeats = sum(1 for _, seen in bucket if seen == normalized)
        return len(bucket), repeats


async def is_whitelisted(session: AsyncSession, chat_id: int, user_id: int) -> bool:
    row = await session.scalar(select(WhitelistedUser).where(WhitelistedUser.chat_id == chat_id, WhitelistedUser.user_id == user_id))
    return row is not None


async def bad_words(session: AsyncSession, chat_id: int) -> list[str]:
    result = await session.scalars(select(BadWord.word).where(BadWord.chat_id == chat_id))
    return [word.casefold() for word in result]


async def whitelisted_domains(session: AsyncSession, chat_id: int) -> set[str]:
    result = await session.scalars(select(WhitelistedDomain.domain).where(WhitelistedDomain.chat_id == chat_id))
    return {domain.casefold() for domain in result}


def analyze_message(
    *,
    text: str,
    settings: ChatSettings,
    bad_word_list: list[str],
    trusted_domains: set[str],
    flood_count: int,
    repeat_count: int,
    forwarded: bool,
) -> SpamDecision:
    normalized = normalize_text(text)
    domains = extract_domains(text)
    untrusted_domains = {domain for domain in domains if domain not in trusted_domains}

    if settings.anti_badword_enabled and any(word and word in normalized for word in bad_word_list):
        return SpamDecision(AutoAction.WARN, "bad word")
    if any(keyword in normalized for keyword in ("crypto giveaway", "free airdrop", "seed phrase", "wallet connect", "double your money")):
        return SpamDecision(AutoAction.BAN, "scam keywords")
    if settings.anti_link_enabled and contains_invite_link(text):
        return SpamDecision(AutoAction.MUTE, "invite link")
    if settings.anti_link_enabled and contains_link(text) and untrusted_domains:
        return SpamDecision(AutoAction.WARN, "link spam")
    if mention_count(text) > settings.mention_max:
        return SpamDecision(AutoAction.WARN, "mention spam")
    if settings.anti_caps_enabled and len(text) >= settings.caps_min_length and uppercase_ratio(text) >= settings.caps_max_ratio:
        return SpamDecision(AutoAction.DELETE, "caps spam")
    if emoji_ratio(text) >= settings.emoji_max_ratio and len(text) >= 12:
        return SpamDecision(AutoAction.DELETE, "emoji spam")
    if settings.anti_forward_enabled and forwarded:
        return SpamDecision(AutoAction.WARN, "forwarded spam")
    if settings.anti_spam_enabled and flood_count > settings.flood_max_messages:
        return SpamDecision(AutoAction.MUTE, "message flooding")
    if settings.anti_spam_enabled and repeat_count >= settings.repeat_max:
        return SpamDecision(AutoAction.WARN, "repeated messages")
    return SpamDecision(AutoAction.NONE, "")

