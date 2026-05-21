from __future__ import annotations

import shlex

from phpelefant_discord.services.music import ffmpeg_header_options, normalized_headers, parse_spotify_resource, spotify_track_query


def test_parse_spotify_track_url() -> None:
    resource = parse_spotify_resource("https://open.spotify.com/track/abc123?si=value")

    assert resource is not None
    assert resource.kind == "track"
    assert resource.resource_id == "abc123"


def test_parse_spotify_rejects_non_spotify() -> None:
    assert parse_spotify_resource("https://example.com/track/abc123") is None


def test_spotify_track_query_includes_artists() -> None:
    assert spotify_track_query("Song", ["Artist One", "Artist Two"]) == "Artist One Artist Two - Song audio"


def test_normalized_headers_removes_newlines() -> None:
    headers = normalized_headers({"User-Agent\n": "PHPelefant\r\n", "Empty": ""})

    assert headers == {"User-Agent": "PHPelefant"}


def test_ffmpeg_header_options_uses_single_quoted_argument() -> None:
    option = ffmpeg_header_options({"User-Agent": "PHPelefant", "Referer": "https://soundcloud.com/"})
    parts = shlex.split(option)

    assert parts[0] == "-headers"
    assert "User-Agent: PHPelefant\r\n" in parts[1]
    assert "Referer: https://soundcloud.com/\r\n" in parts[1]
