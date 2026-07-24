# Legal Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** Commercial contract risk, IP ownership, and licensing obligations in M&A and technology contexts

## How to use

```yaml
persona_libraries:
  - legal
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `contract_risk_reader` | SKEPTIC | sonnet | MSA/SOW liability caps, termination asymmetry, auto-renewal, change-of-control consent | Commercial diligence, contract schedule review |
| `ip_licensing_skeptic` | SKEPTIC | sonnet | IP assignment chain, OSS license compliance, contractor work-product, founder pre-incorporation IP | IP diligence, technology acquisition |

## Peer-attack graph (legal pack)

```
contract_risk_reader  → steelman_defender   (defenders/)
ip_licensing_skeptic  → steelman_defender   (defenders/)

steelman_defender     → contract_risk_reader, ip_licensing_skeptic (this pack)
```

Cross-pack attacks:
- `steelman_defender` (defenders/) argues relationship-based flexibility on `contract_risk_reader` termination risk, and commercial license alternatives to `ip_licensing_skeptic` copyleft findings

## Recommended wave configuration (legal diligence)

**Wave 1:** `contract_risk_reader` + `ip_licensing_skeptic` (parallel — independent evidence bases)
**Wave 2:** `steelman_defender` (defenders/) — challenge both findings
**Reconciliation:** opus

## Craft-score reference

| Scout ID | craft_score |
|---|---|
| `contract_risk_reader` | 8.5 |
| `ip_licensing_skeptic` | 8.5 |

## Usage note: legal output is advisory

These scouts produce risk assessments and flag exposures. They do not produce legal opinions. Every material finding from these scouts should be reviewed by licensed legal counsel before being relied upon in a transaction.

## Related packs

- `deal/` — `financial_analyst` (revenue quality), `valuation_deal_structure_skeptic` (deal terms); legal risk amplifies financial risk when termination clauses affect ARR
- `security/` — `vendor_risk_analyst` (sub-processor DPA obligations connect to contract_risk_reader's security representation findings)
- `defenders/` — mandatory complement for remediation path analysis and gold-plating detection in remediation specs
