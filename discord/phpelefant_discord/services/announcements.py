from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from urllib.parse import quote, urljoin, urlparse, urlunparse
from xml.etree import ElementTree

HTML_RE = re.compile(r"<[^>]+>")
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", flags=re.IGNORECASE)
HTML_ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*([\"'])(.*?)\2", flags=re.DOTALL)
X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
FEDIVERSE_PROFILE_IGNORED_SEGMENTS = {"about", "api", "auth", "emoji", "instance", "main", "nodeinfo", "oauth", "settings"}


@dataclass(slots=True)
class FeedEntry:
    entry_id: str
    title: str
    url: str | None
    summary: str


@dataclass(frozen=True, slots=True)
class FeedCandidate:
    url: str
    label: str


def clean_html(value: str | None) -> str:
    text = HTML_RE.sub("", value or "")
    return html.unescape(text).strip()


def first_text(element: ElementTree.Element, names: tuple[str, ...]) -> str | None:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    for child in element:
        short = child.tag.rsplit("}", 1)[-1]
        if short in names and child.text:
            return child.text.strip()
    return None


def first_link(element: ElementTree.Element) -> str | None:
    direct = first_text(element, ("link",))
    if direct and direct.startswith("http"):
        return direct
    fallback: str | None = None
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == "link":
            href = child.attrib.get("href")
            if not href:
                continue
            rel = child.attrib.get("rel", "alternate").casefold()
            if rel == "alternate":
                return href
            fallback = fallback or href
    return fallback


def normalize_feed_input(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    parsed = urlparse(text)
    if parsed.scheme:
        return text
    return f"https://{text}"


def feed_url_candidates(value: str, rsshub_base_url: str | None = "https://rsshub.app") -> list[FeedCandidate]:
    url = normalize_feed_input(value)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []

    candidates: list[FeedCandidate] = []
    host = parsed.netloc.casefold()
    segments = [segment for segment in parsed.path.split("/") if segment]
    suffix = parsed.path.casefold()

    if host in X_HOSTS:
        username = x_profile_username(segments)
        if username and rsshub_base_url:
            candidates.append(FeedCandidate(f"{rsshub_base_url.rstrip('/')}/twitter/user/{quote(username)}", "RSSHub X/Twitter user feed"))

    if host not in X_HOSTS and not suffix.endswith((".rss", ".atom", ".xml", ".json")):
        candidates.extend(fediverse_candidates(parsed, segments))

    candidates.append(FeedCandidate(url, "Original URL"))
    return dedupe_candidates(candidates)


def x_profile_username(segments: list[str]) -> str | None:
    if len(segments) != 1:
        return None
    username = segments[0].strip("@")
    if not username or username.casefold() in {"home", "i", "intent", "search", "share"}:
        return None
    return username


def fediverse_candidates(parsed, segments: list[str]) -> list[FeedCandidate]:
    if not segments:
        return []
    if segments[0].casefold() in FEDIVERSE_PROFILE_IGNORED_SEGMENTS:
        return []

    base = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    username: str | None = None
    if len(segments) == 1:
        username = segments[0].strip("@")
    elif len(segments) >= 2 and segments[0].casefold() == "users":
        username = segments[1].strip("@")
    if not username:
        return []

    quoted = quote(username)
    return [
        FeedCandidate(f"{base}/users/{quoted}/feed.atom", "Fediverse Atom feed"),
        FeedCandidate(f"{base}/users/{quoted}.rss", "Fediverse RSS feed"),
        FeedCandidate(f"{base}/@{quoted}.rss", "Mastodon profile RSS feed"),
        FeedCandidate(urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + ".rss", "", "", "")), "Profile RSS feed"),
    ]


def dedupe_candidates(candidates: list[FeedCandidate]) -> list[FeedCandidate]:
    seen: set[str] = set()
    unique: list[FeedCandidate] = []
    for candidate in candidates:
        if not candidate.url or candidate.url in seen:
            continue
        seen.add(candidate.url)
        unique.append(candidate)
    return unique


def discover_feed_links(base_url: str, text: str) -> list[FeedCandidate]:
    candidates: list[FeedCandidate] = []
    for tag in LINK_TAG_RE.findall(text):
        attrs = {match.group(1).casefold(): html.unescape(match.group(3).strip()) for match in HTML_ATTR_RE.finditer(tag)}
        href = attrs.get("href")
        if not href:
            continue
        rel = attrs.get("rel", "")
        media_type = attrs.get("type", "")
        if "alternate" not in rel.casefold():
            continue
        if not is_feed_media_type(media_type) and not href.casefold().endswith((".rss", ".atom", ".xml", ".json")):
            continue
        candidates.append(FeedCandidate(urljoin(base_url, href), "Discovered feed link"))
    return dedupe_candidates(candidates)


