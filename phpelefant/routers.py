from __future__ import annotations

from aiogram import Router

from phpelefant.handlers import activity, common, fun, moderation, owner, settings, welcome


def build_router() -> Router:
    router = Router(name="phpelefant")
    router.include_router(owner.router)
    router.include_router(common.router)
    router.include_router(moderation.router)
    router.include_router(settings.router)
    router.include_router(welcome.router)
    router.include_router(fun.router)
    router.include_router(activity.router)
    return router

