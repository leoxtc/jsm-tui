from __future__ import annotations

import logging

import httpx
import pytest

from jsm_tui.api import ApiError, JsmApiClient
from jsm_tui.config import Settings


def _settings(*, log_http_body: bool = False) -> Settings:
    return Settings(
        cloud_id="cloud-1",
        api_email=None,
        api_token=None,
        bearer_token="token",
        page_size=100,
        refresh_interval_seconds=30,
        log_level="INFO",
        log_file="logs/test.log",
        log_http_body=log_http_body,
    )


def test_http_error_logs_status_with_hidden_body(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "oops"}, request=request)

    transport = httpx.MockTransport(handler)
    client = JsmApiClient(_settings(log_http_body=False))
    original_client = client._client
    client._client = httpx.Client(
        base_url=client._client.base_url,
        transport=transport,
        timeout=5.0,
        headers=client._client.headers,
    )
    original_client.close()

    with caplog.at_level(logging.ERROR, logger="jsm_tui.api"), pytest.raises(
        ApiError, match="500: <hidden>"
    ):
        client.list_open_alerts()

    assert "JSM HTTP error GET /v1/alerts status=500" in caplog.text
    assert "body=<hidden>" in caplog.text
    client.close()


def test_get_alert_accepts_top_level_alert_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "alert-1", "status": "open", "message": "test"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = JsmApiClient(_settings())
    original_client = client._client
    client._client = httpx.Client(
        base_url=client._client.base_url,
        transport=transport,
        timeout=5.0,
        headers=client._client.headers,
    )
    original_client.close()

    alert = client.get_alert("alert-1")

    assert alert.id == "alert-1"
    assert alert.message == "test"
    client.close()


def test_get_alert_accepts_wrapped_data_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"id": "alert-2", "status": "open", "message": "wrapped"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    client = JsmApiClient(_settings())
    original_client = client._client
    client._client = httpx.Client(
        base_url=client._client.base_url,
        transport=transport,
        timeout=5.0,
        headers=client._client.headers,
    )
    original_client.close()

    alert = client.get_alert("alert-2")

    assert alert.id == "alert-2"
    assert alert.message == "wrapped"
    client.close()
