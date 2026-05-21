from __future__ import annotations

from phpelefant_discord.services.announcements import feed_url_candidates, parse_feed_payload


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


def test_parse_pleroma_plain_text_content() -> None:
    payload = '[{"id":"1","uri":"https://akkoma.test/objects/1","pleroma":{"content":{"text/plain":"Plain update"}}}]'

    entries = parse_feed_payload(payload, "application/json")

    assert len(entries) == 1
    assert entries[0].summary == "Plain update"
    assert entries[0].url == "https://akkoma.test/objects/1"


def test_fediverse_profile_generates_atom_candidate_first() -> None:
    candidates = feed_url_candidates("https://social.european-commission-europa.eu/m5rcel")

    assert candidates[0].url == "https://social.european-commission-europa.eu/users/m5rcel/feed.atom"


def test_x_profile_generates_rsshub_candidate_first() -> None:
    candidates = feed_url_candidates("https://x.com/m5rcode", "https://rsshub.example")

    assert candidates[0].url == "https://rsshub.example/twitter/user/m5rcode"
