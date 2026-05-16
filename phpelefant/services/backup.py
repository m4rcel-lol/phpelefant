from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.db import models

BACKUP_MODELS = [
    models.User,
    models.Chat,
    models.ChatSettings,
    models.Warning,
    models.ModerationLog,
    models.MemberActivity,
    models.ActivityDaily,
    models.BlacklistedUser,
    models.BlacklistedChat,
    models.WhitelistedUser,
    models.WhitelistedDomain,
    models.BadWord,
    models.BroadcastHistory,
    models.BotStatistic,
]


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


async def export_database_json(session: AsyncSession) -> bytes:
    payload: dict[str, list[dict[str, Any]]] = {}
    for model in BACKUP_MODELS:
        rows = await session.scalars(select(model))
        attrs = sa_inspect(model).column_attrs
        table_rows: list[dict[str, Any]] = []
        for row in rows:
            table_rows.append({attr.columns[0].name: getattr(row, attr.key) for attr in attrs})
        payload[model.__tablename__] = table_rows
    return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")
