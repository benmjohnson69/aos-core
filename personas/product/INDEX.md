# Product Persona Library — IHSD v1.0

**Seeded:** 2026-04-20 (source: AOS Entity Store v1 substrate mission)
**Updated:** 2026-07-24 — INDEX created; market_analyst dedupe resolved (see §Dedupe log)
**Domain:** Product strategy, UX, and market analysis for AI-native and PKM tool decisions

## How to use

```yaml
persona_libraries:
  - product
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `market_analyst` | STANDARD | sonnet | AI-native PKM competitive landscape, data gravity, habituation loops, switching costs | Product competitive analysis, market positioning |
| `product_ux_thinker` | MINIMALIST | sonnet | Interaction loops, friction tax, compounding in user's favor, adjudication fatigue | Substrate design review, feature prioritization, UX audit |

## Peer-attack graph (product pack)

```
market_analyst       → memory_architecture_researcher  (engineering/ — cross-library)
product_ux_thinker   → bitemporal_db_specialist        (engineering/ — cross-library)

memory_architecture_researcher → market_analyst        (engineering/ attacks back)
bitemporal_db_specialist       → product_ux_thinker   (engineering/ attacks back)
```

Cross-pack attack rationale:
- `market_analyst` attacks `memory_architecture_researcher`: schema-purist vs. product-pragmatist (data gravity and distribution moats matter more than schema correctness for adoption)
- `product_ux_thinker` attacks `bitemporal_db_specialist`: user-visible behavior delta is the only valid measure of substrate value; temporal correctness that never surfaces to the user is engineering self-congratulation

## Craft-score reference

| Scout ID | craft_score | pattern_version |
|---|---|---|
| `market_analyst` | 9.0 | 3.1 |
| `product_ux_thinker` | 10.0 | 3.1 |

## Dedupe log

**Decision (2026-07-24):** `market-analyst.md` (hyphen) deleted; `market_analyst.md` (underscore) retained.

**Basis:** Files were byte-for-byte identical (confirmed via `diff` — no output). The underscore form (`market_analyst.md`) is the canonical naming convention across all persona packs (all other scouts use underscore: `product_ux_thinker.md`, `financial_analyst.md`, etc.). The hyphenated form was a naming drift artifact, not a distinct version. No content was lost. The canonical file `market_analyst.md` is the single source of truth.

## Related packs

- `engineering/` — primary cross-library peer-attack partners; product and engineering scouts are designed to challenge each other
- `deal/` — `gtm_market_analyst` (deal/) is the M&A commercial diligence variant of the market analyst role; distinct scout, distinct domain, complementary not overlapping
- `cross-domain/` — `theater-detector` and related scouts for claim-artifact gap detection
