"""Parity metadata — explicit allow-lists consumed by the 004 parity
test infrastructure (T011..T013).

These are intentionally Python-only; the Rust crate and accel facade
do not need a mirror.
"""

from __future__ import annotations

# Bot methods that are intentionally Python-only and must NOT exist on
# `minecraft_bot_accel.Bot`. The introspection test (T012) excludes
# them from the symmetric-difference check. Each entry needs a one-line
# justification in the comment above it, with a code-review trail.
#
# The LLM agent depends on external LLM API clients (anthropic, openai,
# etc.) which would violate Constitution VI if we re-exported them from
# the Rust crate. Keeping the loop and observation hooks Python-only is
# the intentional design.
PYTHON_ONLY_METHODS: frozenset[str] = frozenset({
    "_llm_chat_loop",
    "_llm_observe",
    # Event API (PyTorch-style observation queue + subscriber registry).
    # Lives on the Python-side Connection helper, not on the Bot itself
    # in accel — accel users register packet hooks via `on_packet`.
    "on",
    "subscribe",
    "unsubscribe",
    "drain_events",
    "next_event",
    # Connection-handle accessor — accel users go through the underlying
    # Bot's `connection` field which doesn't pyclass cleanly.
    "connection",
    "is_connected",
    # Auto-eat is a fire-and-forget asyncio task that doesn't make sense
    # to expose as a pyo3 method without a Python event loop bridge.
    # Users can build the same behaviour from the BT eat leaf.
    "auto_eat",
    "stop_auto_eat",
    # Furnace smelt — recipe-database-heavy, deferred polish item.
    "smelt",
    # Slash commands — Python ref uses raw chat-command packets.
    "command",
    # Physics tick (Python ref's bot.tick) — accel runs physics
    # internally inside walk_to; users don't tick manually.
    "tick",
})

# Methods that exist only on the accel facade — typically 003-era
# escape hatches or backend introspection helpers that have no
# meaningful Python equivalent.
ACCEL_ONLY_METHODS: frozenset[str] = frozenset({
    # 003 packet-hook API (lowercase, accel-specific).
    "on_packet",
    "clear_hooks",
    # 003 escape hatch for sending arbitrary serverbound bytes.
    "send_raw",
    # 003 dropping helper, superseded by `drop_item` in 004 but kept
    # for backwards-compat with existing scripts.
    "drop_held_item",
    # 003 diagnostic sliding walk used by perf tests.
    "walk_to_blind",
    # Backend introspection helpers exposed for tests.
    "loaded_chunk_count",
    "world",
    # `offline` is a classmethod constructor; introspection sees it
    # as a property descriptor — exclude until the collector handles
    # classmethods properly.
    "offline",
})

# Type-mapping rules consulted by `test_method_signatures.py` (T013).
# Maps a Python-side annotation to the set of accel-side annotations
# that are considered equivalent.
SIGNATURE_TYPE_EQUIVALENTS: dict[str, set[str]] = {
    "float": {"float", "f64", "f32"},
    "int": {"int", "i32", "i64", "u8", "u32", "u64"},
    "bool": {"bool"},
    "str": {"str", "String"},
    "bytes": {"bytes", "Vec<u8>"},
    "ItemSlot | None": {"ItemSlot | None", "Optional[ItemSlot]"},
    "tuple[float, float, float]": {"tuple[float, float, float]"},
}