def is_feed_media_type(content_type: str) -> bool:
    lowered = content_type.casefold()
    return any(marker in lowered for marker in ("activity+json", "atom", "json", "rss", "xml"))


def looks_like_feed_payload(text: str, content_type: str) -> bool:
    if is_feed_media_type(content_type):
        return True
    stripped = text.lstrip()[:128].casefold()
    return stripped.startswith(("<?xml", "<feed", "<rss", "{", "["))


def feed_display_name(url: str) -> str:
    parsed = urlparse(normalize_feed_input(url))
    host = parsed.netloc.removeprefix("www.")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if parsed.netloc.casefold() in X_HOSTS:
        username = x_profile_username(segments)
        return f"X @{username}" if username else "X Feed"
    if segments:
        username = segments[-1]
        if username == "feed.atom" and len(segments) >= 2:
            username = segments[-2]
        username = username.removesuffix(".rss").removesuffix(".atom").strip("@")
        if username:
            return f"{host} / {username}"[:120]
    return host[:120] or "PHPelefant Feed"


def parse_json_feed(payload: object) -> list[FeedEntry]:
    if isinstance(payload, dict):
        raw_entries = payload.get("items") or payload.get("data") or payload.get("statuses") or []
    elif isinstance(payload, list):
        raw_entries = payload
    else:
        return []
    entries: list[FeedEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        entry_id = str(raw.get("id") or raw.get("guid") or raw.get("uri") or raw.get("url") or "")
        url = raw.get("url") or raw.get("external_url") or raw.get("uri")
        account = raw.get("account") if isinstance(raw.get("account"), dict) else {}
        title = clean_html(str(raw.get("title") or raw.get("name") or account.get("display_name") or account.get("username") or "New PHPelefant post"))
        pleroma = raw.get("pleroma") if isinstance(raw.get("pleroma"), dict) else {}
        plain_content = pleroma.get("content", {}).get("text/plain") if isinstance(pleroma.get("content"), dict) else None
        summary = clean_html(str(raw.get("content") or raw.get("summary") or raw.get("body") or raw.get("text") or plain_content or ""))
        if entry_id:
            entries.append(FeedEntry(entry_id=entry_id, title=title[:256], url=url if isinstance(url, str) else None, summary=summary[:1200]))
    return entries


def parse_xml_feed(text: str) -> list[FeedEntry]:
    try:
        root = ElementTree.fromstring(text)
    except (ElementTree.ParseError, ImportError):
        return parse_xml_feed_fallback(text)
    entries: list[FeedEntry] = []
    candidates = [
        child
        for child in root.iter()
        if child.tag.rsplit("}", 1)[-1] in {"item", "entry"}
    ]
    for item in candidates:
        entry_id = first_text(item, ("id", "guid")) or first_link(item) or ""
        title = clean_html(first_text(item, ("title",)) or "New PHPelefant post")
        summary = clean_html(first_text(item, ("summary", "description", "content", "encoded")) or "")
        url = first_link(item)
        if entry_id:
            entries.append(FeedEntry(entry_id=entry_id, title=title[:256], url=url, summary=summary[:1200]))
    return entries


def parse_xml_feed_fallback(text: str) -> list[FeedEntry]:
    entries: list[FeedEntry] = []
    for match in re.finditer(r"<(item|entry)\b[^>]*>(.*?)</\1>", text, flags=re.IGNORECASE | re.DOTALL):
        block = match.group(2)
        title = clean_html(first_tag_text(block, "title") or "New PHPelefant post")
        entry_id = first_tag_text(block, "guid") or first_tag_text(block, "id") or first_xml_link(block) or ""
        summary = clean_html(first_tag_text(block, "description") or first_tag_text(block, "summary") or first_tag_text(block, "encoded") or first_tag_text(block, "content") or "")
        url = first_xml_link(block)
        if entry_id:
            entries.append(FeedEntry(entry_id=entry_id, title=title[:256], url=url, summary=summary[:1200]))
    return entries


def first_tag_text(block: str, tag: str) -> str | None:
    match = re.search(rf"<(?:[a-z0-9_]+:)?{tag}\b[^>]*>(.*?)</(?:[a-z0-9_]+:)?{tag}>", block, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return clean_html(match.group(1))


def first_xml_link(block: str) -> str | None:
    href = re.search(r"<(?:[a-z0-9_]+:)?link\b[^>]*href=[\"']([^\"']+)[\"'][^>]*/?>", block, flags=re.IGNORECASE)
    if href:
        return html.unescape(href.group(1).strip())
    return first_tag_text(block, "link")


def parse_feed_payload(text: str, content_type: str = "") -> list[FeedEntry]:
    if "json" in content_type:
        try:
            return parse_json_feed(json.loads(text))
        except json.JSONDecodeError:
            return []
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return parse_json_feed(json.loads(text))
        except json.JSONDecodeError:
            return []
    return parse_xml_feed(text)
