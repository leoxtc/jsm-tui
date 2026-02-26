from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Markdown, Static

from .api import ApiError, JsmApiClient
from .models import Alert

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlertDescription:
    alert_id: str
    title: str
    description: str
    status: str
    priority: str
    age: str
    acknowledged_by: str


class DescriptionScreen(ModalScreen[None]):
    CSS = """
    DescriptionScreen {
        align: center middle;
    }

    #detail-header {
        height: auto;
        padding-bottom: 1;
        border-bottom: solid $panel;
    }

    #detail-title {
        text-style: bold;
    }

    #detail-meta {
        color: $text-muted;
    }

    #detail-status-open {
        color: red;
        text-style: bold;
    }

    #detail-status-acked {
        color: green;
        text-style: bold;
    }

    #detail-status-other {
        color: yellow;
        text-style: bold;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("d", "dismiss", "Close"),
        ("v", "dismiss", "Close"),
        ("o", "open_runbook", "Open Runbook"),
    ]

    def __init__(self, details: AlertDescription) -> None:
        super().__init__()
        self._details = details
        self._runbook_url = _extract_runbook_url(details.description)

    def compose(self) -> ComposeResult:
        with Container(id="description-modal"):
            with Container(id="detail-header"):
                yield Static(
                    Text(f"Alert {self._details.alert_id}: {self._details.title}"),
                    id="detail-title",
                )
                yield Static(
                    (
                        f"Prio {self._details.priority}  |  Age {self._details.age}  |  "
                        f"Acked By {self._details.acknowledged_by}"
                    ),
                    id="detail-meta",
                )
                yield Static(
                    f"Status: {self._details.status.upper()}",
                    id=_status_style_id(self._details.status),
                )
            yield Markdown(_linkify_urls(self._details.description), id="description-body")
            with Horizontal(id="description-actions"):
                if self._runbook_url:
                    yield Button("Open Runbook (o)", id="description-runbook", variant="success")
                yield Button("Close (d/ESC/q)", id="description-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "description-runbook" and self._runbook_url:
            self.app.open_url(self._runbook_url)
        elif event.button.id == "description-close":
            self.dismiss()

    def action_open_runbook(self) -> None:
        if self._runbook_url:
            self.app.open_url(self._runbook_url)


class AlertsApp(App[None]):
    TITLE = "Jira Service Management Alerts"

    CSS = """
    Screen {
        layout: vertical;
        background: #1c1c1c;
    }

    Header {
        background: #00005f;
        color: #2d2d6b;
    }

    HeaderClock {
        background: #377a7a;
        color: #005f5f;
    }

    Footer {
        background: #00005f;
        color: #dadada;
    }

    Footer .footer--key {
        color: #ffaf00;
        text-style: bold;
    }

    Footer .footer--description {
        color: #dadada;
    }

    DataTable > .datatable--header {
        background: #00005f;
        color: #dadada;
    }

    DataTable > .datatable--odd-row {
        background: #101010;
    }

    DataTable > .datatable--even-row {
        background: #1c1c1c;
    }

    DataTable > .datatable--cursor {
        background: #005f5f;
        color: #dadada;
    }

    #table-container {
        height: 1fr;
        padding: 1 2;
    }

    #alerts-table {
        height: 1fr;
    }

    #description-modal {
        layout: vertical;
        width: 85%;
        max-width: 100;
        height: 75%;
        padding: 1 3;
        border: heavy $accent;
        background: $surface;
    }

    #description-body {
        overflow-y: auto;
        height: 1fr;
        border: round $panel;
        padding: 1 1;
        margin-top: 1;
    }

    #description-close {
        width: 16;
    }

    #description-runbook {
        margin-right: 2;
    }

    #description-actions {
        width: 1fr;
        align-horizontal: center;
        height: auto;
        padding-top: 1;
        border-top: solid $panel;
        margin-top: 1;
    }

    #open-alerts-count {
        height: 1;
        text-align: left;
        padding-left: 2;
        color: #9e9e9e;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("r", "refresh", "Refresh"),
        ("a", "acknowledge", "Acknowledge"),
        ("c", "close", "Close Alert"),
        ("v", "view", "View Description"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        client: JsmApiClient,
        *,
        refresh_interval_seconds: int = 30,
        actor_email: str | None = None,
    ) -> None:
        super().__init__()
        self._client = client
        self._refresh_interval_seconds = refresh_interval_seconds
        self._actor_email = actor_email
        self._alerts: dict[str, Alert] = {}
        self._row_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="table-container"):
            yield DataTable(id="alerts-table", cursor_type="row")
        yield Static("Open alerts: 0", id="open-alerts-count")
        yield Footer()

    def on_mount(self) -> None:
        table = self._table
        table.add_columns("Prio", "Status", "Age", "Acked By", "Tags", "Message")
        table.zebra_stripes = True
        self.action_refresh()
        self.set_interval(self._refresh_interval_seconds, self.action_refresh)
        logger.info("Auto-refresh enabled every %d seconds", self._refresh_interval_seconds)

    @property
    def _table(self) -> DataTable[object]:
        return self.query_one("#alerts-table", DataTable)

    def action_refresh(self) -> None:
        self._refresh_worker()

    @work(thread=True, exclusive=True)
    def _refresh_worker(self) -> None:
        logger.debug("Refreshing open alerts")
        try:
            alerts = self._client.list_open_alerts()
        except ApiError as exc:
            logger.exception("Failed to refresh open alerts")
            self.call_from_thread(self.notify, str(exc), severity="error")
            return

        logger.info("Refresh completed with %d open alerts", len(alerts))
        self.call_from_thread(self._render_alerts, alerts)

    def _render_alerts(self, alerts: list[Alert]) -> None:
        self._alerts = {alert.id: alert for alert in alerts}
        self._row_ids = [alert.id for alert in alerts]
        self._render_table_from_state()

    def _render_table_from_state(self) -> None:
        table = self._table
        table.clear()
        for alert_id in self._row_ids:
            alert = self._alerts.get(alert_id)
            if not alert:
                continue
            table.add_row(
                alert.priority,
                _status_cell(alert.status),
                alert.age,
                alert.acknowledged_by,
                _truncate_cell(alert.tags_display, max_len=10),
                Text(alert.message),
                key=alert.id,
            )
        self.query_one("#open-alerts-count", Static).update(f"Open alerts: {len(self._row_ids)}")

    def action_acknowledge(self) -> None:
        alert = self._selected_alert()
        if not alert:
            return

        previous = replace(alert)
        restore_index = self._row_ids.index(alert.id)
        self._optimistically_ack_alert(alert.id)
        self._ack_worker(alert.id, previous, restore_index)

    @work(thread=True)
    def _ack_worker(self, alert_id: str, previous: Alert, restore_index: int) -> None:
        logger.info("Acknowledging alert %s", alert_id)
        try:
            self._client.acknowledge_alert(alert_id)
        except ApiError as exc:
            logger.exception("Failed to acknowledge alert %s", alert_id)
            self.call_from_thread(self._restore_alert, previous, restore_index)
            self.call_from_thread(self.notify, str(exc), severity="error")
            return

        self.call_from_thread(self.notify, f"Acknowledged alert {alert_id}", timeout=2)

    def action_close(self) -> None:
        alert = self._selected_alert()
        if not alert:
            return

        removed = replace(alert)
        restore_index = self._row_ids.index(alert.id)
        self._optimistically_remove_alert(alert.id)
        self._close_worker(alert.id, removed, restore_index)

    @work(thread=True)
    def _close_worker(self, alert_id: str, removed: Alert, restore_index: int) -> None:
        logger.info("Closing alert %s", alert_id)
        try:
            self._client.close_alert(alert_id)
        except ApiError as exc:
            logger.exception("Failed to close alert %s", alert_id)
            self.call_from_thread(self._restore_alert, removed, restore_index)
            self.call_from_thread(self.notify, str(exc), severity="error")
            return

        self.call_from_thread(self.notify, f"Closed alert {alert_id}", timeout=2)

    def action_view(self) -> None:
        alert = self._selected_alert()
        if not alert:
            return

        self._view_worker(alert.id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "alerts-table":
            return

        alert_id = event.row_key.value
        if not alert_id and 0 <= event.cursor_row < len(self._row_ids):
            alert_id = self._row_ids[event.cursor_row]
        if not alert_id:
            self.notify("Could not resolve selected alert", severity="error")
            return

        self._view_worker(alert_id)

    @work(thread=True)
    def _view_worker(self, alert_id: str) -> None:
        logger.debug("Fetching alert details for %s", alert_id)
        try:
            alert = self._client.get_alert(alert_id)
        except ApiError as exc:
            logger.exception("Failed to fetch alert details for %s", alert_id)
            self.call_from_thread(self.notify, str(exc), severity="error")
            return

        self.call_from_thread(
            self.push_screen,
            DescriptionScreen(
                AlertDescription(
                    alert_id=alert.id,
                    title=alert.message,
                    description=alert.description,
                    status=alert.status,
                    priority=alert.priority,
                    age=alert.age,
                    acknowledged_by=alert.acknowledged_by,
                )
            ),
        )

    def _selected_alert(self) -> Alert | None:
        table = self._table
        if table.row_count == 0:
            self.notify("No alerts loaded", severity="warning")
            return None

        if table.cursor_row < 0:
            self.notify("Select an alert first", severity="warning")
            return None

        if table.cursor_row >= len(self._row_ids):
            self.notify("Select an alert first", severity="warning")
            return None

        alert_id = self._row_ids[table.cursor_row]
        alert = self._alerts.get(alert_id)
        if not alert:
            self.notify("Could not resolve selected alert", severity="error")
            return None

        return alert

    def _optimistically_remove_alert(self, alert_id: str) -> None:
        self._alerts.pop(alert_id, None)
        self._row_ids = [current for current in self._row_ids if current != alert_id]
        self._render_table_from_state()

    def _optimistically_ack_alert(self, alert_id: str) -> None:
        alert = self._alerts.get(alert_id)
        if not alert:
            return

        alert.status = "acked"
        if self._actor_email:
            alert.acknowledged_by = self._actor_email
        self._render_table_from_state()

    def _restore_alert(self, alert: Alert, index: int) -> None:
        self._alerts[alert.id] = alert
        if alert.id not in self._row_ids:
            insert_at = min(max(index, 0), len(self._row_ids))
            self._row_ids.insert(insert_at, alert.id)
        self._render_table_from_state()


def _status_cell(status: str) -> Text:
    normalized = status.lower().strip()
    if normalized in {"acked", "acknowledged"}:
        style = "green"
    elif normalized == "open":
        style = "red"
    else:
        style = "yellow"
    return Text(status, style=style)


def _status_style_id(status: str) -> str:
    normalized = status.lower().strip()
    if normalized in {"acked", "acknowledged"}:
        return "detail-status-acked"
    if normalized == "open":
        return "detail-status-open"
    return "detail-status-other"


_URL_PATTERN = re.compile(r"(?<!\()(?P<url>https?://[^\s<>)]+)")
_RUNBOOK_MARKDOWN_PATTERN = re.compile(
    r"\[[^\]]*runbook[^\]]*\]\((?P<url>https?://[^)\s]+)\)", flags=re.IGNORECASE
)
_RUNBOOK_PLAIN_PATTERN = re.compile(
    r"runbook\s*[:=-]?\s*(?P<url>https?://[^\s<>)]+)", flags=re.IGNORECASE
)


def _linkify_urls(text: str) -> str:
    return _URL_PATTERN.sub(r"[\g<url>](\g<url>)", text)


def _extract_runbook_url(text: str) -> str | None:
    markdown_match = _RUNBOOK_MARKDOWN_PATTERN.search(text)
    if markdown_match:
        return _clean_url(markdown_match.group("url"))

    plain_match = _RUNBOOK_PLAIN_PATTERN.search(text)
    if plain_match:
        return _clean_url(plain_match.group("url"))

    fallback = _URL_PATTERN.search(text)
    if fallback:
        return _clean_url(fallback.group("url"))

    return None


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:")


def _truncate_cell(value: str, *, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return "." * max_len
    return f"{value[: max_len - 3]}..."
