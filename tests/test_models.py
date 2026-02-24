from datetime import UTC, datetime, timedelta

from jsm_tui.models import Alert


def test_alert_from_api_parses_core_fields() -> None:
    now = datetime.now(UTC).isoformat()
    payload = {
        "id": "abc123",
        "priority": "P1",
        "status": "open",
        "message": "Database unreachable",
        "description": "DB connection timeout for prod",
        "createdAt": now,
        "acknowledgedBy": "oncall@example.com",
    }

    alert = Alert.from_api(payload)

    assert alert.id == "abc123"
    assert alert.priority == "P1"
    assert alert.status == "open"
    assert alert.message == "Database unreachable"
    assert alert.description == "DB connection timeout for prod"
    assert alert.acknowledged_by == "oncall"
    assert alert.tags == ()
    assert alert.tags_display == "-"
    assert alert.created_at is not None


def test_age_formats_days_hours_minutes() -> None:
    base = datetime.now(UTC)

    day_alert = Alert(
        id="1",
        priority="P1",
        status="open",
        message="m",
        description="d",
        created_at=base - timedelta(days=2),
        acknowledged_by="-",
    )
    hour_alert = Alert(
        id="2",
        priority="P1",
        status="open",
        message="m",
        description="d",
        created_at=base - timedelta(hours=3),
        acknowledged_by="-",
    )
    minute_alert = Alert(
        id="3",
        priority="P1",
        status="open",
        message="m",
        description="d",
        created_at=base - timedelta(minutes=15),
        acknowledged_by="-",
    )

    assert day_alert.age.endswith("d")
    assert hour_alert.age.endswith("h")
    assert minute_alert.age.endswith("m")


def test_alert_from_api_parses_acknowledged_by_dict() -> None:
    payload = {
        "id": "abc123",
        "status": "acknowledged",
        "message": "Database unreachable",
        "acknowledgedBy": {"fullName": "Jane Oncall"},
    }

    alert = Alert.from_api(payload)

    assert alert.acknowledged_by == "Jane Oncall"


def test_alert_from_api_parses_acknowledged_by_list() -> None:
    payload = {
        "id": "abc123",
        "status": "acknowledged",
        "message": "Database unreachable",
        "acknowledgedBy": [
            {"fullName": "Jane Oncall"},
            {"email": "sre@example.com"},
        ],
    }

    alert = Alert.from_api(payload)

    assert alert.acknowledged_by == "Jane Oncall, sre"


def test_alert_from_api_parses_tags_from_list_of_strings() -> None:
    payload = {
        "id": "abc123",
        "status": "open",
        "message": "Database unreachable",
        "tags": ["payments", "prod"],
    }

    alert = Alert.from_api(payload)

    assert alert.tags == ("payments", "prod")
    assert alert.tags_display == "payments, prod"


def test_alert_from_api_parses_tags_from_dicts_and_deduplicates() -> None:
    payload = {
        "id": "abc123",
        "status": "open",
        "message": "Database unreachable",
        "alertTags": [
            {"name": "payments"},
            {"label": "p1"},
            {"value": "payments"},
            {"key": "backend"},
            {"ignored": "x"},
        ],
    }

    alert = Alert.from_api(payload)

    assert alert.tags == ("payments", "p1", "backend")

