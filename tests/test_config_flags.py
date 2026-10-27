"""Pins on the two env readers every boot path goes through (finalisation
19-R5 / 19-R10): the layered log-level resolver and the one truthy parser."""
import logging

import pytest

from dora_api.infrastructure.profile import env_flag


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("DORA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DORA_LOG_LEVEL", raising=False)
    monkeypatch.setenv("DORA_ENV", "development")
    from dora_api.infrastructure.configuration_manager import DoraConfig
    return DoraConfig()


def test__log_level__env_wins_over_json_and_profile(config, monkeypatch):
    monkeypatch.setenv("DORA_LOG_LEVEL", "warning")
    assert config.get_log_level() == logging.WARNING


def test__log_level__legacy_json_error_means_profile_default(config):
    # The generated JSON says "ERROR"; development's profile default is DEBUG.
    assert config.get_log_level() == logging.DEBUG


def test__log_level__json_value_is_honoured_when_env_unset(config):
    config._config.LOG_LEVEL = "info"
    assert config.get_log_level() == logging.INFO


def test__log_level__unknown_name_warns_and_falls_back(config, monkeypatch, caplog):
    monkeypatch.setenv("DORA_LOG_LEVEL", "LOUD")
    with caplog.at_level(logging.WARNING):
        assert config.get_log_level() == logging.DEBUG
    assert "Unknown log level 'LOUD'" in caplog.text


@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("Yes", True), ("ON", True),
    ("0", False), ("false", False), ("off", False), ("maybe", False),
])
def test__env_flag__parses_the_four_truthy_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("DORA_TEST_FLAG", raw)
    assert env_flag("DORA_TEST_FLAG") is expected


def test__env_flag__empty_and_unset_use_the_default(monkeypatch):
    monkeypatch.delenv("DORA_TEST_FLAG", raising=False)
    assert env_flag("DORA_TEST_FLAG") is False
    assert env_flag("DORA_TEST_FLAG", default=True) is True
    monkeypatch.setenv("DORA_TEST_FLAG", "   ")
    assert env_flag("DORA_TEST_FLAG", default=True) is True
