from __future__ import annotations

import logging
from dataclasses import dataclass
from os import getenv


@dataclass(slots=True)
class Settings:
    cloud_id: str
    api_email: str | None
    api_token: str | None
    bearer_token: str | None
    page_size: int
    refresh_interval_seconds: int
    log_level: str
    log_file: str
    log_http_body: bool

    @property
    def base_url(self) -> str:
        return f"https://api.atlassian.com/jsm/ops/api/{self.cloud_id}"


class SettingsError(RuntimeError):
    pass


def load_settings() -> Settings:
    cloud_id = _required("JSM_CLOUD_ID")
    api_email = getenv("JSM_API_EMAIL")
    api_token = getenv("JSM_API_TOKEN")
    bearer_token = getenv("JSM_BEARER_TOKEN")
    page_size_raw = getenv("JSM_PAGE_SIZE", "100")
    refresh_interval_raw = getenv("JSM_REFRESH_INTERVAL_SECONDS", "30")
    log_level_raw = getenv("JSM_LOG_LEVEL", "INFO")
    log_file = getenv("JSM_LOG_FILE", "logs/jsm-tui.log")
    log_http_body_raw = getenv("JSM_LOG_HTTP_BODY", "false")

    if not bearer_token and not (api_email and api_token):
        raise SettingsError(
            "Authentication is required. Set JSM_BEARER_TOKEN or JSM_API_EMAIL + JSM_API_TOKEN."
        )

    try:
        page_size = int(page_size_raw)
    except ValueError as exc:
        raise SettingsError("JSM_PAGE_SIZE must be an integer") from exc

    if page_size < 1 or page_size > 500:
        raise SettingsError("JSM_PAGE_SIZE must be between 1 and 500")

    try:
        refresh_interval_seconds = int(refresh_interval_raw)
    except ValueError as exc:
        raise SettingsError("JSM_REFRESH_INTERVAL_SECONDS must be an integer") from exc

    if refresh_interval_seconds < 1:
        raise SettingsError("JSM_REFRESH_INTERVAL_SECONDS must be >= 1")

    log_level = log_level_raw.upper()
    if log_level not in logging.getLevelNamesMapping():
        raise SettingsError("JSM_LOG_LEVEL must be a valid logging level name")

    return Settings(
        cloud_id=cloud_id,
        api_email=api_email,
        api_token=api_token,
        bearer_token=bearer_token,
        page_size=page_size,
        refresh_interval_seconds=refresh_interval_seconds,
        log_level=log_level,
        log_file=log_file,
        log_http_body=_parse_bool("JSM_LOG_HTTP_BODY", log_http_body_raw),
    )


def _required(name: str) -> str:
    value = getenv(name)
    if not value:
        raise SettingsError(f"Missing required environment variable: {name}")
    return value


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{name} must be a boolean (true/false)")
