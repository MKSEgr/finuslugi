# Advertiser Contact Matrix

Date: 2026-08-23

This matrix records current public programme signals and the official route for first contact. It does not replace written commercial terms.

## Priority A — leasing

| Candidate | Public fit | Public commercial signal | Public operational signal | Official first route | Gate 0 priority |
|---|---|---|---|---|---:|
| Альфа-Лизинг | Dedicated programme for legal entities; B2B products and equipment/transport | Up to 2%; public page shows average references around 48–100k RUB and payment up to 3–5 days after asset transfer | API integrations and application status visibility are publicly stated | Legal-entity programme page / partner registration | 1 |
| Европлан | Explicitly names brokers, lead generators, call centres, webmasters and agencies; legal entities and IP | Public page shows partner income tiers and average payment from 3 days; exact formula contractual | Reporting on applications/payments and partner cabinet | Partner programme page / partner cabinet | 2 |
| Реалист Банк | Agents/brokers; dealer employees and B2B sales specialists | Average public reference 100k RUB, up to 2%, payment within 30 days after asset transfer | Public process: application → manager → client information → reward | On-page programme application | 3 |
| CARCADE | Broker programme, different cooperation formats | Public marketing reference 150k+ RUB monthly; exact per-deal formula unknown | Automated CRM application transfer and EDI are publicly stated | Broker programme form | 4 |
| Балтийский лизинг | IP/LLC with active B2B sales; non-exclusive agency agreement | Public rate/payment not established | Agent/broker onboarding and training publicly stated | Agent/broker page / general partner contact | 5 |

### Official sources

- Альфа-Лизинг legal entities: https://alfaleasing.ru/affiliate-program-legal-entities/
- Альфа-Лизинг individuals/IP: https://alfaleasing.ru/affiliate-program/
- Европлан: https://europlan.ru/leasing/agprogram
- Европлан partner cabinet: https://agent.europlan.ru/
- Реалист Банк: https://realistbank.ru/business/leasing/affiliate-program/
- CARCADE: https://www.carcade.com/about/partners-program
- Балтийский лизинг: https://baltlease.ru/finansovyy-marketpleys/kak-stat-agentom/

## Priority B — fast-cash / working-capital layer

| Candidate | Public fit | Public commercial signal | Public operational signal | Official first route | Gate 0 priority |
|---|---|---|---|---|---:|
| Точка Банк | Accountants, lawyers, bloggers, webmasters, franchise networks and other business partners | Up to 20k fixed or revenue-share options; cross-sell rewards | Referral links, partner cabinet, application statuses and API token are publicly stated; programme also rewards referring other partners | Partner application / self-registration | 1 |
| ROWI | Financial brokers, tender agents, consultants and other SME finance participants | Monthly remuneration; public cases show recurring and one-off outcomes but are not guaranteed | Accreditation, agent cabinet, monthly act/payment process | Agent application / callback | 2 |
| ПСБ | RKO, acquiring, credit and salary projects | Monthly partner reward publicly stated; exact current terms require confirmation | Partner route publicly available | Official partner programme | 3 |

### Official sources

- Точка: https://tochka.com/partners/
- ROWI: https://rowi.com/agents/
- ПСБ: https://www.psbank.ru/business/partnerskaya-programma

## First-contact sequence

1. Submit the official programme application using only company/contact data required by the form.
2. During the callback, request the person responsible for broker/affiliate integration rather than an ordinary sales manager.
3. Send the discovery questionnaire from `docs/outreach/advertiser-first-contact.md`.
4. Record every written answer in a private scorecard; publish only non-confidential conclusions.
5. Do not send traffic, partner data or client data before Gate 0 is passed.

## Publicly confirmed positive signals

### Альфа-Лизинг

- dedicated legal-entity partner programme;
- public API integration claim;
- status visibility;
- high-ticket transport/equipment fit;
- fast payment after asset transfer.

### Европлан

- explicitly accepts lead generators, webmasters and agencies;
- legal entities/IP;
- partner reporting;
- public partner cabinet;
- broad national operation.

### Точка

- explicitly supports webmasters and professional referrers;
- referral links and API token;
- visible application statuses;
- an explicit second-level referral mechanism exists publicly, but its compatibility with the Finuslugi umbrella model must still be confirmed contractually.

### ROWI

- recurring monthly remuneration is structurally attractive;
- agent cabinet and monthly act process;
- products include factoring, guarantees and contract financing.

## Critical unknowns common to all candidates

- own/co-branded landing rights;
- exact professional partner/subagent model;
- paid non-brand search permission;
- brand bidding rules;
- dedup window and existing-client definition;
- attribution conflict rule;
- complete status/reason-code model;
- API/postback/export details;
- advertiser SLA;
- in-flight pipeline after termination;
- consent wording and data roles;
- ORД/ЕРИР responsibility;
- mandatory advertising deduction base;
- whether one rejected lead may be routed elsewhere.

## Initial outreach order

### Leasing

1. Альфа-Лизинг — strongest public technical signal (legal-entity programme + API/status visibility).
2. Европлан — strongest public distribution fit (lead generators/webmasters/agencies).
3. Реалист Банк — transparent public payout event and dealer/B2B fit.
4. CARCADE — useful CRM/EDI signal; commercial mechanics need discovery.
5. Балтийский лизинг — clear agency model; technical transparency is weaker publicly.

### Secondary layer

1. Точка — best public API/referral/status fit for fast validation.
2. ROWI — best recurring product hypothesis.
3. ПСБ — diversification after exact terms are confirmed.

## Stop condition

If two independent advertisers do not provide written confirmation of the intended customer path and professional partner distribution, development of partner-facing product functions remains blocked and the wedge must be changed.
