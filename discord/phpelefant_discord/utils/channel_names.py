from __future__ import annotations

from dataclasses import dataclass
import re
import shlex
import unicodedata


VALID_EDIT_TYPES = {"channels", "categories", "all", "text", "voice", "stage", "forum"}
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}
CUSTOM_EMOJI_RE = re.compile(r"^<a?:[A-Za-z0-9_]{2,32}:[0-9]{15,25}>")
TRIM_AFTER_DELETE = " -_|:./\\"


@dataclass(slots=True)
class ChannelEditOptions:
    target_type: str = "channels"
    delete_chars: bool = False
    delete_to_index: int = 0
    keep_emojis: bool = True
    surround_symbol_1: str = ""
    surround_symbol_2: str = ""
    match: str | None = None
    limit: int = 50
    preview: bool = False


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"Expected a boolean value, got {value!r}.")


def parse_edit_options(raw: str) -> ChannelEditOptions:
    values: dict[str, str] = {}
    for token in shlex.split(raw):
        if ":" not in token:
            raise ValueError(f"Invalid option {token!r}; use key:value.")
        key, value = token.split(":", 1)
        values[key.strip().casefold()] = value.strip()

    target_type = values.get("type", values.get("target", "channels")).casefold()
    if target_type not in VALID_EDIT_TYPES:
        raise ValueError(f"type must be one of: {', '.join(sorted(VALID_EDIT_TYPES))}.")

    try:
        delete_to_index = int(values.get("deletetoindex", values.get("delete_to_index", "0")))
        limit = int(values.get("limit", "50"))
    except ValueError as exc:
        raise ValueError("deletetoindex and limit must be integers.") from exc

    if not 0 <= delete_to_index <= 64:
        raise ValueError("deletetoindex must be between 0 and 64.")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")

    symbol_2 = values.get("surroundsymbol2", values.get("sourroundsymbol2", ""))
    match = values.get("match") or None

    return ChannelEditOptions(
        target_type=target_type,
        delete_chars=parse_bool(values.get("deletechars", "false")),
        delete_to_index=delete_to_index,
        keep_emojis=parse_bool(values.get("keepemojis", "true")),
        surround_symbol_1=values.get("surroundsymbol1", ""),
        surround_symbol_2=symbol_2,
        match=match.casefold() if match else None,
        limit=limit,
        preview=parse_bool(values.get("preview", "false")),
    )


def is_unicode_emoji_char(char: str) -> bool:
    codepoint = ord(char)
    if 0x1F000 <= codepoint <= 0x1FAFF:
        return True
    if 0x2600 <= codepoint <= 0x27BF:
        return True
    return unicodedata.category(char) == "So"


def split_leading_emojis(value: str) -> tuple[str, str]:
    prefix = ""
    rest = value
    consumed_emoji = False
    while rest:
        custom = CUSTOM_EMOJI_RE.match(rest)
        if custom:
            prefix += custom.group(0)
            rest = rest[custom.end() :]
            consumed_emoji = True
            continue
        char = rest[0]
        if is_unicode_emoji_char(char) or char in {"\ufe0f", "\u200d"}:
            prefix += char
            rest = rest[1:]
            consumed_emoji = True
            continue
        if consumed_emoji and char in {" ", "-", "_", "|", ":", "・", "•", "·"}:
            prefix += char
            rest = rest[1:]
            continue
        break
    return prefix, rest


def transform_channel_name(name: str, options: ChannelEditOptions) -> str:
    prefix = ""
    body = name.strip()
    if options.keep_emojis:
        prefix, body = split_leading_emojis(body)

    if options.delete_chars and options.delete_to_index:
        body = body[options.delete_to_index :]
        body = body.lstrip(TRIM_AFTER_DELETE)

    body = body.strip()
    if options.surround_symbol_1 or options.surround_symbol_2:
        body = f"{options.surround_symbol_1}{body}{options.surround_symbol_2}"

    candidate = f"{prefix}{body}".strip()
    return candidate[:100] or name[:100]
