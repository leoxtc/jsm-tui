from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class Alert:
    id: str
    priority: str
    status: str
    message: str
    description: str
    created_at: datetime | None
    acknowledged_by: str
    tags: tuple[str, ...] = ()

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Alert:
        created_at = _parse_datetime(
            payload.get("createdAt")
            or payload.get("created_at")
            or payload.get("insertedAt")
            or payload.get("lastOccurredAt")
        )

        acknowledged_by = _first_non_empty(
            _person_name(payload.get("acknowledgedBy")),
            _person_name(payload.get("acknowledged_by")),
            _person_name(payload.get("acknowledgers")),
            _person_name(payload.get("acknowledgedByUser")),
            _owner_name(payload.get("owner")),
        )
        acknowledged_by = _format_acknowledged_by(acknowledged_by)

        message = str(payload.get("message") or payload.get("alias") or "(no message)")
        description = str(payload.get("description") or payload.get("details") or message)

        return cls(
            id=str(payload.get("id") or payload.get("tinyId") or ""),
            priority=str(payload.get("priority") or "unknown").upper(),
            status=str(payload.get("status") or "unknown").lower(),
            message=message,
            description=description,
            created_at=created_at,
            acknowledged_by=acknowledged_by,
            tags=_extract_tags(payload),
        )

    @property
    def age(self) -> str:
        if self.created_at is None:
            return "-"

        delta = datetime.now(UTC) - self.created_at.astimezone(UTC)
        total_seconds = max(int(delta.total_seconds()), 0)
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)

        if days:
            return f"{days}d"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"

    @property
    def is_open(self) -> bool:
        return self.status not in {"closed", "resolved"}

    @property
    def tags_display(self) -> str:
        if not self.tags:
            return "-"
        return ", ".join(self.tags)


def _first_non_empty(*values: object) -> str:
    for value in values:
        if value:
            return str(value)
    return "-"


def _owner_name(owner: object) -> str:
    return _person_name(owner)


def _person_name(value: object) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        return _first_non_empty(
            value.get("fullName"),
            value.get("displayName"),
            value.get("name"),
            value.get("username"),
            value.get("email"),
            value.get("emailAddress"),
        )

    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            name = _person_name(item).strip()
            if name and name != "-" and name not in names:
                names.append(name)
        return ", ".join(names)

    return ""


def _extract_tags(payload: dict[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []
    for key in ("tags", "alertTags", "labels"):
        raw = payload.get(key)
        if isinstance(raw, list):
            for item in raw:
                tag = _tag_name(item)
                if tag and tag not in tags:
                    tags.append(tag)
            if tags:
                break
    return tuple(tags)


def _tag_name(value: object) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in ("name", "label", "value", "key"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                normalized = candidate.strip()
                if normalized:
                    return normalized

    return ""


def _parse_datetime(raw: object) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None

    try:
        # API returns RFC3339 timestamps.
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_acknowledged_by(value: str) -> str:
    parts = [part.strip() for part in value.split(",")]
    normalized: list[str] = []
    for part in parts:
        if not part:
            continue
        if "@" in part:
            local_part = part.split("@", 1)[0].strip()
            normalized.append(local_part or part)
        else:
            normalized.append(part)
    if not normalized:
        return "-"
    return ", ".join(normalized)
