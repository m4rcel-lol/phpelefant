from __future__ import annotations

from datetime import timedelta

import pytest

from phpelefant.utils.time import parse_duration


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("10m", timedelta(minutes=10)), ("1h", timedelta(hours=1)), ("1d", timedelta(days=1)), ("7d", timedelta(days=7))],
)
def test_parse_duration_valid(raw: str, expected: timedelta) -> None:
    assert parse_duration(raw) == expected


@pytest.mark.parametrize("raw", ["0m", "10", "abc", "1y", "-1h"])
def test_parse_duration_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(raw)

