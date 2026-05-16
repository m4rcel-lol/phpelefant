from __future__ import annotations

import pytest

from phpelefant_discord.services.shell import validate_shell_input


def test_validate_shell_input_allows_real_shell() -> None:
    assert validate_shell_input("fastfetch | head -40") == "fastfetch | head -40"


@pytest.mark.parametrize("raw", ["", "   ", "echo bad\x00value"])
def test_validate_shell_input_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_shell_input(raw)

