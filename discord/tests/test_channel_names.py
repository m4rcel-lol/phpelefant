from phpelefant_discord.utils.channel_names import parse_edit_options, transform_channel_name


def test_parse_edit_options_supports_typo_alias() -> None:
    options = parse_edit_options(
        "type:channels deletechars:true deletetoindex:3 keepemojis:true "
        "surroundsymbol1:[ sourroundsymbol2:] limit:10"
    )

    assert options.target_type == "channels"
    assert options.delete_chars is True
    assert options.delete_to_index == 3
    assert options.keep_emojis is True
    assert options.surround_symbol_1 == "["
    assert options.surround_symbol_2 == "]"
    assert options.limit == 10


def test_transform_channel_name_preserves_leading_emoji_before_delete() -> None:
    options = parse_edit_options("type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:[ surroundsymbol2:]")

    assert transform_channel_name("🐘-001-general", options) == "🐘-[general]"


def test_transform_channel_name_without_emoji_preservation() -> None:
    options = parse_edit_options("type:channels deletechars:true deletetoindex:4 keepemojis:false")

    assert transform_channel_name("0001-general", options) == "general"
