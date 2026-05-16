from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message, TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_events: int = 8, window_seconds: int = 5) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._events: dict[tuple[int, int], deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)
        key = (event.chat.id, event.from_user.id)
        now = datetime.now().timestamp()
        bucket = self._events[key]
        bucket.append(now)
        while bucket and now - bucket[0] > self._window_seconds:
            bucket.popleft()
        if len(bucket) > self._max_events:
            if event.chat.type == "private":
                await event.answer("Slow down before sending more commands.")
            return None
        return await handler(event, data)

