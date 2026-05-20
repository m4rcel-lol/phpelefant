from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from phpelefant_discord.services.activity import as_aware_utc, level_for_xp, xp_required_for_level


def test_level_boundaries() -> None:
    assert level_for_xp(0) == 0
    assert level_for_xp(xp_required_for_level(1) - 1) == 0
    assert level_for_xp(xp_required_for_level(1)) == 1
    assert level_for_xp(xp_required_for_level(2)) == 2


def test_as_aware_utc_accepts_sqlite_naive_datetime() -> None:
    naive = datetime(2026, 5, 20, 19, 59, 2)

    assert as_aware_utc(naive) == datetime(2026, 5, 20, 19, 59, 2, tzinfo=UTC)


def test_as_aware_utc_converts_existing_timezone() -> None:
    local = datetime(2026, 5, 20, 21, 59, 2, tzinfo=timezone(timedelta(hours=2)))

    assert as_aware_utc(local) == datetime(2026, 5, 20, 19, 59, 2, tzinfo=UTC)
