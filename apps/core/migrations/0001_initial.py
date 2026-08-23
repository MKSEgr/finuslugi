# Generated manually for the initial Finuslugi core model.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("event_type", models.CharField(db_index=True, max_length=120)),
                ("actor_ref", models.CharField(blank=True, max_length=120)),
                (
                    "object_type",
                    models.CharField(blank=True, db_index=True, max_length=120),
                ),
                (
                    "object_ref",
                    models.CharField(blank=True, db_index=True, max_length=160),
                ),
                (
                    "request_id",
                    models.CharField(blank=True, db_index=True, max_length=64),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-occurred_at"],
                "indexes": [
                    models.Index(
                        fields=["object_type", "object_ref", "occurred_at"],
                        name="core_audit_obj_time_idx",
                    ),
                    models.Index(
                        fields=["actor_ref", "occurred_at"],
                        name="core_audit_actor_time_idx",
                    ),
                ],
            },
        )
    ]
