from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimestampedUUIDModel

_FORBIDDEN_JSON_KEYS = {
    "address",
    "authorization",
    "cookie",
    "document",
    "email",
    "fio",
    "full_name",
    "inn",
    "ip",
    "passport",
    "password",
    "phone",
    "request_body",
    "secret",
    "token",
    "user_agent",
}


def validate_safe_json(value: Any) -> None:
    """Reject obvious PII/credential fields from operational metadata.

    The operational ledger stores identifiers and commercial facts only. Raw contact
    data belongs in a separately reviewed secure data store, not in JSON payloads.
    """

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                normalized = str(key).strip().lower().replace("-", "_")
                if normalized in _FORBIDDEN_JSON_KEYS:
                    raise ValidationError(
                        f"Sensitive JSON key is forbidden in operational metadata: {key}"
                    )
                walk(child)
            return
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for child in node:
                walk(child)
            return
        if node is not None and not isinstance(node, (str, int, float, bool)):
            raise ValidationError("Operational JSON contains an unsupported value type")

    walk(value)


def validate_sha256_digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValidationError("Expected a lowercase hexadecimal SHA-256 digest")


class ValidatedModelMixin:
    """Run Django validation before every mutable model save."""

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ImmutableCreateMixin:
    """Allow creation only; corrections must be represented by new ledger rows."""

    immutable_error = "This ledger record is append-only and cannot be changed"

    def save(self, *args: Any, **kwargs: Any) -> None:
        model = type(self)
        if self.pk and model.objects.filter(pk=self.pk).exists():
            raise ValidationError(self.immutable_error)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError(self.immutable_error)


class ImmutableAfterPublishMixin:
    """Drafts may change; a published terms/text version is immutable."""

    immutable_error = "A published version cannot be changed or deleted"

    def save(self, *args: Any, **kwargs: Any) -> None:
        model = type(self)
        if self.pk:
            original = model.objects.filter(pk=self.pk).only("published_at").first()
            if original is not None and original.published_at is not None:
                raise ValidationError(self.immutable_error)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.published_at is not None:
            raise ValidationError(self.immutable_error)
        return super().delete(*args, **kwargs)


class Partner(ValidatedModelMixin, TimestampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        CLOSED = "CLOSED", "Closed"

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    contract_reference = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "code"], name="ops_partner_status_idx")]

    def __str__(self) -> str:
        return self.name


class PartnerSource(ValidatedModelMixin, TimestampedUUIDModel):
    class SourceType(models.TextChoices):
        EMBEDDED = "EMBEDDED", "Embedded professional partner"
        PAID_SEARCH = "PAID_SEARCH", "Paid search"
        SEO = "SEO", "Organic search"
        TELEGRAM = "TELEGRAM", "Telegram"
        REFERRAL = "REFERRAL", "Referral"
        OTHER = "OTHER", "Other approved source"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        SUSPENDED = "SUSPENDED", "Suspended"
        REJECTED = "REJECTED", "Rejected"

    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="sources")
    code = models.SlugField(max_length=64)
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    allowed_channels = models.JSONField(default=list, blank=True, validators=[validate_safe_json])
    monthly_cap = models.PositiveIntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["partner__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["partner", "code"], name="ops_unique_partner_source"),
            models.CheckConstraint(
                condition=Q(monthly_cap__isnull=True) | Q(monthly_cap__gt=0),
                name="ops_partner_source_cap_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "source_type"], name="ops_source_status_type_idx")
        ]

    def __str__(self) -> str:
        return f"{self.partner.code}:{self.code}"


class Advertiser(ValidatedModelMixin, TimestampedUUIDModel):
    class Status(models.TextChoices):
        DISCOVERY = "DISCOVERY", "Discovery"
        COMPATIBLE = "COMPATIBLE", "Compatible"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        REJECTED = "REJECTED", "Rejected"

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DISCOVERY)
    acknowledgement_sla_minutes = models.PositiveIntegerField(default=60)
    first_contact_sla_minutes = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "code"], name="ops_advertiser_status_idx")]

    def __str__(self) -> str:
        return self.name


