from __future__ import annotations

import discord
from discord.ext import commands


def owner_or_guild_permissions(**permissions: bool):
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id == ctx.bot.settings.bot_owner_id:
            return True
        if not isinstance(ctx.author, discord.Member):
            raise commands.NoPrivateMessage()
        missing = [
            permission
            for permission, expected in permissions.items()
            if getattr(ctx.author.guild_permissions, permission) != expected
        ]
        if missing:
            raise commands.MissingPermissions(missing)
        return True

    return commands.check(predicate)
