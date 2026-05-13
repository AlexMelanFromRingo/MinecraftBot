"""T026 — parity for the 17 state accessors of Group A.

This is a **shape parity** test, not a live-server semantic parity test.
It verifies that on a freshly-constructed (un-connected) Bot:

* Each accessor exists on both backends as a sync property (per Q1).
* Each accessor returns a value of the same Python type on both
  backends (default int/float/bool/None).
* Reading an accessor does not raise on a disconnected Bot.

Per-method live-server parity (the actual values after the Login +
SetExperience + SetHeldItem packets land) is verified by the live
integration test `tests/python/integration/test_bot_full_parity_live.py`
which lives in Phase 3 Group A's live-smoke landing (T027 + the
matching Rust integration test).
"""

from __future__ import annotations

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot

ACCESSORS: tuple[str, ...] = (
    "x", "y", "z",
    "yaw", "pitch", "on_ground",
    "health", "food", "saturation", "is_dead",
    "xp_level", "xp_total",
    "game_mode", "held_slot",
    "entity_id", "world_name", "dimension",
    "is_sneaking", "is_sprinting",
    "position",
)


def _py_bot() -> object:
    return PyBot.offline(
        host="172.26.160.1", port=25565, username="ParityProbe"
    )


def _accel_bot() -> object:
    return minecraft_bot_accel.Bot.offline(
        "172.26.160.1", 25565, "ParityProbe"
    )


def test_accessors_present_on_both_backends():
    py = _py_bot()
    accel = _accel_bot()
    for name in ACCESSORS:
        assert hasattr(py, name), f"Python ref missing accessor: {name}"
        assert hasattr(accel, name), f"accel missing accessor: {name}"


def test_accessor_return_types_match():
    """Per Q1, accessors are sync properties on both backends. The
    returned types must be equivalent (modulo Optional[X] vs None
    when uninitialised)."""
    py = _py_bot()
    accel = _accel_bot()
    diffs: list[str] = []
    for name in ACCESSORS:
        v_py = getattr(py, name)
        v_accel = getattr(accel, name)
        if v_py is None and v_accel is None:
            continue
        if type(v_py) is not type(v_accel):
            diffs.append(
                f"{name}: python={type(v_py).__name__}={v_py!r}, "
                f"accel={type(v_accel).__name__}={v_accel!r}"
            )
    assert not diffs, "Accessor return-type mismatch:\n  " + "\n  ".join(diffs)


def test_accessors_are_sync_not_coroutine():
    """Q1 invariant: reading an accessor must not return a coroutine.
    Otherwise existing Python scripts that do `if bot.health < 5` break.
    """
    import inspect
    accel = _accel_bot()
    for name in ACCESSORS:
        v = getattr(accel, name)
        assert not inspect.iscoroutine(
            v
        ), f"{name} returned a coroutine — should be sync property"