class Offer(ValidatedModelMixin, TimestampedUUIDModel):
    class ProductType(models.TextChoices):
        LEASING = "LEASING", "Leasing"
        RKO = "RKO", "Settlement account"
        FACTORING = "FACTORING", "Factoring"
        GUARANTEE = "GUARANTEE", "Bank guarantee"
        ACQUIRING = "ACQUIRING", "Acquiring"
        OTHER = "OTHER", "Other B2B product"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        CLOSED = "CLOSED", "Closed"

    advertiser = models.ForeignKey(Advertiser, on_delete=models.PROTECT, related_name="offers")
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=24, choices=ProductType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["advertiser__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["advertiser", "code"], name="ops_unique_offer_code")
        ]
        indexes = [
            models.Index(fields=["status", "product_type"], name="ops_offer_status_type_idx")
        ]

    def __str__(self) -> str:
        return f"{self.advertiser.code}:{self.code}"


class OfferTermsVersion(ImmutableAfterPublishMixin, TimestampedUUIDModel):
    class PayoutModel(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        PERCENT = "PERCENT", "Percentage"
        REVSHARE = "REVSHARE", "Revenue share"
        HYBRID = "HYBRID", "Hybrid"

    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name="terms_versions")
    version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    published_at = models.DateTimeField(null=True, blank=True)
    target_action = models.CharField(max_length=128)
    payout_model = models.CharField(max_length=16, choices=PayoutModel.choices)
    payout_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    payout_rate = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    hold_days = models.PositiveIntegerField(default=0)
    dedup_window_days = models.PositiveIntegerField(default=0)
    attribution_window_days = models.PositiveIntegerField(default=30)
    allow_own_landing = models.BooleanField(default=False)
    allow_professional_partners = models.BooleanField(default=False)
    allow_paid_nonbrand_search = models.BooleanField(default=False)
    allow_rerouting = models.BooleanField(default=False)
    terms_digest = models.CharField(max_length=64, validators=[validate_sha256_digest])
    rules = models.JSONField(default=dict, blank=True, validators=[validate_safe_json])

    class Meta:
        ordering = ["offer", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["offer", "version"],
                name="ops_unique_offer_terms_version",
            ),
            models.CheckConstraint(
                condition=Q(payout_amount__isnull=True) | Q(payout_amount__gte=0),
                name="ops_offer_payout_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(payout_rate__isnull=True)
                | (Q(payout_rate__gte=0) & Q(payout_rate__lte=100)),
                name="ops_offer_payout_rate_range",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        amount_required = self.payout_model in {
            self.PayoutModel.FIXED,
            self.PayoutModel.HYBRID,
        }
        rate_required = self.payout_model in {
            self.PayoutModel.PERCENT,
            self.PayoutModel.REVSHARE,
            self.PayoutModel.HYBRID,
        }
        if amount_required and self.payout_amount is None:
            errors["payout_amount"] = "This payout model requires an amount"
        if not amount_required and self.payout_amount is not None:
            errors["payout_amount"] = "This payout model must not define an amount"
        if rate_required and self.payout_rate is None:
            errors["payout_rate"] = "This payout model requires a rate"
        if not rate_required and self.payout_rate is not None:
            errors["payout_rate"] = "This payout model must not define a rate"
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        state = "published" if self.published_at else "draft"
        return f"{self.offer} v{self.version} ({state})"

    def publish(self) -> None:
        if self.published_at is not None:
            raise ValidationError("Terms version is already published")
        self.published_at = timezone.now()
        self.save()


class PartnerOfferTerms(ImmutableAfterPublishMixin, TimestampedUUIDModel):
    class RewardModel(models.TextChoices):
        FIXED = "FIXED", "Fixed amount"
        PERCENT_OF_RECEIPT = "PERCENT_OF_RECEIPT", "Percentage of distributable cash"

    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="offer_terms")
    offer_terms_version = models.ForeignKey(
        OfferTermsVersion,
        on_delete=models.PROTECT,
        related_name="partner_terms",
    )
    version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    published_at = models.DateTimeField(null=True, blank=True)
    reward_model = models.CharField(max_length=24, choices=RewardModel.choices)
    fixed_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    receipt_share_percent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
    )
    hold_days = models.PositiveIntegerField(default=0)
    terms_digest = models.CharField(max_length=64, validators=[validate_sha256_digest])

    class Meta:
        ordering = ["partner", "offer_terms_version", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "offer_terms_version", "version"],
                name="ops_unique_partner_offer_terms",
            ),
            models.CheckConstraint(
                condition=Q(fixed_amount__isnull=True) | Q(fixed_amount__gte=0),
                name="ops_partner_fixed_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(receipt_share_percent__isnull=True)
                | (Q(receipt_share_percent__gte=0) & Q(receipt_share_percent__lte=100)),
                name="ops_partner_share_range",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.published_at is not None and self.offer_terms_version_id:
            if self.offer_terms_version.published_at is None:
                errors["offer_terms_version"] = (
                    "Partner terms cannot be published before advertiser terms"
                )
        if self.reward_model == self.RewardModel.FIXED:
            if self.fixed_amount is None:
                errors["fixed_amount"] = "Fixed reward requires an amount"
            if self.receipt_share_percent is not None:
                errors["receipt_share_percent"] = "Fixed reward must not define a receipt share"
        elif self.reward_model == self.RewardModel.PERCENT_OF_RECEIPT:
            if self.receipt_share_percent is None:
                errors["receipt_share_percent"] = "Percentage reward requires a share"
            if self.fixed_amount is not None:
                errors["fixed_amount"] = "Percentage reward must not define a fixed amount"
        if errors:
            raise ValidationError(errors)

    def publish(self) -> None:
        if self.published_at is not None:
            raise ValidationError("Partner terms version is already published")
        self.published_at = timezone.now()
        self.save()


class LeadStatus(models.TextChoices):
    ASSISTED_DRAFT = "ASSISTED_DRAFT", "Assisted draft"
    LEAD_CREATED = "LEAD_CREATED", "Lead created"
    PHONE_VERIFIED = "PHONE_VERIFIED", "Phone verified"
    CONSENTS_CONFIRMED = "CONSENTS_CONFIRMED", "Consents confirmed"
    QUALIFICATION_STARTED = "QUALIFICATION_STARTED", "Qualification started"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION", "Needs clarification"
    QUALIFIED = "QUALIFIED", "Qualified"
    NOT_QUALIFIED = "NOT_QUALIFIED", "Not qualified"
    DUPLICATE = "DUPLICATE", "Duplicate"
    SOURCE_NOT_ALLOWED = "SOURCE_NOT_ALLOWED", "Source not allowed"
    CONSENT_INVALID = "CONSENT_INVALID", "Consent invalid"
    ROUTING_DECIDED = "ROUTING_DECIDED", "Routing decided"
    SENT_TO_ADVERTISER = "SENT_TO_ADVERTISER", "Sent to advertiser"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED", "Delivery confirmed"
    ADVERTISER_ACCEPTED = "ADVERTISER_ACCEPTED", "Advertiser accepted"
    ADVERTISER_REJECTED = "ADVERTISER_REJECTED", "Advertiser rejected"
    CLIENT_CONTACTED = "CLIENT_CONTACTED", "Client contacted"
    DOCUMENTS_REQUESTED = "DOCUMENTS_REQUESTED", "Documents requested"
    PRE_APPROVED = "PRE_APPROVED", "Pre-approved"
    APPROVED = "APPROVED", "Approved"
    CONTRACT_SIGNED = "CONTRACT_SIGNED", "Contract signed"
    PRODUCT_ACTIVATED = "PRODUCT_ACTIVATED", "Asset delivered or product activated"
    PAYOUT_EXPECTED = "PAYOUT_EXPECTED", "Payout expected"
    PAYOUT_APPROVED = "PAYOUT_APPROVED", "Payout approved"
    RECONCILIATION_RECEIVED = "RECONCILIATION_RECEIVED", "Reconciliation received"
    INVOICED = "INVOICED", "Invoiced"
    CASH_RECEIVED = "CASH_RECEIVED", "Cash received"
    PARTNER_ACCRUAL_CREATED = "PARTNER_ACCRUAL_CREATED", "Partner accrual created"
    PARTNER_PAID = "PARTNER_PAID", "Partner paid"
    CANCELLED = "CANCELLED", "Cancelled"


class Lead(ValidatedModelMixin, TimestampedUUIDModel):
    offer_terms_version = models.ForeignKey(
        OfferTermsVersion,
        on_delete=models.PROTECT,
        related_name="leads",
    )
    partner_source = models.ForeignKey(
        PartnerSource,
        on_delete=models.PROTECT,
        related_name="leads",
        null=True,
        blank=True,
    )
    direct_source_code = models.SlugField(max_length=64, blank=True)
    client_subject_ref = models.UUIDField(db_index=True)
    organization_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        validators=[validate_sha256_digest],
    )
    contact_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        validators=[validate_sha256_digest],
    )
    fingerprint_key_version = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Version of the secret key used for HMAC-SHA-256 fingerprints",
    )
    commercial_context = models.JSONField(default=dict, blank=True, validators=[validate_safe_json])
    current_status = models.CharField(
        max_length=40,
        choices=LeadStatus.choices,
        blank=True,
    )
    current_status_at = models.DateTimeField(null=True, blank=True)
    is_test = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(partner_source__isnull=False) & Q(direct_source_code=""))
                | (Q(partner_source__isnull=True) & ~Q(direct_source_code="")),
                name="ops_lead_exactly_one_source",
            )
        ]
        indexes = [
            models.Index(fields=["current_status", "created_at"], name="ops_lead_status_time_idx"),
            models.Index(
                fields=["organization_fingerprint", "created_at"],
                name="ops_lead_org_fp_time_idx",
            ),
        ]

    _IMMUTABLE_FIELDS = (
        "offer_terms_version_id",
        "partner_source_id",
        "direct_source_code",
        "client_subject_ref",
        "organization_fingerprint",
        "contact_fingerprint",
        "fingerprint_key_version",
        "is_test",
        "current_status",
        "current_status_at",
    )

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.offer_terms_version_id:
            if self.offer_terms_version.published_at is None:
                errors["offer_terms_version"] = "Lead requires published offer terms"
            if self.partner_source_id and not self.offer_terms_version.allow_professional_partners:
                errors["partner_source"] = (
                    "Offer terms do not allow professional partner distribution"
                )
        if self.partner_source_id:
            if self.partner_source.status != PartnerSource.Status.APPROVED:
                errors["partner_source"] = "Lead source must be approved"
            if self.partner_source.partner.status != Partner.Status.ACTIVE:
                errors["partner_source"] = "Lead partner must be active"
        if not self.pk and (self.current_status or self.current_status_at is not None):
            errors["current_status"] = "Initial status must be appended through the status ledger"
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values(*self._IMMUTABLE_FIELDS).first()
            if original is not None:
                changed = [
                    field
                    for field in self._IMMUTABLE_FIELDS
                    if getattr(self, field) != original[field]
                ]
                if changed:
                    raise ValidationError(
                        f"Immutable lead fields cannot be changed: {', '.join(changed)}"
                    )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.id)


