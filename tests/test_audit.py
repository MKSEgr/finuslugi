import pytest

from apps.core.audit import record_audit_event
from apps.core.models import AuditEvent


@pytest.mark.django_db
def test_audit_event_is_created_with_non_sensitive_metadata() -> None:
    event = record_audit_event(
        event_type="offer.viewed",
        actor_ref="partner:example",
        object_type="offer",
        object_ref="offer:leasing-v1",
        request_id="request-123",
        metadata={"source": "partner_link", "terms_version": "v1"},
    )

    persisted_event = AuditEvent.objects.get(pk=event.pk)
    assert persisted_event.event_type == "offer.viewed"
    assert persisted_event.metadata["terms_version"] == "v1"


@pytest.mark.django_db
def test_audit_service_rejects_sensitive_metadata_keys() -> None:
    with pytest.raises(ValueError, match="Sensitive audit metadata keys"):
        record_audit_event(
            event_type="lead.created",
            metadata={"phone": "+70000000000"},
        )


@pytest.mark.django_db
def test_audit_event_cannot_be_updated() -> None:
    event = record_audit_event(event_type="lead.created")
    event.event_type = "lead.changed"

    with pytest.raises(ValueError, match="append-only"):
        event.save()


@pytest.mark.django_db
def test_audit_event_cannot_be_deleted_through_instance() -> None:
    event = record_audit_event(event_type="lead.created")

    with pytest.raises(ValueError, match="append-only"):
        event.delete()
