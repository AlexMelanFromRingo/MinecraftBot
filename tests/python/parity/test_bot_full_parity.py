"""T012 — introspection parity gate.

Compares the public method set of `minecraft_bot.Bot` against
`minecraft_bot_accel.Bot`. The symmetric difference (minus
`PYTHON_ONLY_METHODS`) must be empty. The test is intentionally
xfail until 004 Group I lands; it becomes a hard gate once all
60 methods are ported.
"""

from __future__ import annotations

import pytest

import minecraft_bot
import minecraft_bot_accel

from tests.python.parity._method_collector import (
    MethodSpec,
    collect_public_methods,
)


# Flip to False when 004 Group I (T077) lands and the parity is
# complete. Until then this is xfail to keep CI green while still
# surfacing diffs in pytest output.
_PARITY_COMPLETE = False


pytestmark = pytest.mark.xfail(
    not _PARITY_COMPLETE,
    reason="004 in progress — full Bot parity lands at T077.",
    strict=False,
)


def _bot_class(module) -> type:
    """Return the `Bot` class from a backend module, regardless of
    whether it lives at `module.Bot` (accel) or
    `module.bot.Bot` (Python ref)."""
    if hasattr(module, "Bot"):
        return module.Bot
    return module.bot.Bot


def test_method_name_sets_match():
    """The Python and accel backends must expose the same public method
    names (excluding the PYTHON_ONLY allow-list).
    """
    py_methods = collect_public_methods(_bot_class(minecraft_bot))
    accel_methods = collect_public_methods(_bot_class(minecraft_bot_accel))

    py_names = set(py_methods.keys())
    accel_names = set(accel_methods.keys())

    missing_on_accel = sorted(py_names - accel_names)
    extra_on_accel = sorted(accel_names - py_names)

    msg = (
        f"Bot API parity broken.\n"
        f"  Missing on minecraft_bot_accel.Bot: {missing_on_accel}\n"
        f"  Extra on minecraft_bot_accel.Bot:  {extra_on_accel}"
    )
    assert not missing_on_accel and not extra_on_accel, msg


def test_method_kinds_match():
    """Each shared name must have the same kind (property vs async vs sync).
    """
    py = collect_public_methods(_bot_class(minecraft_bot))
    accel = collect_public_methods(_bot_class(minecraft_bot_accel))

    shared = set(py.keys()) & set(accel.keys())
    diffs: list[tuple[str, MethodSpec, MethodSpec]] = []
    for name in sorted(shared):
        if py[name].kind != accel[name].kind:
            diffs.append((name, py[name], accel[name]))

    msg = "\n".join(
        f"  {n}: python={p.kind!r}, accel={a.kind!r}" for n, p, a in diffs
    )
    assert not diffs, f"Method-kind mismatch on shared names:\n{msg}"
