# Supporting additional Minecraft protocol versions

The codebase is laid out so a new protocol number is a sibling
directory copy, not a global refactor. This guide walks through the
end-to-end steps to add support for one (using protocol 765 as the
worked example) without breaking the existing v763 surface.

## Constitutional invariants

Before changing anything:

- Versions are tracked by **protocol number**, never by game version
  string. `v763` is Minecraft 1.20.1; `v764` is 1.20.2; `v765` is
  1.20.3 / 1.20.4; etc.
- Per-version files live under the matching `vN` subdirectory. There
  are no `v763`-specific imports outside `protocol/v763/`. The same
  rule applies to a new version: keep its packet IDs, type IDs, and
  state machine entirely inside its own folder.
- Cross-version code (Connection, Bot, World, codec primitives) is
  parameterised by `ProtocolVersion`. It picks the right packet
  registry at construction time, not by build feature.

## Step 1: clone the per-version tree

```bash
# Python reference.
cp -r python/minecraft_bot/protocol/v763 python/minecraft_bot/protocol/v765
# Rust standalone crate.
cp -r rust/src/protocol/v763 rust/src/protocol/v765
# Per-version protocol data (block table, registries, golden bytes).
cp -r protocol-data/v763 protocol-data/v765
```

Edit the `PROTOCOL_VERSION` constant at the top of each
`v765/states.py`, `v765/__init__.py`, and the matching Rust
`mod.rs`. Run `git grep '763'` inside each `v765/` subtree to spot
references that need to be renumbered.

## Step 2: update the version registry

The Rust crate keeps a central list of supported protocol versions
in `rust/src/protocol/mod.rs`:

```rust
pub const V_1_20_1: ProtocolVersion = ProtocolVersion { number: 763, ... };
pub const V_1_20_4: ProtocolVersion = ProtocolVersion { number: 765, ... };
```

Add an entry for the new version next to the existing ones. The
Python reference uses a parallel list in `python/minecraft_bot/protocol/__init__.py`.

If `Connection` should now pick the new version by default,
update `Connection::offline`'s `version` field. Otherwise add a
`with_version(...)` builder method so callers opt in.

## Step 3: regenerate the protocol-data files

Each `protocol-data/vN/` folder contains:

- `block_states.json`: full state-ID to block-name table (~24 000
  entries on 1.20.1). Generated from PrismarineJS minecraft-data.
- `registries.json` and friends: entity types, item IDs, particle
  codecs, sound IDs.
- `golden_bytes/`: captured packet samples for the cross-check tool.

Regenerate via the scraping scripts in `tools/`:

```bash
python tools/fetch_block_states.py --protocol 765
python tools/fetch_entity_metadata.py --protocol 765
python tools/fetch_foods.py --protocol 765
```

These scripts read from the `PrismarineJS/minecraft-data` GitHub
repo, downsample to the fields the framework actually uses, and
emit the per-version JSON. The cross-check tool consumes the
golden-byte fixtures; you can seed them from a live capture
(`tools/capture_session.py`) or hand-author them for the few
edge-case packets that lack PrismarineJS coverage.

## Step 4: diff the packet schemas

Between protocol numbers Mojang typically:

- Adds, removes, or re-numbers packet IDs.
- Changes one or two field types per packet (e.g., a varint becomes
  a varlong; an optional NBT becomes required; a coordinate adds a
  `yaw` component).
- Renames a packet (rare).

For each `v765/packets/<state>/<dir>/<name>.py`, diff against the
v763 source, apply the wire-format changes, and re-run the codegen
to regenerate the Rust mirror:

```bash
python tools/generate_rust_packets.py --version 765
```

Currently the generator is hard-coded to v763. The `--version`
flag is the targeted extension; update
`tools/generate_rust_packets.py`'s `PROTOCOL_NUMBER` constant when
you add it.

If a packet was renamed, do the rename in both Python and Rust
trees; the per-packet-per-file rule (`one packet, one file`) makes
the diff a `git mv` plus content edit.

## Step 5: cross-check parity

For every packet listed in
`protocol-data/v765/golden_bytes/packets/<dir>/<name>.json`, the
three encoders (Python, standalone Rust, accel) must produce
identical bytes:

```bash
cargo build --release --manifest-path rust/Cargo.toml --example encode_one
python tools/cross_check.py --accel
```

Zero discrepancies expected. If a fixture mismatches, the encoder
that diverges from the golden bytes is wrong; fix it before
shipping.

## Step 6: update the Bot facade and the PyO3 wrapper

The high-level Bot picks its protocol via `Connection`:

```python
# python/minecraft_bot/bot.py
bot = Bot.offline(host, port, name, version=V_1_20_4)
```

```rust
// rust/src/bot.rs
let bot = Bot::offline(host, port, username).with_version(V_1_20_4);
```

The PyO3 wrapper inherits the version from the underlying
`Connection`; no facade changes are needed beyond passing the
version through.

The packet dispatcher in `Bot::connect` matches on packet IDs.
When IDs differ between versions, the dispatcher needs a version
check or per-version match arm. The cleanest approach is a small
indirection layer: `protocol::v765::ids::MAP_CHUNK` plus a generic
dispatcher driven by named constants rather than literal `0x24`.

## Step 7: live-test on a matching server

A protocol number is only validated against a live server speaking
that protocol. For 1.20.4:

- Run Paper 1.20.4 alongside the existing Paper 1.20.1.
- Update `tests/python/conftest.py` to route version-tagged tests
  to the matching server port.
- Run the existing live integration suite under the new version.

## Step 8: cross-version sanity tests

Add a parity test that connects to two servers in sequence (v763
and v765) under both backends and verifies the same Bot script
produces server-equivalent behaviour on each. The
`tests/python/integration/` tree gets a new file:

```
tests/python/integration/test_multi_version_smoke.py
```

with a `@pytest.mark.parametrize("version", [V_1_20_1, V_1_20_4])`
matrix.

## Worked example status

| Version | Python tree | Rust tree | Live-tested |
|---------|-------------|-----------|-------------|
| 763 (1.20.1) | yes | yes | yes (Paper 1.20.1 at the project test arena) |
| 765 (1.20.4) | not yet | not yet | not yet |

Adding 765 is a follow-on milestone; the layout above is the path
to take. The constitution and the directory structure already
enforce the multi-version invariants; the actual port is `cp`
plus the per-packet schema diff.

## Why the layout supports this

The cross-language byte parity gate (the three-way cross-check) is
re-runnable per version. The Bot facade and World cache are
protocol-agnostic at the type level; they just need the right
packet IDs to dispatch on. The 176 packets per protocol live in
their own files, so a wire-format change to one packet is a one
file edit, not a global refactor.
