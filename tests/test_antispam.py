from __future__ import annotations

from phpelefant.db.models import ChatSettings
from phpelefant.services.antispam import AutoAction, analyze_message


def settings() -> ChatSettings:
    return ChatSettings(
        chat_id=-100,
        anti_spam_enabled=True,
        anti_link_enabled=True,
        anti_caps_enabled=True,
        anti_badword_enabled=True,
        anti_forward_enabled=True,
        mention_max=3,
        emoji_max_ratio=0.65,
        caps_min_length=8,
        caps_max_ratio=0.7,
        flood_max_messages=5,
        repeat_max=3,
    )


def test_invite_link_is_muted() -> None:
    decision = analyze_message(
        text="join t.me/+abcdef",
        settings=settings(),
        bad_word_list=[],
        trusted_domains=set(),
        flood_count=1,
        repeat_count=1,
        forwarded=False,
    )
    assert decision.action is AutoAction.MUTE


def test_whitelisted_domain_allows_link() -> None:
    decision = analyze_message(
        text="read https://example.com/post",
        settings=settings(),
        bad_word_list=[],
        trusted_domains={"example.com"},
        flood_count=1,
        repeat_count=1,
        forwarded=False,
    )
    assert decision.action is AutoAction.NONE


def test_bad_word_warns() -> None:
    decision = analyze_message(
        text="this contains bannedword",
        settings=settings(),
        bad_word_list=["bannedword"],
        trusted_domains=set(),
        flood_count=1,
        repeat_count=1,
        forwarded=False,
    )
    assert decision.action is AutoAction.WARN

