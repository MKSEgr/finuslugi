from django.contrib import admin
from django.http import HttpRequest

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "event_type",
        "actor_ref",
        "object_type",
        "object_ref",
        "request_id",
    )
    list_filter = ("event_type", "object_type")
    search_fields = ("actor_ref", "object_ref", "request_id")
    readonly_fields = (
        "id",
        "occurred_at",
        "event_type",
        "actor_ref",
        "object_type",
        "object_ref",
        "request_id",
        "metadata",
    )
    date_hierarchy = "occurred_at"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: AuditEvent | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditEvent | None = None) -> bool:
        return False
