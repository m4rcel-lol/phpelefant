from __future__ import annotations

import re
from urllib.parse import urlparse

URL_RE = re.compile(r"(https?://[^\s]+|discord\.gg/[^\s]+|www\.[^\s]+)", re.IGNORECASE)
INVITE_RE = re.compile(r"(discord\.gg/[^\s]+|discord(?:app)?\.com/invite/[^\s]+)", re.IGNORECASE)
MENTION_RE = re.compile(r"<@!?[0-9]+>|<@&[0-9]+>|@[A-Za-z0-9_.-]{2,32}")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF]+", re.UNICODE)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def contains_link(text: str) -> bool:
    return bool(URL_RE.search(text))


def contains_invite_link(text: str) -> bool:
    return bool(INVITE_RE.search(text))


def mention_count(text: str) -> int:
    return len(MENTION_RE.findall(text))


def extract_domains(text: str) -> set[str]:
    domains: set[str] = set()
    for raw in URL_RE.findall(text):
        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        if parsed.netloc:
            domains.add(parsed.netloc.lower().removeprefix("www."))
    return domains


def uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def emoji_ratio(text: str) -> float:
    if not text:
        return 0.0
    emoji_chars = sum(len(match.group(0)) for match in EMOJI_RE.finditer(text))
    return emoji_chars / len(text)

