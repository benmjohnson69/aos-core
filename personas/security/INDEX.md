# Security Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** Organizational security, compliance posture, and third-party risk — NOT code-level security

## How to use

```yaml
persona_libraries:
  - security
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `threat_modeler` | SKEPTIC | sonnet | Org/product threat modeling, insider risk, vendor access, off-boarding | M&A security diligence, org risk assessment |
| `compliance_assessor` | SKEPTIC | sonnet | SOC 2/CMMC/HIPAA scope, evidence vs. attestation, audit-mode theater | Compliance diligence, regulatory readiness |
| `vendor_risk_analyst` | SKEPTIC | sonnet | SaaS sprawl, shadow IT, DPAs, auto-renewal traps, sub-processor exposure | Vendor inventory, third-party risk |

## Peer-attack graph (security pack)

```
threat_modeler       → steelman_defender   (defenders/)
compliance_assessor  → feasibility_advocate (defenders/)
vendor_risk_analyst  → feasibility_advocate (defenders/)

steelman_defender    → threat_modeler      (this pack)
feasibility_advocate → compliance_assessor, vendor_risk_analyst (this pack)
```

Cross-pack attacks:
- `steelman_defender` (defenders/) argues compensating controls credit for `threat_modeler` findings
- `feasibility_advocate` (defenders/) challenges gold-plating in `compliance_assessor` remediation specs and alternative paths for `vendor_risk_analyst` "cannot be done" findings

## Recommended wave configuration (security diligence)

**Wave 1:** `threat_modeler` + `vendor_risk_analyst` (parallel — independent evidence bases)
**Wave 2:** `compliance_assessor` (informed by Wave 1 findings on access and vendor scope)
**Wave 3:** `steelman_defender` + `feasibility_advocate` (defenders/) — challenge and remediation-path
**Reconciliation:** opus

## Craft-score reference

| Scout ID | craft_score |
|---|---|
| `threat_modeler` | 8.5 |
| `compliance_assessor` | 8.5 |
| `vendor_risk_analyst` | 8.5 |

## Boundary note

This pack covers **organizational** threat modeling, compliance posture, and vendor risk. It does NOT cover code-level security (SAST, DAST, dependency vulnerability scanning) — those belong in a `coding/` pack with a security-auditor scout focused on application-layer risk.

## Related packs

- `legal/` — `contract_risk_reader` (customer contract security representations), `ip_licensing_skeptic` (OSS compliance)
- `defenders/` — mandatory complement; skeptic-only security diligence without a defender produces risk lists that cannot be prioritized