class AttributionSnapshot(ImmutableCreateMixin, TimestampedUUIDModel):
    lead = models.OneToOneField(Lead, on_delete=models.PROTECT, related_name="attribution")
    partner_id_snapshot = models.UUIDField(null=True, blank=True)
    partner_source_id_snapshot = models.UUIDField(null=True, blank=True)
    click_id = models.CharField(max_length=128, blank=True)
    signed_token_digest = models.CharField(
        max_length=64,
        blank=True,
        validators=[validate_sha256_digest],
    )
    utm_source = models.CharField(max_length=128, blank=True)
    utm_medium = models.CharField(max_length=128, blank=True)
    utm_campaign = models.CharField(max_length=128, blank=True)
    utm_content = models.CharField(max_length=128, blank=True)
    utm_term = models.CharField(max_length=128, blank=True)
    landing_variant = models.CharField(max_length=64, blank=True)
    referrer_domain = models.CharField(max_length=255, blank=True)
    first_touch_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def clean(self) -> None:
        super().clean()
        if not self.lead_id:
            return
        if self.lead.partner_source_id:
            expected_partner = self.lead.partner_source.partner_id
            if self.partner_source_id_snapshot != self.lead.partner_source_id:
                raise ValidationError("Attribution source snapshot does not match the lead")
            if self.partner_id_snapshot != expected_partner:
                raise ValidationError("Attribution partner snapshot does not match the lead")
            return
        if self.partner_id_snapshot is not None or self.partner_source_id_snapshot is not None:
            raise ValidationError("Direct lead attribution must not contain partner snapshots")

    def __str__(self) -> str:
        return f"Attribution {self.lead_id}"


