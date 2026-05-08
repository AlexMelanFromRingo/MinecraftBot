<!--
SYNC IMPACT REPORT
==================
Version change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification. Template tokens replaced with concrete project
principles, technology constraints, workflow rules, and governance.

Principles defined (all newly added):
  I.   Python Is the Source of Truth
  II.  One Packet, One File; Versions in Folders
  III. PyTorch-Style Composable API
  IV.  Bots Are Packet Sets, Not Entities
  V.   Live-Server Integration Testing (NON-NEGOTIABLE)
  VI.  Zero Runtime Dependencies in the Core
  VII. Observability and Determinism

Sections added:
  - Technology and Architecture Constraints
  - Development Workflow and Quality Gates
  - Governance

Sections removed: none (template placeholders only).

Templates audited:
  - .specify/templates/plan-template.md   ✅ aligned (Constitution Check section
    already references this constitution; principle list will load on next /speckit-plan).
  - .specify/templates/spec-template.md   ✅ aligned (no constitution-specific tokens).
  - .specify/templates/tasks-template.md  ✅ aligned (no constitution-specific tokens).
  - .specify/templates/checklist-template.md  ✅ aligned (no constitution-specific tokens).
  - CLAUDE.md                              ✅ aligned (only points to current plan;
    constitution is self-loading by Spec Kit commands).

Deferred items: none.
-->

# Minecraft Bot Framework Constitution

## Core Principles

### I. Python Is the Source of Truth

The Python implementation under `python/` is the canonical reference for every protocol
codec, packet, state machine, and high-level Bot API. Rust under `rust/` MUST achieve
byte-for-byte parity with the Python implementation; in any disagreement between the two,
the Python output observed against the live server is correct until proven otherwise.
The PyO3 bridge will eventually subsume the pure-Python core, but only after the Rust
implementation has matched the Python reference end-to-end and the Python API surface
is preserved unchanged from the user's perspective.

**Rationale**: Python iterates faster, is easier to debug live, and historically reached
correct behaviour first on this codebase. Forcing Rust to chase Python — not the
reverse — keeps the truth-source single and prevents architectural drift.

### II. One Packet, One File; Versions in Folders

Every wire-format packet (handshaking, status, login, configuration, play; both
clientbound and serverbound) MUST live in its own file at:

```
{python|rust}/.../protocol/v{N}/packets/{state}/{direction}/{snake_case_name}.{py|rs}
```

`{N}` is the **protocol number** (e.g., `v763` for Minecraft 1.20.1), never the game
version. Version-specific data tables (block-state ID ranges, registry IDs, particle
codecs, entity metadata schemas) are namespaced the same way. Cross-version reuse is
expressed via explicit re-exports or aliases — never by implicit overlap, never by
"this also works on protocol X" comments.

**Rationale**: Minecraft's wire protocol drifts unpredictably; future-you needs to be
able to (a) port a single packet to a new protocol number with a single file copy and
(b) read the diff between two protocol versions as a directory diff.

### III. PyTorch-Style Composable API

The high-level Bot API mirrors PyTorch's mental model:
- `Bot` is a stateful module composed of submodules (`movement`, `inventory`, `world`,
  `combat`, `look`, `effects`, `chat`, …) accessed as attributes.
- Behaviors (walk-to, attack, eat, follow) are callable units that compose; a complex
  behavior is built from simpler ones, not from string-matched method names.
- Observation snapshots are first-class values (frozen dataclasses or `#[pyclass]`-
  exposed structs) suitable for both human inspection and ML pipelines.
- Hooks (forward / pre / post / on_packet) are first-class subscriptions, not ad-hoc
  callbacks.

**Rationale**: A PyTorch-shaped surface is what the ML/agent users (the primary
audience) already know; reusing that mental model gets us composability for free and
removes the need to invent or document a new framework idiom.

### IV. Bots Are Packet Sets, Not Entities

