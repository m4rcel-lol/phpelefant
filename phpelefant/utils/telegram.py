from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

T = TypeVar("T")
logger = logging.getLogger(__name__)


async def telegram_call(action: Callable[[], Awaitable[T]], public_error: str = "Telegram rejected that action.") -> tuple[bool, T | str]:
    try:
        return True, await action()
    except TelegramRetryAfter as exc:
        logger.warning("Telegram rate limit: retry after %s seconds", exc.retry_after)
        return False, f"Telegram rate limit hit. Retry after {exc.retry_after} seconds."
    except TelegramAPIError as exc:
        logger.info("Telegram API error: %s", exc)
        return False, public_error

