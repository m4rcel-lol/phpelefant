from __future__ import annotations

from phpelefant_discord.services.activity import level_for_xp, xp_required_for_level


def test_level_boundaries() -> None:
    assert level_for_xp(0) == 0
    assert level_for_xp(xp_required_for_level(1) - 1) == 0
    assert level_for_xp(xp_required_for_level(1)) == 1
    assert level_for_xp(xp_required_for_level(2)) == 2