A bot is the union of (a) a state derived from inbound packets and (b) a set of valid
outbound packet sequences. Every high-level action (`bot.walk_to`, `bot.attack`,
`bot.eat`, `bot.look_at`) MUST reduce to packets the protocol state machine accepts at
that moment. Client-side simulation (physics, pathfinding, NBT parsing) is permitted
only to **decide which packets to send** — never to fake state the server has not
confirmed.

**Rationale**: The bot exists on the server, not in our process. State invented locally
without a packet origin will diverge from the server and break in survival, anti-cheat,
or PvP scenarios. Treating the bot as packets keeps the contract honest and testable.

### V. Live-Server Integration Testing (NON-NEGOTIABLE)

Protocol-correctness and Bot API behaviour MUST be verified against a live Paper 1.20.1
server. Mock or fake servers are forbidden for protocol-level tests. Two test layers
are mandatory:

1. **Unit tests** for pure codecs (VarInt, NBT, BitSet, Slot, registries) using
   golden-byte fixtures derived from PrismarineJS `minecraft-data` and live captures.
2. **Integration tests** running against the configured Paper server (default
   `172.26.160.1:25565`, `online-mode=false`). Every Bot API method that touches the
   network ships with a passing integration test before the feature is considered done.

Block-state IDs, entity metadata schemas, and registry numbers are sourced from
`minecraft-data` first and confirmed by live-server probes when the doc-source and the
server disagree. The live-server probe is the final authority.

**Rationale**: A prior incident (memorialized in past project memory) had passing
mocked tests while the live behaviour broke; mocks reproduce only what their author
remembered to encode. The live server is cheap to run locally and removes that whole
class of false confidence.

### VI. Zero Runtime Dependencies in the Core

The Python core (`python/minecraft_bot/`) uses only the standard library: `asyncio`,
`struct`, `zlib`, `dataclasses`, `enum`, `socket`, `pathlib`, `logging`. Third-party
dependencies are permitted only inside opt-in adapters under `python/minecraft_bot/extras/`
or analogous subdirectories, declared as optional extras in `pyproject.toml`
(e.g., `pip install minecraft-bot[ml]`). The Rust core depends on `tokio`, `bytes`,
`flate2` (or stdlib equivalents) and a minimal NBT/serialization crate set; everything
ML- or RL-adjacent goes behind feature flags.

**Rationale**: This framework is a foundation other people will build on. A heavy
dependency tree limits adoption, multiplies version-conflict bugs, and makes the
"is this our code or theirs?" debugging question harder than it needs to be.

### VII. Observability and Determinism

Every inbound and outbound packet MUST be loggable at full byte fidelity (raw payload
plus decoded view) under a single logger name (`minecraft_bot.protocol`). Physics ticks
MUST be deterministic given a fixed seed and packet trace; given a captured session log
it MUST be possible to replay state evolution offline. Bot APIs MUST surface enough
state (`position`, `health`, `food`, `yaw`, `pitch`, `inventory`, `effects`, `entities`)
that an external observer can reproduce the bot's decisions without reading source.

