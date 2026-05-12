"""T043 — Public API surface parity.

Enumerates the symbols/methods the accel package MUST export so that
the migration recipe in `docs/migration_to_accel.md` works as
advertised. Confirms presence (and approximate signature shape) on
both backends.

The accel surface is **growing** incrementally; this test pins what
ships today so regressions are caught immediately.
"""

from __future__ import annotations

import inspect

import pytest


# (attribute path, kind). kind ∈ {"class", "func", "module", "attr"}.
ACCEL_REQUIRED_SURFACE: list[tuple[str, str]] = [
    # Module-level identity
    ("__version__", "attr"),
    ("python_compat", "attr"),
    ("implementation", "attr"),
    # Top-level submodules
    ("errors", "module"),
    ("codec", "module"),
    ("framer", "module"),
    ("world", "module"),
    ("pathfinding", "module"),
    ("physics", "module"),
    # Bot / WireLog classes
    ("Bot", "class"),
    ("WireLog", "class"),
    # codec primitives
    ("codec.Reader", "class"),
    ("codec.Writer", "class"),
    ("codec.varint", "module"),
    ("codec.varlong", "module"),
    # World class + helpers
    ("world.World", "class"),
    ("world.block_is_solid", "func"),
    ("world.block_is_water", "func"),
    ("world.block_name", "func"),
    ("world.decode_chunk_summary", "func"),
    # pathfinding
    ("pathfinding.find_path", "func"),
    # physics
    ("physics.tick", "func"),
    ("physics.PhysicsState", "class"),
    ("physics.PhysicsIntent", "class"),
    # framer
    ("framer.Framer", "class"),
    # errors (sample of the hierarchy)
    ("errors.ProtocolError", "class"),
    ("errors.DecodeError", "class"),
    ("errors.OversizedVarInt", "class"),
    ("errors.KickedByServer", "class"),
    ("errors.NoPathFound", "class"),
]

BOT_REQUIRED_METHODS: list[str] = [
    "connect", "disconnect", "entity_id", "health", "food", "position",
    "walk_to", "walk_to_blind", "drop_held_item", "world",
    "loaded_chunk_count",
]


def _resolve(root, dotted: str):
    obj = root
    for part in dotted.split("."):
        obj = getattr(obj, part)
    return obj


def test_accel_top_level_surface() -> None:
    import minecraft_bot_accel as mb_accel

    missing: list[str] = []
    type_mismatches: list[str] = []
    for path, kind in ACCEL_REQUIRED_SURFACE:
        try:
            obj = _resolve(mb_accel, path)
        except AttributeError:
            missing.append(path)
            continue
        if kind == "class" and not isinstance(obj, type):
            type_mismatches.append(f"{path}: expected class, got {type(obj).__name__}")
        elif kind == "func" and not callable(obj):
            type_mismatches.append(f"{path}: expected callable, got {type(obj).__name__}")
        elif kind == "module" and not inspect.ismodule(obj):
            type_mismatches.append(f"{path}: expected module, got {type(obj).__name__}")
    assert not missing, "missing accel symbols:\n  " + "\n  ".join(missing)
    assert not type_mismatches, "type mismatches:\n  " + "\n  ".join(type_mismatches)


def test_accel_bot_class_has_required_methods() -> None:
    import minecraft_bot_accel as mb_accel
    missing: list[str] = []
    for name in BOT_REQUIRED_METHODS:
        if not hasattr(mb_accel.Bot, name):
            missing.append(name)
    assert not missing, f"Bot is missing methods: {missing}"


def test_accel_bot_offline_classmethod() -> None:
    """Bot.offline must be a classmethod returning a Bot instance."""
    import minecraft_bot_accel as mb_accel
    # Construct without connecting — just verify the type.
    bot = mb_accel.Bot.offline("nowhere.invalid", 25565, "TestBot")
    assert type(bot).__name__ == "Bot"
    # repr smoke
    assert "Bot" in repr(bot)


def test_accel_python_compat_matches_minecraft_bot_version() -> None:
    """SC-007: accel.python_compat MUST cover minecraft_bot.__version__'s
    MAJOR.MINOR line."""
    import re
    import minecraft_bot
    import minecraft_bot_accel as mb_accel

    py_ver = minecraft_bot.__version__
    m = re.match(r"^(\d+)\.(\d+)", py_ver)
    assert m, f"python __version__ not semver: {py_ver}"
    py_major_minor = (m.group(1), m.group(2))

    compat = mb_accel.python_compat
    m2 = re.match(r"^(\d+)\.(\d+)\.", compat)
    assert m2, f"accel python_compat not semver-shaped: {compat}"
    ac_major_minor = (m2.group(1), m2.group(2))

    assert ac_major_minor == py_major_minor, (
        f"accel.python_compat {compat!r} does NOT cover "
        f"minecraft_bot {py_ver!r}"
    )


def test_both_backends_have_implementation_attr() -> None:
    """Both packages advertise their implementation identifier."""
    import minecraft_bot
    import minecraft_bot_accel as mb_accel

    assert minecraft_bot.implementation == "python"
    assert mb_accel.implementation == "rust"
    # They MUST differ so callers can dispatch on this.
    assert minecraft_bot.implementation != mb_accel.implementation
