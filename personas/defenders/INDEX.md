# Defenders Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** Affirmative-case building, feasibility advocacy, and assumption-symmetry enforcement — cross-domain pack that pairs with any skeptic pack

## How to use

```yaml
persona_libraries:
  - defenders
```

The defenders pack is designed to be used in the final wave of any IHSD run that uses skeptic-heavy packs. Deploy after skeptic scouts have produced their findings; defenders respond to the actual findings, not hypothetical ones.

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `steelman_defender` | DEFENDER | opus | Strongest-case building, assumption-symmetry enforcement, build-vs-buy analysis, compensating control credit | Any mission with skeptic-dominant findings; M&A deal thesis defense |
| `feasibility_advocate` | DEFENDER | sonnet | Execution reality check, resource contention analysis, gold-plating detection, alternative path finding | Integration planning, remediation plan review, any plan-vs-reality gap |

## Peer-attack graph (defenders pack + all packs attacked)

The defenders pack attacks outward; all skeptic packs attack inward:

```
steelman_defender   → financial_analyst          (deal/)
steelman_defender   → valuation_deal_structure_skeptic (deal/)
steelman_defender   → gtm_market_analyst         (deal/)
steelman_defender   → contract_risk_reader       (legal/)
steelman_defender   → ip_licensing_skeptic       (legal/)
steelman_defender   → threat_modeler             (security/)
steelman_defender   → sre_reliability_skeptic    (ops/)

feasibility_advocate → integration_risk_assessor (deal/)
feasibility_advocate → compliance_assessor       (security/)
feasibility_advocate → vendor_risk_analyst       (security/)
feasibility_advocate → service_delivery_realist  (ops/)

financial_analyst          → steelman_defender   (attacks back)
integration_risk_assessor  → feasibility_advocate (attacks back)
```

## Deployment pattern

The defenders pack works best as a final-wave challenge, not an early-wave participant:

1. **Waves 1-N:** Skeptic scouts from domain packs (deal, security, legal, ops)
2. **Wave N+1:** `steelman_defender` + `feasibility_advocate` respond to the aggregated findings
3. **Reconciliation:** opus synthesizes the skeptic findings + defender challenges into the matrix

Do NOT deploy defenders in Wave 1 without prior skeptic findings to respond to — defenders without a specific target argument produce generic encouragement, not adversarial quality control.

## Craft-score reference

| Scout ID | craft_score |
|---|---|
| `steelman_defender` | 8.5 |
| `feasibility_advocate` | 8.5 |

## Model note

`steelman_defender` is assigned opus by default — the affirmative case requires the highest reasoning capability available to generate the strongest honest counter-argument to a multi-scout skeptic consensus. Do not downgrade to sonnet for cost savings; a weak steelman defense defeats the purpose of the exercise.

## Anti-pattern: defenders as optimism theater

The defenders pack is adversarial quality control on skeptic outputs, not cheerleading. A `steelman_defender` output that does not cite specific skeptic arguments and specific counter-evidence is theater. If the steelman cannot build a case with evidence, the deal thesis does not survive — that is the correct outcome. The defenders pack makes the skeptics stronger by forcing them to answer the best counter-argument, not by manufacturing reasons to proceed.
