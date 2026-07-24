# Deal Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** M&A due diligence — financial, commercial, structural, integration, and integration risk

## How to use

In a v1.0 mission.yaml, reference this library via:

```yaml
persona_libraries:
  - deal
```

Then in the waves block, reference scouts by ID:

```yaml
waves:
  - n: 1
    scouts:
      - id: financial_analyst
        frame: SKEPTIC
        model: opus
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `financial_analyst` | SKEPTIC | opus | QoE, EBITDA normalization, revenue quality, WC, DSO | Financial diligence, QoE review |
| `valuation_deal_structure_skeptic` | SKEPTIC | sonnet | Earnout mechanics, seller note traps, equity roll, escrow | Deal structuring, term-sheet review |
| `integration_risk_assessor` | SKEPTIC | sonnet | 100-day plan, key-person retention, TSA, client churn | Post-close integration planning |
| `gtm_market_analyst` | SKEPTIC | sonnet | TAM/SAM/SOM, channel fit, competitive moat, CAC, NRR | Commercial diligence, market thesis |

## Peer-attack graph (deal pack)

```
financial_analyst          → steelman_defender    (defenders/)
valuation_deal_structure_skeptic → steelman_defender (defenders/)
integration_risk_assessor  → feasibility_advocate (defenders/)
gtm_market_analyst         → steelman_defender    (defenders/)

steelman_defender          → financial_analyst    (this pack)
feasibility_advocate       → integration_risk_assessor (this pack)
```

Cross-pack attacks:
- `steelman_defender` (defenders/) attacks `financial_analyst`, `valuation_deal_structure_skeptic`, and `gtm_market_analyst`
- `feasibility_advocate` (defenders/) attacks `integration_risk_assessor`

## Recommended wave configuration (M&A diligence)

**Wave 1 (financial foundation):** `financial_analyst` + `valuation_deal_structure_skeptic`
**Wave 2 (commercial + integration):** `gtm_market_analyst` + `integration_risk_assessor`
**Wave 3 (defender challenge):** `steelman_defender` + `feasibility_advocate` (from defenders/)
**Reconciliation:** opus

## Craft-score reference

All 4 scouts passed persona-author craft standard with craft_score ≥ 8.5.

| Scout ID | craft_score |
|---|---|
| `financial_analyst` | 8.5 |
| `valuation_deal_structure_skeptic` | 8.5 |
| `integration_risk_assessor` | 8.5 |
| `gtm_market_analyst` | 8.5 |

## Related packs (cross-library attack targets)

- `defenders/` — `steelman_defender` (opus) and `feasibility_advocate` (sonnet); attack deal skeptics
- `legal/` — `contract_risk_reader` and `ip_licensing_skeptic`; extend financial diligence into contractual and IP risk
- `security/` — `threat_modeler`, `compliance_assessor`, `vendor_risk_analyst`; extend into technical diligence

## Known gaps

No DEFENDER frame in this pack — `steelman_defender` from defenders/ fills that role. If running deal diligence without the defenders/ pack, consider authoring a deal-specific defender or using `feasibility_advocate` with a modified peer-attack target.
