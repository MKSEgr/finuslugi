from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    CashAdjustment,
    CashReceipt,
    Lead,
    LeadStatus,
    Partner,
    PartnerAccrual,
    PartnerAccrualAdjustment,
    PartnerOfferTerms,
    StatusEvent,
)

_MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)
_ZERO = Decimal("0.00")


class CashInvariantError(ValidationError):
    """Raised when a financial ledger operation would over-allocate cash."""


def _sum_amount(queryset: Any) -> Decimal:
    result = queryset.aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(_ZERO, output_field=_MONEY_FIELD),
            output_field=_MONEY_FIELD,
        )
    )["total"]
    return Decimal(result)


def available_for_distribution(cash_receipt: CashReceipt) -> Decimal:
    adjustments = _sum_amount(cash_receipt.adjustments.all())
    return Decimal(cash_receipt.distributable_amount) + adjustments


def allocated_to_partners(cash_receipt: CashReceipt) -> Decimal:
    base = _sum_amount(cash_receipt.partner_accruals.all())
    adjustments = _sum_amount(
        PartnerAccrualAdjustment.objects.filter(partner_accrual__cash_receipt=cash_receipt)
    )
    return base + adjustments


@transaction.atomic
def append_status_event(
    *,
    lead: Lead,
    status_code: str,
    actor_type: str,
    actor_ref: str = "",
    source_system: str = "finuslugi",
    reason_code: str = "",
    external_reference: str = "",
    metadata: dict[str, Any] | None = None,
    occurred_at: Any | None = None,
) -> StatusEvent:
    """Append one status and update the lead projection under a row lock."""

    if status_code not in LeadStatus.values:
        raise ValidationError({"status_code": "Unknown lead status"})
    if actor_type not in StatusEvent.ActorType.values:
        raise ValidationError({"actor_type": "Unknown actor type"})

    locked_lead = Lead.objects.select_for_update().get(pk=lead.pk)
    last_sequence = (
        StatusEvent.objects.filter(lead=locked_lead)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
        or 0
    )
    event_time = occurred_at or timezone.now()
    event = StatusEvent.objects.create(
        lead=locked_lead,
        sequence=last_sequence + 1,
        status_code=status_code,
        occurred_at=event_time,
        actor_type=actor_type,
        actor_ref=actor_ref,
        source_system=source_system,
        reason_code=reason_code,
        external_reference=external_reference,
        metadata=metadata or {},
    )
    Lead.objects.filter(pk=locked_lead.pk).update(
        current_status=status_code,
        current_status_at=event_time,
        updated_at=timezone.now(),
    )
    return event


@transaction.atomic
def create_cash_adjustment(
    *,
    cash_receipt: CashReceipt,
    amount: Decimal,
    reason_code: str,
    evidence_reference: str,
) -> CashAdjustment:
    locked_receipt = CashReceipt.objects.select_for_update().get(pk=cash_receipt.pk)
    amount = Decimal(amount)
    if amount == _ZERO:
        raise CashInvariantError("Cash adjustment must be non-zero")

    new_available = available_for_distribution(locked_receipt) + amount
    allocated = allocated_to_partners(locked_receipt)
    if new_available < _ZERO:
        raise CashInvariantError("Cash adjustment would make distributable cash negative")
    if new_available < allocated:
        raise CashInvariantError(
            "Cash adjustment would reduce available cash below existing partner allocations"
        )

    return CashAdjustment.objects.create(
        cash_receipt=locked_receipt,
        amount=amount,
        reason_code=reason_code,
        evidence_reference=evidence_reference,
    )


@transaction.atomic
def create_partner_accrual(
    *,
    cash_receipt: CashReceipt,
    partner: Partner,
    partner_offer_terms: PartnerOfferTerms,
    amount: Decimal,
    rate_basis: str,
) -> PartnerAccrual:
    locked_receipt = CashReceipt.objects.select_for_update().get(pk=cash_receipt.pk)
    amount = Decimal(amount)
    if amount <= _ZERO:
        raise CashInvariantError("Partner accrual must be positive")
    if partner_offer_terms.published_at is None:
        raise CashInvariantError("Partner terms must be published before accrual")
    if PartnerAccrual.objects.filter(
        cash_receipt=locked_receipt,
        partner=partner,
    ).exists():
        raise CashInvariantError("A partner accrual already exists for this cash receipt")

    available = available_for_distribution(locked_receipt)
    allocated = allocated_to_partners(locked_receipt)
    if allocated + amount > available:
        raise CashInvariantError(
            f"Accrual exceeds available cash: {allocated + amount} > {available}"
        )

    return PartnerAccrual.objects.create(
        cash_receipt=locked_receipt,
        partner=partner,
        partner_offer_terms=partner_offer_terms,
        amount=amount,
        currency=locked_receipt.currency,
        rate_basis=rate_basis,
    )


@transaction.atomic
def create_partner_accrual_adjustment(
    *,
    partner_accrual: PartnerAccrual,
    amount: Decimal,
    reason_code: str,
    evidence_reference: str,
) -> PartnerAccrualAdjustment:
    locked_accrual = (
        PartnerAccrual.objects.select_for_update()
        .select_related("cash_receipt")
        .get(pk=partner_accrual.pk)
    )
    locked_receipt = CashReceipt.objects.select_for_update().get(pk=locked_accrual.cash_receipt_id)
    amount = Decimal(amount)
    if amount == _ZERO:
        raise CashInvariantError("Partner accrual adjustment must be non-zero")

    current_accrual_adjustments = _sum_amount(locked_accrual.adjustments.all())
    new_effective_accrual = Decimal(locked_accrual.amount) + current_accrual_adjustments + amount
    if new_effective_accrual < _ZERO:
        raise CashInvariantError("Adjustment would make partner accrual negative")

    new_total_allocated = allocated_to_partners(locked_receipt) + amount
    available = available_for_distribution(locked_receipt)
    if new_total_allocated > available:
        raise CashInvariantError("Adjustment would allocate more partner cash than is available")

    return PartnerAccrualAdjustment.objects.create(
        partner_accrual=locked_accrual,
        amount=amount,
        reason_code=reason_code,
        evidence_reference=evidence_reference,
    )
