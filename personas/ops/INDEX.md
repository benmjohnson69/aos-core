# Ops Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** Cloud architecture fitness, SRE/reliability posture, and managed-services delivery economics

## How to use

```yaml
persona_libraries:
  - ops
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `cloud_architect` | DEFENDER | sonnet | Architecture fitness, cost shape, lock-in exposure, team-capability match | Cloud infrastructure assessment, post-acquisition architecture review |
| `sre_reliability_skeptic` | SKEPTIC | sonnet | SLO honesty, SPOF inventory, alert fatigue, on-call health, runbook reality | Reliability posture assessment, production readiness review |
| `service_delivery_realist` | SKEPTIC | sonnet | Technician utilization, ticket escalation economics, contract profitability, tool cost | Managed-services M&A diligence, delivery model assessment |

## Peer-attack graph (ops pack)

```
cloud_architect          → sre_reliability_skeptic  (this pack — DEFENDER attacks SKEPTIC)
sre_reliability_skeptic  → cloud_architect           (this pack — SKEPTIC attacks DEFENDER)
service_delivery_realist → feasibility_advocate      (defenders/)

feasibility_advocate     → service_delivery_realist  (this pack)
steelman_defender        → sre_reliability_skeptic   (this pack — credits compensating controls)
```

Internal peer-attack pair:
- `cloud_architect` ↔ `sre_reliability_skeptic`: architect argues for feasible path and team capability; SRE skeptic attacks SLO claims and SPOF gaps in the architecture

Cross-pack attacks:
- `feasibility_advocate` (defenders/) challenges minimum-viable paths for `service_delivery_realist` margin-compression findings
- `steelman_defender` (defenders/) credits compensating reliability controls flagged by `sre_reliability_skeptic`

## Recommended wave configuration (ops/infrastructure diligence)

**Wave 1:** `cloud_architect` + `sre_reliability_skeptic` (parallel — same evidence base, opposite frames)
**Wave 2:** `service_delivery_realist` (for managed-services targets; skip for pure SaaS)
**Wave 3:** `feasibility_advocate` + `steelman_defender` (defenders/)
**Reconciliation:** opus

## Craft-score reference

| Scout ID | craft_score |
|---|---|
| `cloud_architect` | 8.5 |
| `sre_reliability_skeptic` | 8.5 |
| `service_delivery_realist` | 8.5 |

## Frame diversity note

This pack has one DEFENDER (`cloud_architect`) and two SKEPTICs. For balanced frame coverage, pair with `steelman_defender` (opus) from defenders/. The `cloud_architect`'s DEFENDER frame covers architecture fitness but does not cover delivery economics or reliability posture — those require the two skeptic scouts to be tested against the defender frame from outside the pack.

## Related packs

- `deal/` — `integration_risk_assessor` (people/systems integration risk), `financial_analyst` (cost-shape findings feed into EBITDA normalization)
- `security/` — `threat_modeler` (overlaps on vendor access and privileged-account findings), `compliance_assessor` (cloud architecture scope maps to SOC 2 in-scope system boundary)
- `defenders/` — mandatory complement; the ops pack's two skeptics need defender challenge to produce actionable findings vs. walk recommendations
