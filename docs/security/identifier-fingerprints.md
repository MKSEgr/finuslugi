# Identifier Fingerprints

## Purpose

Operational deduplication and reconciliation sometimes require stable comparison of identifiers such as an organization tax number or a normalized contact. The operational ledger must not store the raw identifier and must not store a plain unsalted hash of a low-entropy value.

## Required construction

Use a versioned keyed fingerprint:

```text
fingerprint = HMAC-SHA-256(secret_key_version, namespace || 0x00 || normalized_value)
```

Where:

- `secret_key_version` selects a secret held outside the repository and database;
- `namespace` separates identifier types and environments, for example `prod:organization:inn` or `prod:contact:phone`;
- `normalized_value` is produced by a documented deterministic normalizer;
- the resulting lowercase hexadecimal digest is stored in the relevant fingerprint field;
- `fingerprint_key_version` is stored with the lead so historical comparisons remain explainable during key rotation.

A plain SHA-256 digest, a public salt, reversible encryption used as a lookup token, or a shared key committed to source control is not acceptable.

## Normalization

Normalization must be explicit and versioned in code or configuration.

Examples:

- organization identifier: digits only, validated expected length before fingerprinting;
- phone: canonical E.164 representation after country/number validation;
- email, if ever approved for deduplication: Unicode/domain normalization and lowercasing rules must be specified separately.

Invalid values must not be fingerprinted merely to make them fit the schema.

## Key management

- keys are generated with a cryptographically secure random source;
- keys live in a production secret manager or equivalent protected environment variable injection;
- repository, logs, CI output, database fixtures and analytics must never contain a real key;
- each environment uses different keys;
- access is limited to the service that creates or compares fingerprints;
- key rotation creates a new version rather than silently changing the meaning of stored digests;
- migration/re-fingerprinting, when required, runs as an audited privileged operation over the protected source data store.

## Separation from PII storage

The operational ledger stores only:

- opaque subject references;
- versioned HMAC fingerprints;
- commercial attributes approved by data minimisation review.

Raw phone numbers, organization identifiers, names, documents and consent proof artifacts belong in a separately reviewed protected store. Fingerprints reduce exposure but are still treated as security-sensitive pseudonymous data, not anonymous data.

## Application invariants

1. Lead identity fingerprints and `fingerprint_key_version` are immutable after lead creation.
2. Status projection updates cannot rewrite identity or attribution.
3. Raw identifiers are forbidden in JSON metadata and standard logs.
4. Dedup decisions record the rule/version and result, not the compared raw values.
5. Direct-source and partner-source attribution remain mutually exclusive.
6. A partner payout cannot be redirected by replacing a fingerprint, partner source or attribution snapshot.

## Tests and review

Before production collection:

- unit tests cover deterministic normalization and HMAC output for non-production test keys;
- tests prove namespace separation;
- tests prove different key versions produce different fingerprints;
- logs are inspected for accidental raw identifiers;
- a security review confirms key storage, access, rotation and incident response;
- legal review confirms the role and retention of the pseudonymous identifiers.

Production keys and real identifier fixtures are never used in CI.
