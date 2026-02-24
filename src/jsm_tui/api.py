from __future__ import annotations

import logging
from pprint import pformat
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from .config import Settings
from .models import Alert

logger = logging.getLogger(__name__)


class ApiError(RuntimeError):
    pass


class JsmApiClient:
    def __init__(self, settings: Settings) -> None:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        auth: tuple[str, str] | None = None

        if settings.bearer_token:
            headers["Authorization"] = f"Bearer {settings.bearer_token}"
        else:
            if not settings.api_email or not settings.api_token:
                raise ApiError("Missing basic auth credentials")
            auth = (settings.api_email, settings.api_token)

        self._client = httpx.Client(
            base_url=settings.base_url,
            timeout=20.0,
            headers=headers,
            auth=auth,
        )
        self._page_size = settings.page_size
        self._log_http_body = settings.log_http_body
        logger.info(
            "Initialized JSM API client (base_url=%s, auth_mode=%s, page_size=%d)",
            settings.base_url,
            "bearer" if settings.bearer_token else "basic",
            settings.page_size,
        )

    def close(self) -> None:
        self._client.close()

    def list_open_alerts(self) -> list[Alert]:
        payload = self._request_json("GET", "/v1/alerts", params={"size": self._page_size})

        raw_alerts = _extract_alerts(payload)
        alerts: list[Alert] = []
        for item in raw_alerts:
            alert = Alert.from_api(item)
            logger.info(
                "Alert details id=%s priority=%s status=%s age=%s acked_by=%s tags=%s message=%s",
                alert.id,
                alert.priority,
                alert.status,
                alert.age,
                alert.acknowledged_by,
                alert.tags_display,
                _truncate_text(alert.message, max_len=250),
            )
            logger.info("Alert raw payload: %s", _truncate_text(pformat(item), max_len=4000))
            if alert.id and alert.is_open:
                alerts.append(alert)

        return sorted(alerts, key=_sort_key, reverse=True)

    def get_alert(self, alert_id: str) -> Alert:
        payload = self._request_json("GET", f"/v1/alerts/{alert_id}")
        data = _extract_single_alert(payload)
        if not data:
            logger.error(
                "Invalid alert details response format for alert_id=%s keys=%s",
                alert_id,
                sorted(payload.keys()),
            )
            raise ApiError("Invalid alert response format")
        return Alert.from_api(data)

    def acknowledge_alert(self, alert_id: str) -> None:
        self._request_json("POST", f"/v1/alerts/{alert_id}/acknowledge", json={})

    def close_alert(self, alert_id: str) -> None:
        self._request_json("POST", f"/v1/alerts/{alert_id}/close", json={})

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        start = perf_counter()
        logger.debug(
            "JSM request %s %s (params=%s, json_keys=%s)",
            method,
            path,
            _safe_params(params),
            sorted(json.keys()) if json else None,
        )
        try:
            response = self._client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            duration_ms = int((perf_counter() - start) * 1000)
            message = _truncate_text(exc.response.text.strip())
            error_body = message if self._log_http_body else "<hidden>"
            logger.error(
                "JSM HTTP error %s %s status=%d duration_ms=%d body=%s",
                method,
                path,
                exc.response.status_code,
                duration_ms,
                error_body,
            )
            raise ApiError(
                f"{method} {path} failed with {exc.response.status_code}: {error_body}"
            ) from exc
        except httpx.HTTPError as exc:
            duration_ms = int((perf_counter() - start) * 1000)
            logger.exception(
                "JSM transport error %s %s duration_ms=%d",
                method,
                path,
                duration_ms,
            )
            raise ApiError(f"{method} {path} failed: {exc}") from exc

        duration_ms = int((perf_counter() - start) * 1000)
        logger.info(
            "JSM response %s %s status=%d duration_ms=%d",
            method,
            path,
            response.status_code,
            duration_ms,
        )

        try:
            data = response.json()
        except ValueError as exc:
            logger.error(
                "JSM non-JSON response %s %s status=%d body=%s",
                method,
                path,
                response.status_code,
                _truncate_text(response.text) if self._log_http_body else "<hidden>",
            )
            raise ApiError(f"{method} {path} returned non-JSON response") from exc

        if not isinstance(data, dict):
            logger.error(
                "JSM unexpected JSON payload type %s %s type=%s",
                method,
                path,
                type(data).__name__,
            )
            raise ApiError(f"{method} {path} returned unexpected JSON payload")

        return data


def _extract_alerts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("data", "values", "alerts"):
        raw = payload.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]

    return []


def _extract_single_alert(payload: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("data", "value", "alert"):
        raw = payload.get(key)
        if isinstance(raw, dict):
            return raw

    if _looks_like_alert(payload):
        return payload

    return None


def _looks_like_alert(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("id", "tinyId", "message", "status"))


def _sort_key(alert: Alert) -> datetime:
    return alert.created_at or datetime.fromtimestamp(0, UTC)


def _safe_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    redacted = dict(params)
    for key in list(redacted.keys()):
        if "token" in key.lower() or "password" in key.lower():
            redacted[key] = "<redacted>"
    return redacted


def _truncate_text(message: str, max_len: int = 500) -> str:
    if len(message) <= max_len:
        return message
    return f"{message[:max_len]}...<truncated>"
