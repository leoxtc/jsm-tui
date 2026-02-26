from jsm_tui.app import _extract_runbook_url, _linkify_urls, _status_cell, _truncate_cell


def test_status_cell_uses_green_for_acked() -> None:
    cell = _status_cell("acked")
    assert cell.style == "green"


def test_status_cell_uses_red_for_open() -> None:
    cell = _status_cell("open")
    assert cell.style == "red"


def test_linkify_urls_wraps_bare_http_links() -> None:
    text = "See https://example.com/path?x=1 for details."
    expected = "See [https://example.com/path?x=1](https://example.com/path?x=1) for details."
    assert _linkify_urls(text) == expected


def test_linkify_urls_keeps_existing_markdown_links() -> None:
    text = "See [runbook](https://example.com/runbook)."
    assert _linkify_urls(text) == text


def test_extract_runbook_url_prefers_markdown_runbook_link() -> None:
    text = "Docs: https://example.com/docs and [Runbook](https://example.com/runbook)"
    assert _extract_runbook_url(text) == "https://example.com/runbook"


def test_extract_runbook_url_from_plain_runbook_label() -> None:
    text = "Runbook: https://example.com/runbook."
    assert _extract_runbook_url(text) == "https://example.com/runbook"


def test_truncate_cell_keeps_short_values() -> None:
    assert _truncate_cell("prod", max_len=10) == "prod"


def test_truncate_cell_limits_to_max_len() -> None:
    assert _truncate_cell("payments,prod", max_len=10) == "payment..."
