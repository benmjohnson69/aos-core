# Comms Persona Library — IHSD v1.0

**Seeded:** 2026-07-24 from persona-author batch run (back-half-lifecycle-2026-06-04)
**Domain:** Outbound communications review — brand voice fidelity, editorial gate, artifact consistency

## How to use

```yaml
persona_libraries:
  - comms
```

**Critical:** The `brand_voice_editor` scout requires a voice profile supplied at runtime. The profile must include: (1) five named voice attributes with behavioral descriptions, (2) banned register list, (3) one to two exemplar sentences. Without the profile, the scout blocks and requests it. Do not invoke without preparing the profile input.

## Scout Inventory

| Scout ID | Default Frame | Default Model | Domain | Best-fit mission types |
|---|---|---|---|---|
| `brand_voice_editor` | DEFENDER | sonnet | Brand voice fidelity measurement, banned-register detection, multi-artifact consistency, editorial gate | Outbound artifact review, proposal QA, communications audit |

## Peer-attack graph (comms pack)

```
brand_voice_editor  → gtm_market_analyst   (deal/ — voice fidelity is correct but audience calibration may be wrong)

gtm_market_analyst  → brand_voice_editor   (deal/ — attacks when message is on-voice but off-market)
```

Cross-pack attack rationale: the `gtm_market_analyst` (deal/) attacks `brand_voice_editor` when an artifact is voice-consistent but commercially misaligned — the message sounds right and says the wrong thing. The voice editor cannot detect this; the market analyst can.

## Craft-score reference

| Scout ID | craft_score |
|---|---|
| `brand_voice_editor` | 8.5 |

## Runtime profile format

Supply the voice profile as part of the mission input or wave prompt:

```
VOICE PROFILE — [Brand Name]
Attribute 1: [name] — [behavioral description]
Attribute 2: [name] — [behavioral description]
Attribute 3: [name] — [behavioral description]
Attribute 4: [name] — [behavioral description]
Attribute 5: [name] — [behavioral description]
Banned register: [list of phrases, constructions, or tones explicitly rejected]
Exemplar: "[sentence that demonstrates the voice in action]"
Exemplar: "[second sentence, optional]"
```

The scout will confirm ingestion before beginning evaluation. If the profile is absent or malformed, it will block and output the required format.

## Deployment pattern

The comms pack is not typically part of a standard M&A diligence IHSD run. It is designed for:
- Pre-send review of high-stakes outbound artifacts (proposals, executive briefs, press releases)
- Batch review of a content set for voice drift audit
- Post-rebrand consistency check across existing artifact library

Pair with `gtm_market_analyst` (deal/) when both voice fidelity and commercial messaging accuracy are in scope.

## Related packs

- `deal/` — `gtm_market_analyst` is the natural peer-attacker for this scout
- No other pack dependencies; comms is a standalone review pack
