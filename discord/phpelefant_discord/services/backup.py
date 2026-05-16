from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.db import models

BACKUP_MODELS = [
    models.User,
    models.Guild,
    models.GuildSettings,
    models.Warning,
    models.ModerationLog,
    models.MemberActivity,
    models.ActivityDaily,
    models.BlacklistedUser,
    models.BlacklistedGuild,
    models.ShellAllowedUser,
    models.WhitelistedUser,
    models.WhitelistedDomain,
    models.BadWord,
    models.BroadcastHistory,
    models.BotStatistic,
]


def json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


async def export_database_json(session: AsyncSession) -> bytes:
    payload: dict[str, list[dict[str, Any]]] = {}
    for model in BACKUP_MODELS:
        rows = await session.scalars(select(model))
        attrs = sa_inspect(model).column_attrs
        payload[model.__tablename__] = [
            {attr.columns[0].name: getattr(row, attr.key) for attr in attrs}
            for row in rows
        ]
    return json.dumps(payload, ensure_ascii=False, indent=2, default=json_default).encode("utf-8")
