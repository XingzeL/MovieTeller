from __future__ import annotations

from movieteller_config.schema import settings_from_dict


def test_capability_timeout_and_retries_from_yaml_keys() -> None:
    settings = settings_from_dict(
        {
            "capability_timeouts": {"tts": 180, "embedding": 60},
            "capability_retries": {"tts": 3, "embedding": 4},
        }
    )
    assert settings.capability_timeout_sec("tts") == 180.0
    assert settings.capability_timeout_sec("embedding") == 60.0
    assert settings.capability_max_attempts("tts") == 3
    assert settings.capability_max_attempts("embedding") == 4


def test_capability_policy_defaults_when_key_missing() -> None:
    settings = settings_from_dict({})
    assert settings.capability_timeout_sec("tts") is None
    assert settings.capability_max_attempts("tts", default=2) == 2
