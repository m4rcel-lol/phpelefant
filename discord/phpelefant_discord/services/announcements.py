from __future__ import annotations

from dataclasses import dataclass
import html
import json
import re
from xml.etree import ElementTree

HTML_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class FeedEntry:
    entry_id: str
    title: str
    url: str | None
    summary: str


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
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


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
        entry_id = str(raw.get("id") or raw.get("guid") or raw.get("url") or "")
        url = raw.get("url") or raw.get("external_url")
        title = clean_html(str(raw.get("title") or raw.get("name") or "New PHPelefant post"))
        summary = clean_html(str(raw.get("content") or raw.get("summary") or raw.get("body") or raw.get("text") or ""))
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
        summary = clean_html(first_text(item, ("summary", "description", "content")) or "")
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
        summary = clean_html(first_tag_text(block, "description") or first_tag_text(block, "summary") or first_tag_text(block, "content") or "")
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
