from __future__ import annotations

import pytest

from phpelefant.services.shell import parse_shell_command


def test_parse_shell_command_allows_read_only_command() -> None:
    assert parse_shell_command("ls -la") == ["ls", "-la"]


def test_parse_shell_command_allows_fastfetch() -> None:
    assert parse_shell_command("fastfetch --version") == ["fastfetch", "--version"]


@pytest.mark.parametrize("raw", ["rm -rf /tmp/x", "python -c 'print(1)'", "/bin/ls"])
def test_parse_shell_command_rejects_unapproved_commands(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_shell_command(raw)


@pytest.mark.parametrize("raw", ["ls | head", "cat .env > out", "echo $(whoami)"])
def test_parse_shell_command_rejects_shell_operators(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_shell_command(raw)


@pytest.mark.parametrize("raw", ["find . -delete", "find . -exec ls ;", "sed -i s/a/b/g file.txt"])
def test_parse_shell_command_rejects_write_capable_flags(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_shell_command(raw)
