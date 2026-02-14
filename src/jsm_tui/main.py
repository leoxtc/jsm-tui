from __future__ import annotations

import logging

from .api import JsmApiClient
from .app import AlertsApp
from .config import SettingsError, load_settings
from .logging_config import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    try:
        settings = load_settings()
    except SettingsError as exc:
        raise SystemExit(str(exc)) from exc

    configure_logging(settings.log_level, settings.log_file)
    logger.info("Starting JSM alerts TUI")

    client = JsmApiClient(settings)
    try:
        AlertsApp(
            client,
            refresh_interval_seconds=settings.refresh_interval_seconds,
            actor_email=settings.api_email,
        ).run()
    finally:
        logger.info("Closing JSM API client")
        client.close()


if __name__ == "__main__":
    run()
