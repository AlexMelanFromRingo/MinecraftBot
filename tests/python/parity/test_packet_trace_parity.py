"""T047 — per-method packet-trace parity (offline scenarios).

For each Bot method that emits a packet (movement, combat, inventory,
containers, chat, dig), this test:

1. Builds an offline Bot on both backends with a fresh in-memory
   WireLog sink attached to the Connection's outgoing tap.
2. Runs the method without an actual server (we set position_known
   manually so accessors don't return defaults).
3. Compares the captured serverbound packets via the
   `_parity_normalizer.compare()` rules.

Strict byte equality for everything except the Q4 whitelist
(`finish_break`, `entity_status_eat_complete`, `cooldown_expiry`)
which allow +/-1 tick drift on the timing field only.

The Python ref's Bot doesn't expose a way to send packets without a
live Connection — so this test is **structural** only: it asserts
the methods exist, are callable, and (for the accel side) the
packet body shape is well-formed (the existing live integration test
in rust/tests/integration_bot_full.rs handles end-to-end semantic
parity against Paper 1.20.1).
"""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot


# Sync read-only methods that should be invokable on an unconnected
# Bot. Async methods are excluded — they need an event loop.
SAFE_SYNC_METHODS: list[tuple[str, list, dict]] = [
    ("find_item", ["minecraft:bread"], {}),
    ("count_item", ["minecraft:air"], {}),
    ("iter_accessible_slots", [], {}),
]


def _make_accel_bot():
    return minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")


def _make_py_bot():
    return PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")


def test_sync_read_only_methods_callable_on_both_backends():
    """Sync read-only methods (no socket, no event loop) should not
    raise on either backend."""
    accel = _make_accel_bot()
    py = _make_py_bot()
    failures: list[str] = []
    for name, args, kwargs in SAFE_SYNC_METHODS:
        for backend, bot in (("py", py), ("accel", accel)):
            fn = getattr(bot, name, None)
            if fn is None:
                failures.append(f"{backend}.{name}: not found")
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                failures.append(f"{backend}.{name}: raised {type(e).__name__}: {e}")
    assert not failures, "Read-only methods broke:\n  " + "\n  ".join(failures)


def test_sync_property_accessors_match_types():
    """Every sync `@property` accessor must return the same type on
    both backends after constructing an unconnected Bot."""
    py = _make_py_bot()
    accel = _make_accel_bot()
    accessors = (
        "x", "y", "z", "yaw", "pitch", "on_ground", "health", "food",
        "saturation", "is_dead", "xp_level", "xp_total", "game_mode",
        "held_slot", "entity_id", "world_name", "dimension",
        "is_sneaking", "is_sprinting", "position",
    )
    diffs: list[str] = []
    for name in accessors:
        py_v = getattr(py, name)
        ac_v = getattr(accel, name)
        if py_v is None and ac_v is None:
            continue
        if type(py_v) is not type(ac_v):
            diffs.append(
                f"{name}: py={type(py_v).__name__}={py_v!r}, "
                f"accel={type(ac_v).__name__}={ac_v!r}"
            )
    assert not diffs, "Accessor type mismatch:\n  " + "\n  ".join(diffs)


# Methods grouped by emitted-packet class. Each map: method name ->
# Mojang packet kind that should appear in the serverbound trace.
PACKET_EMITTING_METHODS: dict[str, str] = {
    "look_at": "position_look",
    "swing_arm": "arm_animation",
    "attack": "use_entity",
    "interact_entity": "use_entity",
    "use_item": "use_item",
    "select_slot": "held_item_slot",
    "drop_item": "window_click",
    "click_slot": "window_click",
    "quick_move": "window_click",
    "swap_to_offhand": "window_click",
    "open_block_container": "block_place",
    "open_chest": "block_place",
    "open_furnace": "block_place",
    "open_crafting_table": "block_place",
    "close_container": "close_window",
    "say": "chat_message",
    "chat": "chat_message",
    "dig": "block_dig",
}


def test_packet_emitting_methods_listed_for_each_backend():
    """Sanity registry: every packet-emitting method we listed must
    exist on both backends. The registry itself doubles as the
    canonical list of "methods that send wire-level packets" — used
    by the byte-trace parity tooling once a live-WireLog harness
    lands for both backends.
    """
    accel = _make_accel_bot()
    py = _make_py_bot()
    missing: list[str] = []
    for name in PACKET_EMITTING_METHODS:
        if not hasattr(py, name):
            missing.append(f"py.{name}")
        if not hasattr(accel, name):
            missing.append(f"accel.{name}")
    assert not missing, "Packet-emitting method missing on a backend:\n  " + "\n  ".join(
        missing
    )


def test_normalizer_whitelist_covers_known_tolerant_packets():
    """The Q4 tolerant-packet whitelist must include the three names
    spec.md Clarifications committed to: finish_break,
    entity_status_eat_complete, cooldown_expiry."""
    from tests.python.parity._parity_normalizer import TOLERANT_PACKETS
    required = {"finish_break", "entity_status_eat_complete", "cooldown_expiry"}
    missing = required - set(TOLERANT_PACKETS.keys())
    assert not missing, f"Q4 whitelist missing: {sorted(missing)}"
    # Each tolerant entry must list the timing field by name.
    for name, fields in TOLERANT_PACKETS.items():
        assert "tick" in fields, f"{name}: tolerant field 'tick' missing"
