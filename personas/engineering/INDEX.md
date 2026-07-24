# Engineering Persona Library — IHSD v1.0

**Seeded:** 2026-04-20 from AOS Entity Store v1 substrate mission (first canonical IHSD run)
**Provenance:** `governance/patterns/iterative_heterogeneous_specialists/scouts/` on AOS repo
**Mission context:** Single-user worldmodel substrate decision (SQLite + FAISS at 1.57M vectors)

## How to use

In a v1.0 mission.yaml, reference this library via:

```yaml
persona_libraries:
  - engineering
```

Then in the waves block, reference scouts by ID — the engine will load from `~/.claude/ihsd-personas/engineering/<scout_id>.md`:

```yaml
waves:
  - n: 1
    scouts:
      - id: bitemporal_db_specialist
        frame: SKEPTIC        # override library default
        model: opus
```

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `bitemporal_db_specialist` | SKEPTIC | opus | Bitemporal schema, valid_from/valid_to, point-in-time queries | Schema, audit, compliance |
| `cognitive_architecture_worldmodel_learner` | STANDARD | opus | Agent worldmodel construction, skill libraries, reflection | AI agent architecture |
| `event_sourcing_engineer` | STANDARD | sonnet | CQRS-lite, event logs, replay semantics | Event-driven systems |
| `fine_tuning_distillation_specialist` | DEFENDER | sonnet | DPO/ORPO/KTO on M-series, local evaluator training | ML infrastructure |
| `knowledge_graph_engineer` | DEFENDER | opus | Property graphs, triple stores, entity resolution | Knowledge graph, entity mgmt |
| `libsql_turso_litestream_specialist` | MINIMALIST | sonnet | SQLite-at-the-edge, replication, multi-writer limits | Distributed SQLite |
| `memory_architecture_researcher` | STANDARD | opus | Schema for fact vs interpretation, retrieval reconciliation | Memory system design |
| `postgres_pgvector_wizard` | DEFENDER | sonnet | pgvector, pgvectorscale, ParadeDB, Postgres extensions | Postgres substrate |
| `rag_systems_engineer` | SKEPTIC | opus | Hybrid retrieval (BM25+vector+graph), cross-encoder, rerank | Retrieval systems |
| `vector_db_specialist` | STANDARD | opus | FAISS vs Qdrant/Weaviate/pgvector/sqlite-vec at scale | Vector storage |

## Known gap (flagged in source mission)

The source roster referenced `systems_architect` as a peer-attack target for `event_sourcing_engineer` and `libsql_turso_litestream_specialist`, but no such scout was authored. If you're running an engineering IHSD and need a systems-architect voice, either:
- Author `systems_architect.md` via `persona-author` skill (suggested lens: "What's the substrate boundary, consistency model, idempotency key, and blast radius of every design decision?"), or
- Fold the role into `event_sourcing_engineer` + `libsql_turso_litestream_specialist` with peer-attack retargeted.

## Peer-attack pairings (from source mission — optional to preserve)

- `memory_architecture_researcher` ↔ `market_analyst` (schema purist vs product pragmatist) — cross-library
- `rag_systems_engineer` ↔ `bitemporal_db_specialist` (retrieval-at-query vs time-aware schema)
- `vector_db_specialist` ↔ `knowledge_graph_engineer` (embeddings vs structured graph)
- `event_sourcing_engineer` → `systems_architect` [MISSING]
- `libsql_turso_litestream_specialist` → `systems_architect` [MISSING]
- `fine_tuning_distillation_specialist` ↔ `product_ux_thinker` — cross-library (product/)
- `llm_judge_evaluator_specialist` ↔ `fine_tuning_distillation_specialist` — cross-library (research/)
- `cognitive_architecture_worldmodel_learner` ↔ `memory_architecture_researcher`

## Craft-score reference

All 10 scouts passed persona-author Stage 3 with craft_score ≥ 8. Individual `.craft_report.json` files live alongside the originals in the AOS repo at `governance/patterns/iterative_heterogeneous_specialists/scouts/`. They were intentionally not copied here to keep the library content-only.

## Related libraries

- `~/.claude/ihsd-personas/research/` — `anthropic_frontier_researcher`, `llm_judge_evaluator_specialist`
- `~/.claude/ihsd-personas/product/` — `market_analyst`, `product_ux_thinker`

## Deferred

`pkm_historian_local_first_activist` from the source mission does not fit any of the 5 seed library types (health / legal / ma-due-diligence / engineering / research). Held at source location pending a future `pkm` or `history` library. Its lens ("What 50-year pattern compounds vs fails?") is high-value for any long-lived-system mission — consider promoting to a general-purpose `history` library when spun up.
