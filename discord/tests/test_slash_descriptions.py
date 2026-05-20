from __future__ import annotations

from dataclasses import dataclass, field

from phpelefant_discord.utils.slash_descriptions import apply_slash_descriptions


@dataclass
class FakeParameter:
    name: str
    description: str = "..."


@dataclass
class FakeCommand:
    name: str
    qualified_name: str
    description: str = "..."
    parameters: list[FakeParameter] = field(default_factory=list)


class FakeTree:
    def __init__(self, commands: list[FakeCommand]) -> None:
        self.commands = commands

    def walk_commands(self) -> list[FakeCommand]:
        return self.commands


def test_apply_slash_descriptions_replaces_command_and_parameter_placeholders() -> None:
    command = FakeCommand("ban", "ban", parameters=[FakeParameter("member"), FakeParameter("reason")])

    apply_slash_descriptions(FakeTree([command]))

    assert command.description == "Ban a member and log the action."
    assert command.parameters[0].description == "The server member to target."
    assert command.parameters[1].description == "Reason shown in logs and responses."


def test_apply_slash_descriptions_supports_qualified_subcommands() -> None:
    command = FakeCommand("add", "ticket add", parameters=[FakeParameter("member")])

    apply_slash_descriptions(FakeTree([command]))

    assert command.description == "Add a member to the current ticket."
