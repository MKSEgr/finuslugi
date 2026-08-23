from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import AuditEvent

_FORBIDDEN_METADATA_KEYS = {
    "authorization",
    "cookie",
    "document",
    "email",
    "inn",
    "passport",
    "password",
    "phone",
    "request_body",
    "secret",
    "token",
}


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    normalized_keys = {str(key).strip().lower() for key in metadata}
    forbidden_keys = normalized_keys & _FORBIDDEN_METADATA_KEYS
    if forbidden_keys:
        joined_keys = ", ".join(sorted(forbidden_keys))
        raise ValueError(f"Sensitive audit metadata keys are forbidden: {joined_keys}")


def record_audit_event(
    *,
    event_type: str,
    actor_ref: str = "",
    object_type: str = "",
    object_ref: str = "",
    request_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> AuditEvent:
    """Persist a sanitized, append-only business audit event."""

    safe_metadata = dict(metadata or {})
    _validate_metadata(safe_metadata)
    return AuditEvent.objects.create(
        event_type=event_type,
        actor_ref=actor_ref,
        object_type=object_type,
        object_ref=object_ref,
        request_id=request_id,
        metadata=safe_metadata,
    )
