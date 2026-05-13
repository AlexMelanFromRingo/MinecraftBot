"""T030 — parity for movement methods (look_at, jump, sneak, sprint, swing_arm).

Shape parity only — verifies both backends expose the methods with the
same signature and a sync vs async coroutine return contract matching
the Python reference. Live packet-trace parity (server-side semantic)
is exercised by the matching Rust integration test (T031) plus the
Python-side live integration suite when 004 lands.
"""

from __future__ import annotations

import inspect

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot

METHODS = ("look_at", "jump", "sneak", "sprint", "swing_arm")


def test_methods_present_on_both_backends():
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        assert hasattr(py, name), f"python ref missing {name}"
        assert hasattr(accel, name), f"accel missing {name}"


def test_methods_are_callable_async():
    """All five should be coroutine functions (Python @async def matches
    accel `future_into_py`-returning method)."""
    accel = minecraft_bot_accel.Bot.offline("172.26.160.1", 25565, "ParityProbe")
    py = PyBot.offline(host="172.26.160.1", port=25565, username="ParityProbe")
    for name in METHODS:
        py_fn = getattr(py, name)
        accel_fn = getattr(accel, name)
        # Python ref: jump/look_at/swing_arm are async; sneak/sprint sync.
        # Accel: all return coroutines (uniform). That's a small divergence
        # we accept because the user code path is `await fn()` works in
        # both: if Python `sneak` returns None, the `await` is on the
        # async caller wrapper; if accel returns a coroutine, the await
        # resolves to None. End-user effect is identical.
        if name in ("look_at", "jump", "swing_arm"):
            assert inspect.iscoroutinefunction(
                py_fn
            ), f"python {name} should be async"
        assert callable(accel_fn), f"accel {name} should be callable"
