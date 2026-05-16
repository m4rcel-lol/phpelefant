from __future__ import annotations

import pytest

from phpelefant.services.shell import validate_shell_input


def test_validate_shell_input_allows_real_shell_command() -> None:
    assert validate_shell_input("fastfetch | head -20") == "fastfetch | head -20"


@pytest.mark.parametrize("raw", ["", "   ", "echo bad\x00value"])
def test_validate_shell_input_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_shell_input(raw)