class ConsentTextVersion(ImmutableAfterPublishMixin, TimestampedUUIDModel):
    class ConsentType(models.TextChoices):
        PROCESSING = "PROCESSING", "Personal data processing"
        TRANSFER = "TRANSFER", "Personal data transfer"
        MARKETING = "MARKETING", "Marketing communications"
        CALL_RECORDING = "CALL_RECORDING", "Call recording"

    consent_type = models.CharField(max_length=24, choices=ConsentType.choices)
    version = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    text_digest = models.CharField(max_length=64, validators=[validate_sha256_digest])
    public_reference = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["consent_type", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["consent_type", "version"],
                name="ops_unique_consent_text_version",
            )
        ]

    def publish(self) -> None:
        if self.published_at is not None:
            raise ValidationError("Consent text version is already published")
        self.published_at = timezone.now()
        self.save()

    def __str__(self) -> str:
        return f"{self.consent_type} v{self.version}"


class ConsentEvidence(ImmutableCreateMixin, TimestampedUUIDModel):
    class Channel(models.TextChoices):
        WEB_CHECKBOX = "WEB_CHECKBOX", "Web checkbox"
        SMS_OTP = "SMS_OTP", "SMS OTP"
        SIGNED_LINK = "SIGNED_LINK", "Signed link"
        OTHER = "OTHER", "Other approved channel"

    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="consent_evidence")
    consent_text_version = models.ForeignKey(
        ConsentTextVersion,
        on_delete=models.PROTECT,
        related_name="evidence",
    )
    confirmed_at = models.DateTimeField()
    channel = models.CharField(max_length=24, choices=Channel.choices)
    subject_ref = models.UUIDField()
    evidence_digest = models.CharField(max_length=64, validators=[validate_sha256_digest])
    ip_digest = models.CharField(max_length=64, blank=True, validators=[validate_sha256_digest])
    user_agent_digest = models.CharField(
        max_length=64,
        blank=True,
        validators=[validate_sha256_digest],
    )
    recipient_list_version = models.CharField(max_length=64, blank=True)
    proof_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["lead", "confirmed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "consent_text_version"],
                name="ops_unique_lead_consent_evidence",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.consent_text_version_id and self.consent_text_version.published_at is None:
            raise ValidationError("Consent evidence must reference a published text version")
        if self.lead_id and self.subject_ref != self.lead.client_subject_ref:
            raise ValidationError("Consent subject does not match the lead subject")

    def __str__(self) -> str:
        return f"Consent {self.lead_id}:{self.consent_text_version_id}"


class StatusEvent(ImmutableCreateMixin, TimestampedUUIDModel):
    class ActorType(models.TextChoices):
        SYSTEM = "SYSTEM", "System"
        OPERATOR = "OPERATOR", "Operator"
        PARTNER = "PARTNER", "Partner"
        ADVERTISER = "ADVERTISER", "Advertiser"
        FINANCE = "FINANCE", "Finance"

    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="status_events")
    sequence = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status_code = models.CharField(max_length=40, choices=LeadStatus.choices)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor_type = models.CharField(max_length=16, choices=ActorType.choices)
    actor_ref = models.CharField(max_length=120, blank=True)
    source_system = models.CharField(max_length=64, default="finuslugi")
    reason_code = models.CharField(max_length=64, blank=True)
    external_reference = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True, validators=[validate_safe_json])

    class Meta:
        ordering = ["lead", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["lead", "sequence"], name="ops_unique_lead_sequence")
        ]
        indexes = [models.Index(fields=["lead", "occurred_at"], name="ops_status_lead_time_idx")]

    def __str__(self) -> str:
        return f"{self.lead_id} #{self.sequence} {self.status_code}"


