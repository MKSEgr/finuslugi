from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import (
    Advertiser,
    AttributionSnapshot,
    CashAdjustment,
    CashReceipt,
    ConsentEvidence,
    ConsentTextVersion,
    Lead,
    Offer,
    OfferTermsVersion,
    Partner,
    PartnerAccrual,
    PartnerAccrualAdjustment,
    PartnerOfferTerms,
    PartnerSource,
    StatusEvent,
)


class ReadOnlyLedgerAdmin(admin.ModelAdmin):
    """Ledger rows are created through services and remain read-only in admin."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False


class DraftVersionAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "updated_at", "published_at")

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        if obj is not None and obj.published_at is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        if obj is not None and obj.published_at is not None:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("code", "name", "contract_reference")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PartnerSource)
class PartnerSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "partner", "source_type", "status", "monthly_cap", "approved_at")
    list_filter = ("status", "source_type")
    search_fields = ("code", "partner__code", "partner__name")
    autocomplete_fields = ("partner",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Advertiser)
class AdvertiserAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "status",
        "acknowledgement_sla_minutes",
        "first_contact_sla_minutes",
    )
    list_filter = ("status",)
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "advertiser", "product_type", "status")
    list_filter = ("status", "product_type", "advertiser")
    search_fields = ("code", "name", "advertiser__name")
    autocomplete_fields = ("advertiser",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(OfferTermsVersion)
class OfferTermsVersionAdmin(DraftVersionAdmin):
    list_display = (
        "offer",
        "version",
        "target_action",
        "payout_model",
        "hold_days",
        "published_at",
    )
    list_filter = ("payout_model", "published_at", "offer__product_type")
    search_fields = ("offer__code", "offer__name", "target_action", "terms_digest")
    autocomplete_fields = ("offer",)


@admin.register(PartnerOfferTerms)
class PartnerOfferTermsAdmin(DraftVersionAdmin):
    list_display = (
        "partner",
        "offer_terms_version",
        "version",
        "reward_model",
        "hold_days",
        "published_at",
    )
    list_filter = ("reward_model", "published_at")
    search_fields = ("partner__code", "partner__name", "terms_digest")
    autocomplete_fields = ("partner", "offer_terms_version")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "offer_terms_version",
        "partner_source",
        "direct_source_code",
        "current_status",
        "current_status_at",
        "is_test",
        "created_at",
    )
    list_filter = ("is_test", "current_status", "offer_terms_version__offer__product_type")
    search_fields = (
        "id",
        "client_subject_ref",
        "organization_fingerprint",
        "contact_fingerprint",
    )
    autocomplete_fields = ("offer_terms_version", "partner_source")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "current_status",
        "current_status_at",
    )


@admin.register(ConsentTextVersion)
class ConsentTextVersionAdmin(DraftVersionAdmin):
    list_display = ("consent_type", "version", "published_at", "text_digest")
    list_filter = ("consent_type", "published_at")
    search_fields = ("text_digest", "public_reference")


@admin.register(AttributionSnapshot)
class AttributionSnapshotAdmin(ReadOnlyLedgerAdmin):
    list_display = ("lead", "partner_id_snapshot", "click_id", "first_touch_at", "created_at")
    search_fields = ("lead__id", "click_id", "signed_token_digest")
    readonly_fields = [field.name for field in AttributionSnapshot._meta.fields]


@admin.register(ConsentEvidence)
class ConsentEvidenceAdmin(ReadOnlyLedgerAdmin):
    list_display = ("lead", "consent_text_version", "channel", "confirmed_at")
    list_filter = ("channel", "consent_text_version__consent_type")
    search_fields = ("lead__id", "evidence_digest", "proof_reference")
    readonly_fields = [field.name for field in ConsentEvidence._meta.fields]


@admin.register(StatusEvent)
class StatusEventAdmin(ReadOnlyLedgerAdmin):
    list_display = (
        "lead",
        "sequence",
        "status_code",
        "actor_type",
        "reason_code",
        "occurred_at",
    )
    list_filter = ("status_code", "actor_type", "source_system")
    search_fields = ("lead__id", "actor_ref", "external_reference", "reason_code")
    readonly_fields = [field.name for field in StatusEvent._meta.fields]


@admin.register(CashReceipt)
class CashReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "external_reference",
        "advertiser",
        "lead",
        "gross_amount",
        "distributable_amount",
        "currency",
        "received_at",
    )
    list_filter = ("currency", "advertiser")
    search_fields = ("external_reference", "lead__id", "evidence_reference")
    autocomplete_fields = ("lead", "advertiser")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_change_permission(self, request: HttpRequest, obj: CashReceipt | None = None) -> bool:
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: CashReceipt | None = None) -> bool:
        return False


@admin.register(CashAdjustment)
class CashAdjustmentAdmin(ReadOnlyLedgerAdmin):
    list_display = ("cash_receipt", "amount", "reason_code", "occurred_at")
    search_fields = ("cash_receipt__external_reference", "reason_code", "evidence_reference")
    readonly_fields = [field.name for field in CashAdjustment._meta.fields]


@admin.register(PartnerAccrual)
class PartnerAccrualAdmin(ReadOnlyLedgerAdmin):
    list_display = ("cash_receipt", "partner", "amount", "currency", "created_at")
    list_filter = ("currency", "partner")
    search_fields = ("cash_receipt__external_reference", "partner__code", "rate_basis")
    readonly_fields = [field.name for field in PartnerAccrual._meta.fields]


@admin.register(PartnerAccrualAdjustment)
class PartnerAccrualAdjustmentAdmin(ReadOnlyLedgerAdmin):
    list_display = ("partner_accrual", "amount", "reason_code", "occurred_at")
    search_fields = ("partner_accrual__id", "reason_code", "evidence_reference")
    readonly_fields = [field.name for field in PartnerAccrualAdjustment._meta.fields]
