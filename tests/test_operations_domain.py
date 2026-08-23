from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.operations.models import (
    Advertiser,
    AttributionSnapshot,
    CashReceipt,
    ConsentEvidence,
    ConsentTextVersion,
    Lead,
    LeadStatus,
    Offer,
    OfferTermsVersion,
    Partner,
    PartnerOfferTerms,
    PartnerSource,
    StatusEvent,
)
from apps.operations.services import (
    CashInvariantError,
    allocated_to_partners,
    append_status_event,
    available_for_distribution,
    create_cash_adjustment,
    create_partner_accrual,
    create_partner_accrual_adjustment,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


@pytest.fixture
def domain() -> dict[str, object]:
    partner = Partner.objects.create(
        code="dealer-one",
        name="Dealer One",
        status=Partner.Status.ACTIVE,
    )
    source = PartnerSource.objects.create(
        partner=partner,
        code="embedded-sales",
        source_type=PartnerSource.SourceType.EMBEDDED,
        status=PartnerSource.Status.APPROVED,
        allowed_channels=["co_branded_link"],
        monthly_cap=20,
        approved_at=timezone.now(),
    )
    advertiser = Advertiser.objects.create(
        code="lessor-one",
        name="Lessor One",
        status=Advertiser.Status.COMPATIBLE,
    )
    offer = Offer.objects.create(
        advertiser=advertiser,
        code="commercial-vehicle-leasing",
        name="Commercial vehicle leasing",
        product_type=Offer.ProductType.LEASING,
        status=Offer.Status.ACTIVE,
    )
    offer_terms = OfferTermsVersion.objects.create(
        offer=offer,
        version=1,
        published_at=timezone.now(),
        target_action="asset_delivered",
        payout_model=OfferTermsVersion.PayoutModel.PERCENT,
        payout_rate=Decimal("2.0000"),
        hold_days=3,
        dedup_window_days=90,
        attribution_window_days=90,
        allow_own_landing=True,
        allow_professional_partners=True,
        allow_paid_nonbrand_search=False,
        allow_rerouting=False,
        terms_digest=DIGEST_A,
        rules={"asset_types": ["light_commercial_vehicle"]},
    )
    partner_terms = PartnerOfferTerms.objects.create(
        partner=partner,
        offer_terms_version=offer_terms,
        version=1,
        published_at=timezone.now(),
        reward_model=PartnerOfferTerms.RewardModel.PERCENT_OF_RECEIPT,
        receipt_share_percent=Decimal("60.0000"),
        hold_days=0,
        terms_digest=DIGEST_B,
    )
    subject_ref = uuid.uuid4()
    lead = Lead.objects.create(
        offer_terms_version=offer_terms,
        partner_source=source,
        direct_source_code="",
        client_subject_ref=subject_ref,
        organization_fingerprint=DIGEST_B,
        contact_fingerprint=DIGEST_C,
        commercial_context={
            "asset_type": "light_commercial_vehicle",
            "amount_band": "3m_5m",
        },
        is_test=True,
    )
    return {
        "partner": partner,
        "source": source,
        "advertiser": advertiser,
        "offer": offer,
        "offer_terms": offer_terms,
        "partner_terms": partner_terms,
        "lead": lead,
        "subject_ref": subject_ref,
    }


@pytest.mark.django_db
def test_published_offer_terms_are_immutable(domain: dict[str, object]) -> None:
    offer_terms = domain["offer_terms"]
    assert isinstance(offer_terms, OfferTermsVersion)

    offer_terms.target_action = "changed_after_publication"
    with pytest.raises(ValidationError, match="published version"):
        offer_terms.save()

    with pytest.raises(ValidationError, match="published version"):
        offer_terms.delete()


@pytest.mark.django_db
def test_attribution_snapshot_is_append_only(domain: dict[str, object]) -> None:
    lead = domain["lead"]
    source = domain["source"]
    partner = domain["partner"]
    assert isinstance(lead, Lead)
    assert isinstance(source, PartnerSource)
    assert isinstance(partner, Partner)

    snapshot = AttributionSnapshot.objects.create(
        lead=lead,
        partner_id_snapshot=partner.id,
        partner_source_id_snapshot=source.id,
        click_id="click-001",
        signed_token_digest=DIGEST_A,
        utm_source="partner",
        utm_medium="embedded",
        landing_variant="vehicle-v1",
        referrer_domain="dealer.example",
        first_touch_at=timezone.now(),
    )
    snapshot.click_id = "rewritten"

    with pytest.raises(ValidationError, match="append-only"):
        snapshot.save()
    with pytest.raises(ValidationError, match="append-only"):
        snapshot.delete()


@pytest.mark.django_db
def test_status_service_appends_sequence_and_updates_projection(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    assert isinstance(lead, Lead)

    first = append_status_event(
        lead=lead,
        status_code=LeadStatus.LEAD_CREATED,
        actor_type=StatusEvent.ActorType.SYSTEM,
    )
    second = append_status_event(
        lead=lead,
        status_code=LeadStatus.PHONE_VERIFIED,
        actor_type=StatusEvent.ActorType.OPERATOR,
        actor_ref="operator:test",
    )

    assert first.sequence == 1
    assert second.sequence == 2
    lead.refresh_from_db()
    assert lead.current_status == LeadStatus.PHONE_VERIFIED
    assert lead.current_status_at == second.occurred_at

    first.reason_code = "rewritten"
    with pytest.raises(ValidationError, match="append-only"):
        first.save()


@pytest.mark.django_db
def test_consent_evidence_requires_published_exact_version(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    subject_ref = domain["subject_ref"]
    assert isinstance(lead, Lead)
    assert isinstance(subject_ref, uuid.UUID)

    consent_text = ConsentTextVersion.objects.create(
        consent_type=ConsentTextVersion.ConsentType.TRANSFER,
        version=1,
        text_digest=DIGEST_A,
        public_reference="/legal/consent/transfer/v1",
        published_at=timezone.now(),
    )
    evidence = ConsentEvidence.objects.create(
        lead=lead,
        consent_text_version=consent_text,
        confirmed_at=timezone.now(),
        channel=ConsentEvidence.Channel.SMS_OTP,
        subject_ref=subject_ref,
        evidence_digest=DIGEST_B,
        ip_digest=DIGEST_C,
        user_agent_digest=DIGEST_A,
        recipient_list_version="lessors-v1",
        proof_reference="vault://consents/test-001",
    )
    evidence.proof_reference = "vault://consents/rewritten"

    with pytest.raises(ValidationError, match="append-only"):
        evidence.save()


@pytest.mark.django_db
def test_operational_json_rejects_raw_pii_keys(domain: dict[str, object]) -> None:
    lead = domain["lead"]
    assert isinstance(lead, Lead)

    lead.commercial_context = {"asset_type": "truck", "phone": "+70000000000"}
    with pytest.raises(ValidationError, match="Sensitive JSON key"):
        lead.save()


@pytest.mark.django_db
def test_partner_accrual_cannot_exceed_distributable_cash(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    advertiser = domain["advertiser"]
    partner = domain["partner"]
    partner_terms = domain["partner_terms"]
    assert isinstance(lead, Lead)
    assert isinstance(advertiser, Advertiser)
    assert isinstance(partner, Partner)
    assert isinstance(partner_terms, PartnerOfferTerms)

    receipt = CashReceipt.objects.create(
        lead=lead,
        advertiser=advertiser,
        external_reference="cash-001",
        gross_amount=Decimal("100.00"),
        distributable_amount=Decimal("100.00"),
        currency="RUB",
        evidence_reference="registry://cash-001",
    )

    with pytest.raises(CashInvariantError, match="exceeds available cash"):
        create_partner_accrual(
            cash_receipt=receipt,
            partner=partner,
            partner_offer_terms=partner_terms,
            amount=Decimal("110.00"),
            rate_basis="invalid over-allocation",
        )

    accrual = create_partner_accrual(
        cash_receipt=receipt,
        partner=partner,
        partner_offer_terms=partner_terms,
        amount=Decimal("60.00"),
        rate_basis="60% of distributable receipt",
    )

    assert available_for_distribution(receipt) == Decimal("100.00")
    assert allocated_to_partners(receipt) == Decimal("60.00")
    assert accrual.amount == Decimal("60.00")


@pytest.mark.django_db
def test_adjustments_preserve_cash_and_accrual_invariants(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    advertiser = domain["advertiser"]
    partner = domain["partner"]
    partner_terms = domain["partner_terms"]
    assert isinstance(lead, Lead)
    assert isinstance(advertiser, Advertiser)
    assert isinstance(partner, Partner)
    assert isinstance(partner_terms, PartnerOfferTerms)

    receipt = CashReceipt.objects.create(
        lead=lead,
        advertiser=advertiser,
        external_reference="cash-002",
        gross_amount=Decimal("100.00"),
        distributable_amount=Decimal("100.00"),
        currency="RUB",
        evidence_reference="registry://cash-002",
    )
    accrual = create_partner_accrual(
        cash_receipt=receipt,
        partner=partner,
        partner_offer_terms=partner_terms,
        amount=Decimal("60.00"),
        rate_basis="60% of distributable receipt",
    )

    with pytest.raises(CashInvariantError, match="below existing partner allocations"):
        create_cash_adjustment(
            cash_receipt=receipt,
            amount=Decimal("-50.00"),
            reason_code="advertiser_clawback",
            evidence_reference="registry://adjustment-blocked",
        )

    negative_adjustment = create_partner_accrual_adjustment(
        partner_accrual=accrual,
        amount=Decimal("-10.00"),
        reason_code="partner_correction",
        evidence_reference="registry://partner-adjustment-001",
    )
    assert negative_adjustment.amount == Decimal("-10.00")
    assert allocated_to_partners(receipt) == Decimal("50.00")

    cash_adjustment = create_cash_adjustment(
        cash_receipt=receipt,
        amount=Decimal("-50.00"),
        reason_code="advertiser_clawback",
        evidence_reference="registry://cash-adjustment-001",
    )
    assert cash_adjustment.amount == Decimal("-50.00")
    assert available_for_distribution(receipt) == Decimal("50.00")

    with pytest.raises(CashInvariantError, match="allocate more partner cash"):
        create_partner_accrual_adjustment(
            partner_accrual=accrual,
            amount=Decimal("1.00"),
            reason_code="invalid_positive_correction",
            evidence_reference="registry://partner-adjustment-blocked",
        )


@pytest.mark.django_db
def test_offer_and_partner_terms_reject_ambiguous_payout_shapes(
    domain: dict[str, object],
) -> None:
    offer = domain["offer"]
    partner = domain["partner"]
    assert isinstance(offer, Offer)
    assert isinstance(partner, Partner)

    with pytest.raises(ValidationError, match="requires an amount"):
        OfferTermsVersion.objects.create(
            offer=offer,
            version=2,
            target_action="asset_delivered",
            payout_model=OfferTermsVersion.PayoutModel.FIXED,
            terms_digest=DIGEST_C,
        )

    draft_offer_terms = OfferTermsVersion.objects.create(
        offer=offer,
        version=3,
        target_action="asset_delivered",
        payout_model=OfferTermsVersion.PayoutModel.FIXED,
        payout_amount=Decimal("100.00"),
        terms_digest=DIGEST_C,
    )
    with pytest.raises(ValidationError, match="before advertiser terms"):
        PartnerOfferTerms.objects.create(
            partner=partner,
            offer_terms_version=draft_offer_terms,
            version=1,
            published_at=timezone.now(),
            reward_model=PartnerOfferTerms.RewardModel.FIXED,
            fixed_amount=Decimal("50.00"),
            terms_digest=DIGEST_A,
        )


@pytest.mark.django_db
def test_lead_identity_and_status_projection_cannot_be_rewritten(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    assert isinstance(lead, Lead)

    lead.contact_fingerprint = DIGEST_A
    with pytest.raises(ValidationError, match="Immutable lead fields"):
        lead.save()

    lead.refresh_from_db()
    append_status_event(
        lead=lead,
        status_code=LeadStatus.LEAD_CREATED,
        actor_type=StatusEvent.ActorType.SYSTEM,
    )
    lead.refresh_from_db()
    lead.current_status = LeadStatus.APPROVED
    with pytest.raises(ValidationError, match="Immutable lead fields"):
        lead.save()


@pytest.mark.django_db
def test_direct_lead_attribution_rejects_partner_snapshots(
    domain: dict[str, object],
) -> None:
    offer_terms = domain["offer_terms"]
    partner = domain["partner"]
    source = domain["source"]
    assert isinstance(offer_terms, OfferTermsVersion)
    assert isinstance(partner, Partner)
    assert isinstance(source, PartnerSource)

    direct_lead = Lead.objects.create(
        offer_terms_version=offer_terms,
        direct_source_code="control-search",
        client_subject_ref=uuid.uuid4(),
        organization_fingerprint=DIGEST_A,
        contact_fingerprint=DIGEST_B,
        commercial_context={"asset_type": "light_commercial_vehicle"},
        is_test=True,
    )
    with pytest.raises(ValidationError, match="must not contain partner snapshots"):
        AttributionSnapshot.objects.create(
            lead=direct_lead,
            partner_id_snapshot=partner.id,
            partner_source_id_snapshot=source.id,
            click_id="direct-click-001",
            signed_token_digest=DIGEST_C,
            first_touch_at=timezone.now(),
        )


@pytest.mark.django_db
def test_cash_receipt_advertiser_must_match_the_lead_offer(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    assert isinstance(lead, Lead)
    wrong_advertiser = Advertiser.objects.create(
        code="wrong-lessor",
        name="Wrong Lessor",
        status=Advertiser.Status.COMPATIBLE,
    )

    with pytest.raises(ValidationError, match="does not match the lead offer"):
        CashReceipt.objects.create(
            lead=lead,
            advertiser=wrong_advertiser,
            external_reference="wrong-cash-001",
            gross_amount=Decimal("100.00"),
            distributable_amount=Decimal("100.00"),
            currency="RUB",
            evidence_reference="registry://wrong-cash-001",
        )


@pytest.mark.django_db
def test_partner_accrual_must_match_the_original_lead_source(
    domain: dict[str, object],
) -> None:
    lead = domain["lead"]
    advertiser = domain["advertiser"]
    offer_terms = domain["offer_terms"]
    assert isinstance(lead, Lead)
    assert isinstance(advertiser, Advertiser)
    assert isinstance(offer_terms, OfferTermsVersion)

    other_partner = Partner.objects.create(
        code="other-dealer",
        name="Other Dealer",
        status=Partner.Status.ACTIVE,
    )
    other_terms = PartnerOfferTerms.objects.create(
        partner=other_partner,
        offer_terms_version=offer_terms,
        version=1,
        published_at=timezone.now(),
        reward_model=PartnerOfferTerms.RewardModel.FIXED,
        fixed_amount=Decimal("10.00"),
        terms_digest=DIGEST_C,
    )
    receipt = CashReceipt.objects.create(
        lead=lead,
        advertiser=advertiser,
        external_reference="cash-source-mismatch",
        gross_amount=Decimal("100.00"),
        distributable_amount=Decimal("100.00"),
        currency="RUB",
        evidence_reference="registry://cash-source-mismatch",
    )

    with pytest.raises(CashInvariantError, match="match the lead source"):
        create_partner_accrual(
            cash_receipt=receipt,
            partner=other_partner,
            partner_offer_terms=other_terms,
            amount=Decimal("10.00"),
            rate_basis="invalid source mismatch",
        )
