# MinecraftBot

A bot/agent framework for Minecraft Java Edition (1.20.1, protocol 763).
Python is the canonical reference implementation; Rust mirrors it for
performance, with a future PyO3 bridge that subsumes the Python core
while preserving its API surface.

## Status

**Active milestone**: `001-protocol-foundation`. Wire protocol fundament
(codecs, framer, packet registry, handshake/login/play state machine,
WireLog capture & replay).

See:
- **Active plan**: [`specs/001-protocol-foundation/plan.md`](./specs/001-protocol-foundation/plan.md)
- **Spec**: [`specs/001-protocol-foundation/spec.md`](./specs/001-protocol-foundation/spec.md)
- **Quickstart**: [`specs/001-protocol-foundation/quickstart.md`](./specs/001-protocol-foundation/quickstart.md)
- **Project constitution**: [`.specify/memory/constitution.md`](./.specify/memory/constitution.md)
- **Tasks**: [`specs/001-protocol-foundation/tasks.md`](./specs/001-protocol-foundation/tasks.md)

## Quick start

```bash
# Python (canonical)
pip install -e python/[dev]
pytest -q tests/python/unit              # offline unit tests
pytest -m live tests/python/integration  # live server required

# Rust (mirror)
cargo build --manifest-path rust/Cargo.toml
cargo test --manifest-path rust/Cargo.toml
cargo test --manifest-path rust/Cargo.toml --features live-smoke
```

For end-to-end usage examples (connect, observe, send, replay), see
`specs/001-protocol-foundation/quickstart.md`.

## Repository layout

```text
python/minecraft_bot/    # Canonical Python implementation
rust/                    # Parity Rust crate
protocol-data/v763/      # Pinned PrismarineJS minecraft-data + golden fixtures
tests/{python,rust}/     # Unit, integration, replay, perf tiers
tools/                   # Codegen, capture, cross-check scripts (not shipped)
specs/                   # Spec Kit deliverables
.specify/memory/         # Project constitution
```

## Test target

Paper 1.20.1, `online-mode=false`, default address `172.26.160.1:25565`.

## License

MIT.