class CashReceipt(ImmutableCreateMixin, TimestampedUUIDModel):
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="cash_receipts")
    advertiser = models.ForeignKey(
        Advertiser,
        on_delete=models.PROTECT,
        related_name="cash_receipts",
    )
    external_reference = models.CharField(max_length=128)
    received_at = models.DateTimeField(default=timezone.now)
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2)
    distributable_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    evidence_reference = models.CharField(max_length=255)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["advertiser", "external_reference"],
                name="ops_unique_advertiser_cash_ref",
            ),
            models.CheckConstraint(condition=Q(gross_amount__gt=0), name="ops_cash_gross_positive"),
            models.CheckConstraint(
                condition=Q(distributable_amount__gte=0),
                name="ops_cash_distributable_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(distributable_amount__lte=models.F("gross_amount")),
                name="ops_cash_distributable_lte_gross",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not self.lead_id or not self.advertiser_id:
            return
        expected_advertiser = self.lead.offer_terms_version.offer.advertiser_id
        if self.advertiser_id != expected_advertiser:
            raise ValidationError("Cash receipt advertiser does not match the lead offer")
        if self.currency != self.lead.offer_terms_version.currency:
            raise ValidationError("Cash receipt currency does not match the offer terms")

    def __str__(self) -> str:
        return f"{self.external_reference}: {self.distributable_amount} {self.currency}"


class CashAdjustment(ImmutableCreateMixin, TimestampedUUIDModel):
    cash_receipt = models.ForeignKey(
        CashReceipt,
        on_delete=models.PROTECT,
        related_name="adjustments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason_code = models.CharField(max_length=64)
    evidence_reference = models.CharField(max_length=255)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["cash_receipt", "occurred_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="ops_cash_adjustment_nonzero")
        ]

    def clean(self) -> None:
        super().clean()
        if not self.cash_receipt_id or self.amount is None:
            return
        existing_adjustments = self.cash_receipt.adjustments.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        base_allocated = self.cash_receipt.partner_accruals.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        accrual_adjustments = PartnerAccrualAdjustment.objects.filter(
            partner_accrual__cash_receipt=self.cash_receipt
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
        new_available = (
            Decimal(self.cash_receipt.distributable_amount)
            + Decimal(existing_adjustments)
            + Decimal(self.amount)
        )
        allocated = Decimal(base_allocated) + Decimal(accrual_adjustments)
        if new_available < 0:
            raise ValidationError("Cash adjustment would make distributable cash negative")
        if new_available < allocated:
            raise ValidationError("Cash adjustment would reduce cash below partner allocations")

    def __str__(self) -> str:
        return f"Cash adjustment {self.amount} for {self.cash_receipt_id}"


class PartnerAccrual(ImmutableCreateMixin, TimestampedUUIDModel):
    cash_receipt = models.ForeignKey(
        CashReceipt,
        on_delete=models.PROTECT,
        related_name="partner_accruals",
    )
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="accruals")
    partner_offer_terms = models.ForeignKey(
        PartnerOfferTerms,
        on_delete=models.PROTECT,
        related_name="accruals",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    rate_basis = models.CharField(max_length=255)

    class Meta:
        ordering = ["cash_receipt", "partner"]
        constraints = [
            models.UniqueConstraint(
                fields=["cash_receipt", "partner"],
                name="ops_unique_receipt_partner_accrual",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="ops_partner_accrual_positive"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.partner_offer_terms_id and self.partner_offer_terms.published_at is None:
            raise ValidationError("Partner terms must be published before accrual")
        if self.partner_offer_terms_id and self.partner_offer_terms.partner_id != self.partner_id:
            raise ValidationError("Partner terms do not belong to the accrual partner")
        if (
            self.partner_offer_terms_id
            and self.partner_offer_terms.offer_terms_version_id
            != self.cash_receipt.lead.offer_terms_version_id
        ):
            raise ValidationError("Partner terms do not match the receipt lead offer version")
        lead_source = self.cash_receipt.lead.partner_source
        if lead_source is None or lead_source.partner_id != self.partner_id:
            raise ValidationError("Accrual partner does not match the lead source")
        if self.currency != self.cash_receipt.currency:
            raise ValidationError("Accrual currency must match the cash receipt")
        existing_cash_adjustments = self.cash_receipt.adjustments.aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")
        available = Decimal(self.cash_receipt.distributable_amount) + Decimal(
            existing_cash_adjustments
        )
        existing_accruals = self.cash_receipt.partner_accruals.aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")
        existing_accrual_adjustments = PartnerAccrualAdjustment.objects.filter(
            partner_accrual__cash_receipt=self.cash_receipt
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
        if (
            Decimal(existing_accruals)
            + Decimal(existing_accrual_adjustments)
            + Decimal(self.amount)
            > available
        ):
            raise ValidationError("Accrual exceeds distributable cash")

    def __str__(self) -> str:
        return f"{self.partner.code}: {self.amount} {self.currency}"


class PartnerAccrualAdjustment(ImmutableCreateMixin, TimestampedUUIDModel):
    partner_accrual = models.ForeignKey(
        PartnerAccrual,
        on_delete=models.PROTECT,
        related_name="adjustments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason_code = models.CharField(max_length=64)
    evidence_reference = models.CharField(max_length=255)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["partner_accrual", "occurred_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="ops_accrual_adjustment_nonzero")
        ]

    def clean(self) -> None:
        super().clean()
        if not self.partner_accrual_id or self.amount is None:
            return
        receipt = self.partner_accrual.cash_receipt
        current_adjustments = self.partner_accrual.adjustments.aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")
        effective_accrual = (
            Decimal(self.partner_accrual.amount)
            + Decimal(current_adjustments)
            + Decimal(self.amount)
        )
        if effective_accrual < 0:
            raise ValidationError("Adjustment would make partner accrual negative")
        cash_adjustments = receipt.adjustments.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        available = Decimal(receipt.distributable_amount) + Decimal(cash_adjustments)
        base_allocated = receipt.partner_accruals.aggregate(total=models.Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        all_adjustments = PartnerAccrualAdjustment.objects.filter(
            partner_accrual__cash_receipt=receipt
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
        if Decimal(base_allocated) + Decimal(all_adjustments) + Decimal(self.amount) > available:
            raise ValidationError("Adjustment would over-allocate distributable cash")

    def __str__(self) -> str:
        return f"Accrual adjustment {self.amount} for {self.partner_accrual_id}"
