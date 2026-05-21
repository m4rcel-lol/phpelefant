from __future__ import annotations

from phpelefant_discord.services.announcements import parse_feed_payload


def test_parse_rss_feed_payload() -> None:
    payload = """<?xml version="1.0"?>
    <rss><channel><item><guid>post-1</guid><title>Hello</title>
    <link>https://example.test/post-1</link><description>Body</description></item></channel></rss>
    """

    entries = parse_feed_payload(payload, "application/rss+xml")

    assert len(entries) == 1
    assert entries[0].entry_id == "post-1"
    assert entries[0].title == "Hello"
    assert entries[0].url == "https://example.test/post-1"


def test_parse_akkoma_style_json_payload() -> None:
    payload = '[{"id":"1","url":"https://akkoma.test/notice/1","content":"<p>Update posted</p>"}]'

    entries = parse_feed_payload(payload, "application/json")

    assert len(entries) == 1
    assert entries[0].summary == "Update posted"
