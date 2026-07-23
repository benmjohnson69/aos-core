# NOTICE — Authorship & Provenance

**aos-core** is a personal project of Benjamin Johnson, released under the MIT License (see LICENSE).

## Provenance

- **Lineage predates any employment use.** aos-core is an extraction of content-free mechanisms from
  AOS, the author's personal AI operating system, whose direct lineage runs BenGPT (personal memory
  vault, ~2024) → NOS (Notion-based OS) → AOS v1/v2/v3 (2025–2026). The design patterns embodied here
  (turn-0 identity injection, pre/post-compaction state snapshotting, write-time lint enforcement,
  prior-fix surfacing) were developed within that personal project.
- **Personal time and equipment.** Authored on the author's personally owned hardware, on personal
  time. The complete development history exists as git history on that hardware.
- **No employer information.** The artifact is content-free by construction: it contains no employer
  confidential information, no employer code, and no personal data. All identity/memory content is
  loaded at runtime from a separate, user-owned directory (`~/.aos-private/`) that is not part of,
  and is never distributed with, this software.

## Verifying these claims mechanically

Each claim above is checkable, not asserted:

```bash
# 1. Content-free: no personal or employer-specific strings in the artifact
grep -ri "<any name, employer, or personal term>" .    # returns nothing

# 2. Development history: authorship timestamps precede any workplace installation
git log --reverse --format="%ai %h %s" | head

# 3. Runtime separation: private content is load-if-present, external to the package
grep -n "aos-private" lib/private_layer.py README.md
```

## Scope of this release

This repository contains only the mechanism layer (hooks, skills, tools, manifests). It does not
contain — and has never contained — any private bundle, identity content, transcripts, or data of any
person or organization.
