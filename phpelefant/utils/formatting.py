from __future__ import annotations

from phpelefant.utils.text import html_escape

TELEGRAM_MESSAGE_LIMIT = 4096


def code_block(value: str, language: str = "") -> str:
    language_attr = f' class="language-{html_escape(language)}"' if language else ""
    return f"<pre><code{language_attr}>{html_escape(value)}</code></pre>"


def panel(title: str, rows: list[tuple[str, str | int | bool | None]]) -> str:
    width = max((len(label) for label, _ in rows), default=0)
    body = "\n".join(f"{label.ljust(width)} : {'' if value is None else value}" for label, value in rows)
    return f"<b>{html_escape(title)}</b>\n{code_block(body)}"


def truncate_for_code_block(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = "\n... output truncated ..."
    return value[: max(0, limit - len(suffix))] + suffix, True

