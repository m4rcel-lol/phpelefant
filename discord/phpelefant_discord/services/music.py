from __future__ import annotations

from dataclasses import dataclass
import shlex
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class SpotifyResource:
    kind: str
    resource_id: str


def parse_spotify_resource(value: str) -> SpotifyResource | None:
    parsed = urlparse(value.strip())
    if parsed.netloc.casefold() not in {"open.spotify.com", "play.spotify.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    kind = parts[0].casefold()
    if kind not in {"track", "playlist", "album"}:
        return None
    resource_id = parts[1].split("?", 1)[0].strip()
    if not resource_id:
        return None
    return SpotifyResource(kind=kind, resource_id=resource_id)


def spotify_track_query(name: str, artists: list[str]) -> str:
    artist_text = " ".join(artist for artist in artists if artist).strip()
    if artist_text:
        return f"{artist_text} - {name} audio"
    return f"{name} audio"


def normalized_headers(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    headers: dict[str, str] = {}
    for key, header_value in value.items():
        if not isinstance(key, str) or header_value is None:
            continue
        clean_key = key.replace("\r", "").replace("\n", "").strip()
        clean_value = str(header_value).replace("\r", "").replace("\n", "").strip()
        if clean_key and clean_value:
            headers[clean_key] = clean_value
    return headers or None


def ffmpeg_header_options(headers: dict[str, str] | None) -> str:
    if not headers:
        return ""
    header_blob = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    return f"-headers {shlex.quote(header_blob)}"
