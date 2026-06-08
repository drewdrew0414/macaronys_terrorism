from __future__ import annotations

from macaronys_backend.services.discord_service import (
    default_class_label,
    parse_class_key,
)
from macaronys_backend.discord_bot import (
    autocomplete_choice_name,
    configured_class_choices,
    parse_member_ids,
)


def test_parse_class_key_for_grade_and_room() -> None:
    assert parse_class_key("2-3") == (2, 3)
    assert default_class_label("2-3") == "2학년 3반"


def test_parse_class_key_returns_none_for_custom_key() -> None:
    assert parse_class_key("console") == (None, None)
    assert default_class_label("console") == "console"


def test_parse_member_ids_from_mentions_and_plain_ids() -> None:
    raw = "<@123456789012345678> 987654321098765432, <@!123456789012345678>"

    assert parse_member_ids(raw) == [123456789012345678, 987654321098765432]


def test_autocomplete_choice_name_stays_within_discord_limit() -> None:
    name = autocomplete_choice_name("a" * 120, max_length=100)

    assert len(name) == 100
    assert name.endswith("...")


def test_configured_class_choices_use_config_json_when_db_is_empty() -> None:
    choices = configured_class_choices("2-")

    assert choices
    assert all(choice.value.startswith("2-") for choice in choices)
