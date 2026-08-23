from __future__ import annotations

import uuid
from typing import Any

from django.db import models


class TimestampedUUIDModel(models.Model):
    """Abstract base model with stable UUID identity and timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditEvent(models.Model):
    """Append-only audit record for business-significant actions.

    Metadata must contain identifiers and non-sensitive context only. Personal data,
    credentials, request bodies, and documents must never be copied into this table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    actor_ref = models.CharField(max_length=120, blank=True)
    object_type = models.CharField(max_length=120, blank=True, db_index=True)
    object_ref = models.CharField(max_length=160, blank=True, db_index=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    metadata: dict[str, Any] = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["object_type", "object_ref", "occurred_at"]),
            models.Index(fields=["actor_ref", "occurred_at"]),
        ]

    def __str__(self) -> str:
        target = f" {self.object_type}:{self.object_ref}" if self.object_ref else ""
        return f"{self.event_type}{target}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit events are append-only and cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValueError("Audit events are append-only and cannot be deleted")