**Rationale**: Long-running agent work (the project's main use case) fails in subtle
ways; you cannot debug what you cannot replay. Logging at the byte layer also doubles
as the data set for porting to new protocol versions.

## Technology and Architecture Constraints

- **Languages**: Python 3.11+ (required for modern `asyncio`, `dataclass(slots=True)`,
  `tomllib`); Rust stable, edition 2021+.
- **Async runtimes**: Python `asyncio`, Rust `tokio` (multi-thread by default).
- **Repo layout**: monorepo at `/home/young-developer/my_todo/MinecraftBot/` with
  top-level `python/` and `rust/` directories; shared `protocol-data/` for generated
  golden-byte fixtures and registry snapshots.
- **Versioning of protocol code**: by **protocol number** (e.g., `v763`). Initial scope
  is **only protocol 763 (Minecraft 1.20.1)**; the directory layout, however, is
  multi-version-ready from day one (no v763-specific imports outside `protocol/v763/`).
- **Authoritative protocol sources**, in order of precedence when sources disagree:
  1. Live Paper 1.20.1 server probe results.
  2. PrismarineJS `minecraft-data` (https://github.com/PrismarineJS/minecraft-data).
  3. minecraft.wiki (the Wiki.vg merge).
  4. Other client/server sources (read-only reference).
- **Default test target**: Paper 1.20.1, `online-mode=false`, `172.26.160.1:25565`.
  Server folder lives on the Windows host at
  `C:\Users\Alex_Melan\Desktop\Minecraft-MC-Server`.
- **Authentication**: offline-mode is the default and MUST stay supported; online-mode
  (Microsoft/Mojang auth) is optional and lives behind a feature flag/extra.
- **PyO3 future**: any new public API surface in Python or Rust MUST be representable
  on the FFI boundary (`Send + 'static`, no raw pointers, no non-Send futures crossing
  the boundary). API designs that cannot cross PyO3 are rejected at planning time.

## Development Workflow and Quality Gates

- **Spec Kit lifecycle is mandatory** for new features: `/speckit-specify` →
  `/speckit-clarify` (when ambiguity exists) → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. Each `/speckit-plan` MUST contain a Constitution Check section
  that explicitly evaluates compliance with every principle above.
- **Cross-language parity rule**: a feature is "done" only when (a) Python reference
  exists and passes integration tests, (b) a Rust parity ticket exists, (c) the Rust
  implementation matches the Python behaviour. Rust-only features are forbidden until
  the Python reference lands. (This codifies the prior `Trust python-mc over
  minecraft-rs` guidance from project memory.)
- **Per-packet shipping checklist**:
  1. File at `protocol/v{N}/packets/{state}/{direction}/{name}.py` (and `.rs`).
  2. Encode/decode unit test using a golden byte string sourced from `minecraft-data`
     or a live capture.
  3. Integration coverage if any Bot API method consumes or emits the packet.
- **Live-server smoke test** is REQUIRED before merging any change to physics,
  pathfinding, codecs, packet handlers, or the connection layer.
- **Memory hygiene**: project memory at `.claude/projects/-home-young-developer-my-todo-
  MinecraftBot/memory/` is the long-term context; user-profile / project-vision /
  feedback memories MUST be kept current — outdated memories are a deletion target,
  not a record.
- **Auto-commit hooks** (configured in `.specify/extensions.yml`) run after each
  Spec Kit phase; review the diff before accepting.

## Governance

This constitution supersedes ad-hoc style preferences and prior memory entries when
they conflict. In a conflict, the constitution wins; the conflicting memory or doc is
updated, not silently ignored.

**Amendments**:

- Any change to this file requires (a) a documented rationale in the Sync Impact
  Report, (b) a version bump per the rules below, and (c) a sweep of the dependent
  templates and runtime guidance docs to keep them in sync.
- Versioning follows semver:
  - **MAJOR** — a principle is removed or its meaning is redefined in a way that
    invalidates prior plans/specs.
  - **MINOR** — a new principle or section is added, or guidance is materially
    expanded.
  - **PATCH** — wording clarifications, typo fixes, non-semantic refinements.
- The `LAST_AMENDED_DATE` MUST equal the calendar date of the amendment in
  `YYYY-MM-DD`. The `RATIFICATION_DATE` is set once and never edited.

**Compliance review**:

- Every `/speckit-plan` execution MUST include a Constitution Check that evaluates
  the proposed plan against principles I–VII and either passes or carries an explicit
  justified deviation.
- A failing Constitution Check blocks `/speckit-tasks` and `/speckit-implement` until
  the plan is amended or a justified exception is recorded under the plan's
  Complexity Tracking section.

**Version**: 1.0.0 | **Ratified**: 2026-05-08 | **Last Amended**: 2026-05-08
