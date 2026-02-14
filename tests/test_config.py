import pytest

from jsm_tui.config import SettingsError, load_settings


def test_load_settings_requires_cloud_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JSM_CLOUD_ID", raising=False)
    monkeypatch.delenv("JSM_BEARER_TOKEN", raising=False)
    monkeypatch.delenv("JSM_API_EMAIL", raising=False)
    monkeypatch.delenv("JSM_API_TOKEN", raising=False)

    with pytest.raises(SettingsError):
        load_settings()


def test_load_settings_with_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JSM_CLOUD_ID", "cloud-1")
    monkeypatch.setenv("JSM_BEARER_TOKEN", "token")
    monkeypatch.delenv("JSM_API_EMAIL", raising=False)
    monkeypatch.delenv("JSM_API_TOKEN", raising=False)

    settings = load_settings()

    assert settings.cloud_id == "cloud-1"
    assert settings.bearer_token == "token"
    assert settings.refresh_interval_seconds == 30
    assert settings.log_level == "INFO"
    assert settings.log_file == "logs/jsm-tui.log"
    assert settings.log_http_body is False


def test_load_settings_with_logging_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JSM_CLOUD_ID", "cloud-1")
    monkeypatch.setenv("JSM_BEARER_TOKEN", "token")
    monkeypatch.setenv("JSM_REFRESH_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("JSM_LOG_LEVEL", "debug")
    monkeypatch.setenv("JSM_LOG_FILE", "/tmp/jsm-alerts.log")
    monkeypatch.setenv("JSM_LOG_HTTP_BODY", "true")

    settings = load_settings()

    assert settings.refresh_interval_seconds == 10
    assert settings.log_level == "DEBUG"
    assert settings.log_file == "/tmp/jsm-alerts.log"
    assert settings.log_http_body is True
