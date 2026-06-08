from __future__ import annotations

from pathlib import Path
import json


def test_config_json_does_not_contain_env_secrets_or_secret_values() -> None:
    text = Path("config.json").read_text(encoding="utf-8")

    forbidden = [
        "WORKER_TOKEN",
        "DISCORD_BOT_TOKEN",
        "DISCORD_WEBHOOK_URL",
        "BOT_TOKEN_HERE",
        "WEBHOOK_TOKEN",
    ]

    for value in forbidden:
        assert value not in text


def test_config_json_is_discord_first_and_matches_database_tables() -> None:
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))

    assert config["run"]["default_mode"] == "all"
    assert config["discord"]["enabled"] is True
    assert config["discord"]["bot"]["autocomplete"]["enabled"] is True
    tables = set(config["backend"]["database"]["tables"])
    assert "discord_channel_mappings" in tables
    assert "discord_moderation_logs" in tables
    assert "team_projects" in tables
    assert "peer_reviews" in tables
